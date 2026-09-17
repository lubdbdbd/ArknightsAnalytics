"""Local operations handover workflow; source analytics remain read-only."""
from __future__ import annotations

import csv
import io
import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

Category = Literal['商品维护', 'ERP核对', '用户调研', '直播准备', '临时事务']
Status = Literal['todo', 'in_progress', 'blocked', 'done']
STATUS_LABELS = {'todo': '待处理', 'in_progress': '处理中', 'blocked': '待协助', 'done': '已完成'}
LOCAL_TZ = timezone(timedelta(hours=8))


class TaskInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    title: str = Field(min_length=2, max_length=120)
    category: Category
    description: str = Field(min_length=3, max_length=4000)
    acceptance: str = Field(min_length=3, max_length=1500)
    assignee: str = Field(default='', max_length=80)
    due_date: date | None = None
    priority: Literal['P0', 'P1', 'P2'] = 'P1'


class TaskUpdate(TaskInput):
    version: int = Field(ge=0)
    status: Status
    note: str = Field(min_length=3, max_length=2000)


def now() -> str:
    return datetime.now(LOCAL_TZ).isoformat(timespec='seconds')


def task_view(row: sqlite3.Row, today: date | None = None) -> dict:
    result = dict(row)
    today = today or datetime.now(LOCAL_TZ).date()
    result['overdue'] = bool(result['due_date'] and result['due_date'] < today.isoformat()
                             and result['status'] != 'done')
    result['status_label'] = STATUS_LABELS[result['status']]
    return result


def excel_text(value) -> str:
    text = '' if value is None else str(value)
    # CSV quoting alone does not stop spreadsheet formula interpretation.
    return "'" + text if text.lstrip().startswith(('=', '+', '-', '@')) or text.startswith(('\t', '\r', '\n')) else text


def register_tasks(app, state_path: Path, brief_builder: Callable[[], dict]) -> None:
    router = APIRouter(prefix='/api/operations/tasks', tags=['operations tasks'])

    @contextmanager
    def connect():
        connection = sqlite3.connect(state_path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    with connect() as connection:
        connection.executescript('''
            CREATE TABLE IF NOT EXISTS operation_tasks (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, category TEXT NOT NULL,
                description TEXT NOT NULL, acceptance TEXT NOT NULL,
                assignee TEXT NOT NULL, due_date TEXT, priority TEXT NOT NULL,
                status TEXT NOT NULL, note TEXT NOT NULL, nature TEXT NOT NULL,
                source TEXT NOT NULL, source_key TEXT UNIQUE, target TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL, version INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS operation_task_audit (
                audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL, changed_at TEXT NOT NULL, note TEXT NOT NULL,
                before_json TEXT NOT NULL, after_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_operation_task_audit ON operation_task_audit(task_id, audit_id);
        ''')

    def insert_task(connection, payload: TaskInput, *, nature: str, source: str,
                    source_key: str | None = None, target: str = '') -> dict:
        stamp = now()
        record = payload.model_dump(mode='json') | dict(
            id=uuid4().hex, status='todo', note='', nature=nature, source=source,
            source_key=source_key, target=target, created_at=stamp, updated_at=stamp, version=0)
        columns = ','.join(record)
        connection.execute(f"INSERT INTO operation_tasks ({columns}) VALUES ({','.join('?' for _ in record)})", tuple(record.values()))
        connection.execute('INSERT INTO operation_task_audit(task_id,changed_at,note,before_json,after_json) VALUES (?,?,?,?,?)',
                           (record['id'], stamp, '建立待办，尚未执行', '{}', json.dumps(record, ensure_ascii=False)))
        return task_view(record)

    def find_tasks(status: Status | None, category: Category | None, q: str, overdue: bool) -> list[dict]:
        with connect() as connection:
            rows = connection.execute("SELECT * FROM operation_tasks ORDER BY CASE WHEN status='done' THEN 1 ELSE 0 END, priority, COALESCE(due_date,'9999'), created_at, id").fetchall()
        items = [task_view(row) for row in rows]
        query = q.strip().casefold()
        return [item for item in items if (not status or item['status'] == status)
                and (not category or item['category'] == category)
                and (not overdue or item['overdue'])
                and (not query or query in ' '.join(str(item[key] or '') for key in
                     ('id', 'title', 'description', 'assignee', 'note', 'source')).casefold())]

    @router.get('')
    def list_tasks(status: Status | None = None, category: Category | None = None, q: str = '', overdue: bool = False):
        items = find_tasks(status, category, q, overdue)
        return {'items': items, 'total': len(items), 'counts': {key: sum(item['status'] == key for item in items) for key in STATUS_LABELS},
                'overdue_count': sum(item['overdue'] for item in items), 'as_of': now()}

    @router.post('', status_code=201)
    def create_task(payload: TaskInput):
        with connect() as connection:
            return insert_task(connection, payload, nature='人工登记事项（来源与结果待记录）', source='手工录入')

    @router.post('/from-brief')
    def from_brief():
        brief = brief_builder()
        categories = {'catalog': '商品维护', 'erp': 'ERP核对', 'research': '用户调研'}
        created, existing = [], []
        # Serialize source-key lookup and insert to make repeated clicks idempotent.
        with connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            for task in brief['tasks']:
                key = 'brief:' + task['id']
                row = connection.execute('SELECT * FROM operation_tasks WHERE source_key=?', (key,)).fetchone()
                if row:
                    existing.append(task_view(row))
                    continue
                created.append(insert_task(connection, TaskInput(
                    title=task['title'], category=categories[task['id']],
                    description=task['finding'] + '\n建议动作：' + task['action'], acceptance=task['acceptance']),
                    nature=task['nature'], source=task['source'], source_key=key, target=task['target']))
        return {'created': created, 'existing_count': len(existing)}

    @router.post('/live-checklist')
    def live_checklist():
        with connect() as connection:
            return insert_task(connection, TaskInput(
                title='直播前货品与问答准备（演练）', category='直播准备',
                description='逐项核对规格、价格、授权凭证、可售库存、预售交期、优惠口径与售后FAQ；记录缺失信息并确认对接人。',
                acceptance='记录每项核对结果、资料出处及未解决事项；无真实后台数据时不填写曝光、成交或转化成果。'),
                nature='直播准备演练，无真实开播或成交数据', source='运营简报的直播前检查清单')

    @router.get('/export')
    def export_tasks(status: Status | None = None, category: Category | None = None, q: str = '', overdue: bool = False):
        items = find_tasks(status, category, q, overdue)
        columns = {'id': '任务编号', 'title': '事项', 'category': '工作类别', 'priority': '优先级',
                   'status_label': '状态', 'assignee': '负责人', 'due_date': '截止日期', 'overdue': '是否逾期',
                   'description': '工作内容', 'acceptance': '验收要求', 'note': '最新进展或交接说明',
                   'nature': '数据性质', 'source': '来源', 'created_at': '创建时间', 'updated_at': '更新时间', 'version': '版本'}
        output = io.StringIO(newline='')
        writer = csv.writer(output)
        writer.writerow(columns.values())
        for item in items:
            writer.writerow([excel_text(('是' if item[key] else '否') if key == 'overdue' else item[key]) for key in columns])
        return Response(output.getvalue().encode('utf-8-sig'), media_type='text/csv; charset=utf-8',
                        headers={'Content-Disposition': 'attachment; filename="operations-handover.csv"'})

    @router.get('/{task_id}/history')
    def task_history(task_id: str):
        with connect() as connection:
            if not connection.execute('SELECT 1 FROM operation_tasks WHERE id=?', (task_id,)).fetchone():
                raise HTTPException(404, '待办不存在')
            rows = connection.execute('SELECT * FROM operation_task_audit WHERE task_id=? ORDER BY audit_id DESC', (task_id,)).fetchall()
        return {'items': [dict(row) | {'before': json.loads(row['before_json']), 'after': json.loads(row['after_json'])} for row in rows]}

    @router.patch('/{task_id}')
    def update_task(task_id: str, payload: TaskUpdate):
        if payload.status in {'in_progress', 'done'} and not payload.assignee:
            raise HTTPException(422, '开始处理或完成前，请填写负责人')
        if payload.status == 'done' and len(payload.note) < 10:
            raise HTTPException(422, '完成前请填写至少10字的处理结果及核对依据')
        if payload.status == 'blocked' and len(payload.note) < 10:
            raise HTTPException(422, '待协助时请填写至少10字的阻塞原因与需要的协助')
        with connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            row = connection.execute('SELECT * FROM operation_tasks WHERE id=?', (task_id,)).fetchone()
            if not row:
                raise HTTPException(404, '待办不存在')
            previous = dict(row)
            if previous['version'] != payload.version:
                raise HTTPException(409, '待办已被更新，请关闭编辑并刷新列表后重新修改')
            updates = payload.model_dump(mode='json') | {'version': payload.version + 1, 'updated_at': now()}
            connection.execute('UPDATE operation_tasks SET ' + ','.join(f'{key}=?' for key in updates) + ' WHERE id=?',
                               (*updates.values(), task_id))
            result = previous | updates
            connection.execute('INSERT INTO operation_task_audit(task_id,changed_at,note,before_json,after_json) VALUES (?,?,?,?,?)',
                               (task_id, result['updated_at'], payload.note, json.dumps(previous, ensure_ascii=False), json.dumps(result, ensure_ascii=False)))
        return task_view(result)

    app.include_router(router)
