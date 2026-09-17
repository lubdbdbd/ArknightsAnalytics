from __future__ import annotations

import csv
import io
import json
import os
import sqlite3
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest

from .product_catalog import CATEGORY_CODES, build_internal_product_master, build_public_listing_master
from .operations_brief import build_operations_brief, render_operations_brief
from .operations_tasks import register_tasks, excel_text
from .erp_reconciliation import reconcile_orders
from .erp_checks import TABLES as ERP_CHECK_TABLES, build_erp_checks
from .decision_evidence import build_decision_evidence, render_decision_evidence
from .public_data_api import register_public_data
from .lifecycle import build_lifecycle, render_lifecycle
from .gmv import ScenarioComparison, build_gmv_report, compare_scenario, render_gmv_report
from .channel_strategy import build_channel_strategy, render_channel_strategy
from .business_decisions import build_business_decisions, render_business_decisions

ROOT = Path(__file__).resolve().parents[2]
DATASETS = {
    'daily': 'erp_daily_kpis', 'inventory': 'erp_sku_diagnostics',
    'replenishment': 'erp_replenishment_plan', 'orders': 'erp_order_headers',
    'order_lines': 'erp_order_lines', 'aftersales': 'erp_after_sales',
    'reasons': 'erp_after_sales_pareto', 'channels': 'erp_channel_profitability',
    'erp_categories': 'erp_category_diagnostics', 'survey_profile': 'survey_243_profile_summary',
    'survey_categories': 'survey_243_category_summary', 'survey_operators': 'survey_243_operator_summary',
    'survey_prices': 'survey_243_price_summary', 'survey_barriers': 'survey_243_barrier_summary',
    'survey_ages': 'survey_243_age_summary', 'survey_channels': 'survey_243_channel_summary',
    'demand': 'operator_demand_fusion', 'portfolio': 'operator_category_portfolio',
    'evidence': 'evidence_inventory', 'dictionary': 'product_field_dictionary',
}
INTERNAL_FIELDS = {'product_name', 'supplier_id', 'price', 'unit_cost', 'safety_stock',
                   'reorder_point', 'purchase_lead_time_days', 'sku_status'}
PUBLIC_FIELDS = {'product_title', 'operator', 'category', 'list_price', 'fulfillment_type',
                 'verification_status', 'evidence_url'}
NUMERIC_FIELDS = {'price', 'unit_cost', 'safety_stock', 'reorder_point', 'purchase_lead_time_days', 'list_price'}


class CatalogEdit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: int = Field(ge=0)
    changes: dict[str, str | float | int] = Field(min_length=1)
    reason: str = Field(min_length=3, max_length=500)


class ImportPreview(BaseModel):
    csv_text: str = Field(max_length=500_000)


def records(frame: pd.DataFrame) -> list[dict]:
    return json.loads(frame.to_json(orient='records', force_ascii=False))


def filter_rows(frame: pd.DataFrame, q: str = '', category: str = '', channel: str = '',
                start_date: date | None = None, end_date: date | None = None) -> pd.DataFrame:
    if start_date and end_date and start_date > end_date:
        raise HTTPException(422, '开始日期不能晚于结束日期')
    for field, value in [('category', category), ('channel', channel)]:
        if value and field in frame:
            frame = frame[frame[field].eq(value)]
    date_field = next((field for field in ['order_date', 'date', 'requested_at'] if field in frame), None)
    if (start_date or end_date) and not date_field:
        raise HTTPException(422, '该数据集不支持日期筛选')
    if date_field:
        dates = pd.to_datetime(frame[date_field], errors='coerce').dt.date
        if start_date:
            frame = frame[dates >= start_date]
        if end_date:
            frame = frame[dates.loc[frame.index] <= end_date]
    if q:
        frame = frame[frame.astype(str).apply(lambda column: column.str.contains(q, regex=False, case=False)).any(axis=1)]
    return frame.copy()


def create_app(root: Path = ROOT, state_path: Path | None = None) -> FastAPI:
    app = FastAPI(title='Arknights Analytics', version='0.2.0', description='IP周边选品与商品运营分析平台')
    register_public_data(app, root)

    @app.get('/api/business-decisions')
    def business_decisions(download: Literal['markdown', 'json'] | None = None):
        try:
            report = build_business_decisions(root)
        except (OSError, ValueError, KeyError) as error:
            raise HTTPException(503, f'商业数据决策无法生成，请检查输入：{error}')
        if download:
            body = render_business_decisions(report) if download == 'markdown' else json.dumps(report, ensure_ascii=False, allow_nan=False)
            extension, media = ('md', 'text/markdown') if download == 'markdown' else ('json', 'application/json')
            return Response(body, media_type=media+'; charset=utf-8',
                            headers={'Content-Disposition': f'attachment; filename="ark-business-decisions.{extension}"'})
        return report

    @app.get('/api/channel-strategy')
    def channel_strategy(download: Literal['markdown', 'json'] | None = None):
        try:
            report = build_channel_strategy(root)
        except (OSError, ValueError, KeyError) as error:
            raise HTTPException(503, f'渠道分析无法生成，请检查输入：{error}')
        if download:
            body = render_channel_strategy(report) if download == 'markdown' else json.dumps(report, ensure_ascii=False, allow_nan=False)
            extension, media = ('md', 'text/markdown') if download == 'markdown' else ('json', 'application/json')
            return Response(body, media_type=media+'; charset=utf-8',
                            headers={'Content-Disposition': f'attachment; filename="ark-channel-strategy.{extension}"'})
        return report

    @app.get('/api/gmv-drivers')
    def gmv_drivers(download: Literal['markdown', 'json'] | None = None):
        try:
            report = build_gmv_report(root)
        except (OSError, ValueError, KeyError) as error:
            raise HTTPException(503, f'GMV分析无法生成，请检查输入：{error}')
        if download:
            body = render_gmv_report(report) if download == 'markdown' else json.dumps(report, ensure_ascii=False, allow_nan=False)
            extension, media = ('md', 'text/markdown') if download == 'markdown' else ('json', 'application/json')
            return Response(body, media_type=media+'; charset=utf-8',
                            headers={'Content-Disposition': f'attachment; filename="ark-gmv-drivers.{extension}"'})
        return report

    @app.post('/api/gmv-drivers/scenario')
    def gmv_scenario(payload: ScenarioComparison):
        return compare_scenario(payload.base, payload.candidate)

    @app.get('/api/lifecycle')
    def lifecycle(as_of: date | None = None, download: Literal['markdown', 'json'] | None = None):
        try:
            report = build_lifecycle(root, as_of)
        except (OSError, ValueError, KeyError) as error:
            raise HTTPException(503, f'生命周期分析无法生成，请检查输入：{error}')
        if download:
            body = render_lifecycle(report) if download == 'markdown' else json.dumps(report, ensure_ascii=False, allow_nan=False)
            extension, media = ('md', 'text/markdown') if download == 'markdown' else ('json', 'application/json')
            return Response(body, media_type=media+'; charset=utf-8',
                            headers={'Content-Disposition': f'attachment; filename="ark-lifecycle.{extension}"'})
        return report

    processed = root / 'data' / 'processed'
    state_path = state_path or Path(os.getenv('ARK_STATE_DB', str(root / 'data' / 'runtime' / 'platform.db')))
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(state_path) as connection:
        connection.executescript('''
            CREATE TABLE IF NOT EXISTS catalog_overrides (
                domain TEXT NOT NULL, entity_id TEXT NOT NULL, changes TEXT NOT NULL,
                version INTEGER NOT NULL, PRIMARY KEY(domain, entity_id));
            CREATE TABLE IF NOT EXISTS catalog_audit (
                audit_id INTEGER PRIMARY KEY AUTOINCREMENT, domain TEXT NOT NULL,
                entity_id TEXT NOT NULL, changed_at TEXT NOT NULL, reason TEXT NOT NULL,
                before_json TEXT NOT NULL, after_json TEXT NOT NULL, version INTEGER NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_catalog_audit_entity ON catalog_audit(domain, entity_id, audit_id);
        ''')
    registry = CollectorRegistry()
    requests_total = Counter('ark_http_requests_total', 'HTTP requests', ['method', 'route', 'status'], registry=registry)
    latency = Histogram('ark_http_duration_seconds', 'HTTP latency', ['route'], registry=registry)
    redis_client = None
    if os.getenv('REDIS_URL'):
        import redis
        redis_client = redis.Redis.from_url(os.environ['REDIS_URL'], socket_connect_timeout=0.2, socket_timeout=0.2)

    def read(name: str) -> pd.DataFrame:
        path = processed / f'{name}.csv'
        if not path.exists():
            raise HTTPException(503, f'缺少分析数据：{name}，请先运行数据管道')
        return pd.read_csv(path, keep_default_na=True)

    def overrides(domain: str) -> dict:
        with sqlite3.connect(state_path) as connection:
            return {entity_id: (json.loads(changes), version) for entity_id, changes, version in connection.execute(
                'SELECT entity_id, changes, version FROM catalog_overrides WHERE domain=?', (domain,))}

    def catalog(domain: str) -> pd.DataFrame:
        edits = overrides(domain)
        if domain == 'internal':
            frame = read('erp_sku_master')
            for index, row in frame.iterrows():
                for field, value in edits.get(str(row['sku_code']), ({}, 0))[0].items():
                    frame.at[index, field] = value
            frame = build_internal_product_master(frame)
            frame['entity_id'] = frame['sku_code'].astype(str)
        else:
            source = read('taobao_public_snapshots')
            field_map = {'product_title': 'raw_text', 'operator': 'target_operator', 'list_price': 'price'}
            for index, row in source.iterrows():
                entity_id = f"TB-{str(row['item_id'])}"
                for field, value in edits.get(entity_id, ({}, 0))[0].items():
                    if field not in {'verification_status', 'evidence_url'}:
                        source.at[index, field_map.get(field, field)] = value
            frame = build_public_listing_master(source)
            frame['entity_id'] = frame['external_sku_id'].astype(str)
            frame['verification_status'] = frame['entity_id'].map(lambda key: edits.get(key, ({}, 0))[0].get('verification_status', 'pending'))
            frame['evidence_url'] = frame['entity_id'].map(lambda key: edits.get(key, ({}, 0))[0].get('evidence_url', ''))
        frame['version'] = frame['entity_id'].map(lambda key: edits.get(key, ({}, 0))[1])
        return frame

    def validate(domain: str, current: dict, changes: dict) -> dict:
        allowed = INTERNAL_FIELDS if domain == 'internal' else PUBLIC_FIELDS
        if set(changes) - allowed:
            raise HTTPException(422, '包含不可修改字段')
        clean = {}
        for key, value in changes.items():
            if key in NUMERIC_FIELDS:
                try:
                    number = float(value)
                except (ValueError, TypeError):
                    raise HTTPException(422, f'{key} 必须为数字')
                if not 0 <= number <= 10_000_000 or (key in {'price', 'list_price'} and number == 0):
                    raise HTTPException(422, f'{key} 数值超出范围')
                if key in {'safety_stock', 'reorder_point', 'purchase_lead_time_days'} and not number.is_integer():
                    raise HTTPException(422, f'{key} 必须是整数')
                clean[key] = number
            else:
                text = str(value).strip()
                if len(text) > 1000 or (key != 'evidence_url' and not text):
                    raise HTTPException(422, f'{key} 不能为空或过长')
                clean[key] = text
        merged = current | clean
        if domain == 'internal':
            if merged['unit_cost'] >= merged['price']:
                raise HTTPException(422, '单位成本必须低于售价')
            if merged['reorder_point'] < merged['safety_stock']:
                raise HTTPException(422, '再订货点不能低于安全库存')
            if merged['sku_status'] not in {'active', 'planned', 'inactive'}:
                raise HTTPException(422, '生命周期状态无效')
        else:
            if merged['category'] not in {*CATEGORY_CODES, '其他正版周边'}:
                raise HTTPException(422, '品类必须来自标准字典')
            if merged['fulfillment_type'] not in {'未标明', '现货/在售', '预售', '补款'}:
                raise HTTPException(422, '履约类型必须来自标准字典')
            if merged['verification_status'] not in {'pending', 'verified', 'rejected'}:
                raise HTTPException(422, '核验状态无效')
            evidence = merged.get('evidence_url', '')
            if (evidence or merged['verification_status'] != 'pending') and (urlparse(evidence).scheme not in {'http', 'https'} or not urlparse(evidence).netloc):
                raise HTTPException(422, '确认或驳回授权需要提供 HTTP(S) 证据链接')
        return clean

    @app.middleware('http')
    async def observe(request: Request, call_next):
        started = time.perf_counter()
        if request.method in {'POST', 'PATCH'}:
            origin = request.headers.get('origin')
            if origin and urlparse(origin).netloc != request.headers.get('host'):
                return Response('Cross-origin writes are disabled', status_code=403)
        response = await call_next(request)
        route = getattr(request.scope.get('route'), 'path', 'static')
        requests_total.labels(request.method, route, response.status_code).inc()
        latency.labels(route).observe(time.perf_counter() - started)
        return response

    @app.get('/api/health')
    def health():
        redis_status = '未配置（直读本地数据）'
        if redis_client:
            try:
                redis_status = '在线' if redis_client.ping() else '不可用'
            except Exception:
                redis_status = '不可用（已回退直读）'
        with sqlite3.connect(state_path) as connection:
            connection.execute('SELECT 1')
        return {'status': 'ok', 'api': 'FastAPI', 'database': 'SQLite', 'redis': redis_status,
                'categories': list(CATEGORY_CODES), 'mode': '本地单用户运营工作台', 'time': datetime.now(timezone.utc).isoformat()}

    @app.get('/api/overview')
    def overview():
        internal, public = catalog('internal'), catalog('public')
        daily, inventory = read('erp_daily_kpis'), read('erp_sku_diagnostics')
        profile = records(read('survey_243_profile_summary'))[0]
        return {'sku_count': len(internal), 'listing_count': len(public),
                'maintenance_count': int(public['maintenance_priority'].ne('P2-可入库').sum()),
                'verified_count': int(public['verification_status'].eq('verified').sum()),
                'order_count': int(daily['order_count'].sum()), 'revenue': float(inventory['net_sales_after_refund'].sum()),
                'gross_profit': float(inventory['gross_profit'].sum()),
                'refund_amount': float(inventory['refund_amount'].sum()),
                'inventory_value': float((inventory['ending_inventory'] * inventory['unit_cost']).sum()),
                'date_start': daily['date'].min(), 'date_end': daily['date'].max(),
                'survey': profile, 'category_count': len(CATEGORY_CODES),
                'data_updated_at': datetime.fromtimestamp((processed / 'erp_daily_kpis.csv').stat().st_mtime, timezone.utc).isoformat(),
                'daily': records(daily), 'categories': records(read('erp_category_diagnostics')),
                'top_operators': records(read('survey_243_operator_summary').head(5))}

    @app.get('/api/operations/brief')
    def operations_brief(download: bool = False):
        brief = build_operations_brief(catalog('public'), read('erp_channel_profitability'),
                                       read('survey_243_category_summary'), read('survey_243_barrier_summary'),
                                       read('erp_replenishment_plan'))
        if download:
            return Response(render_operations_brief(brief), media_type='text/markdown; charset=utf-8',
                            headers={'Content-Disposition': 'attachment; filename="ark-operations-brief.md"'})
        return brief

    register_tasks(app, state_path, operations_brief)

    @app.get('/api/decision-evidence')
    def decision_evidence(download: bool = False):
        try:
            report = build_decision_evidence(root)
        except (OSError, ValueError, KeyError) as error:
            raise HTTPException(503, f'决策证据无法生成，请复核输入数据：{error}')
        if download:
            return Response(render_decision_evidence(report), media_type='text/markdown; charset=utf-8',
                            headers={'Content-Disposition': 'attachment; filename="ark-decision-evidence.md"'})
        report['robustness'].pop('experiments')
        return report

    @app.get('/api/data/{dataset}')
    def dataset_rows(dataset: str, q: str = '', category: str = '', page: int = Query(1, ge=1),
                     limit: int = Query(30, ge=1, le=1000), order_id: str = '', channel: str = '',
                     start_date: date | None = None, end_date: date | None = None):
        if dataset not in DATASETS:
            raise HTTPException(404, '数据集不存在')
        path = processed / f'{DATASETS[dataset]}.csv'
        cache_key = f'ark:v1:{dataset}:{path.stat().st_mtime_ns}' if path.exists() else ''
        frame = None
        if redis_client and dataset not in {'orders', 'order_lines', 'aftersales'}:
            try:
                cached = redis_client.get(cache_key)
                if cached:
                    frame = pd.DataFrame(json.loads(cached))
            except Exception:
                pass
        if frame is None:
            frame = read(DATASETS[dataset])
            if redis_client and dataset not in {'orders', 'order_lines', 'aftersales'}:
                try:
                    redis_client.setex(cache_key, 60, json.dumps(records(frame)))
                except Exception:
                    pass
        if order_id and 'order_id' in frame:
            frame = frame[frame['order_id'].eq(order_id)]
        frame = filter_rows(frame, q, category, channel, start_date, end_date)
        return {'items': records(frame.iloc[(page-1)*limit:page*limit]), 'total': len(frame), 'page': page,
                'is_simulated': dataset in {'daily', 'inventory', 'replenishment', 'orders', 'order_lines', 'aftersales', 'reasons', 'channels', 'erp_categories'}}

    @app.get('/api/erp/reconciliation')
    def reconciliation(q: str = '', channel: str = '', start_date: date | None = None, end_date: date | None = None):
        all_headers, lines = read('erp_order_headers'), read('erp_order_lines')
        headers = filter_rows(all_headers, q=q, channel=channel, start_date=start_date, end_date=end_date)
        checked = reconcile_orders(headers, lines)
        issues = checked[~checked['passed']]
        orphan_count = int((~lines['order_id'].isin(all_headers['order_id'])).sum())
        return {'checked_count': len(checked), 'passed_count': int(checked['passed'].sum()),
                'issue_count': len(issues), 'issues': records(issues.head(100)),
                'global_orphan_line_count': orphan_count, 'tolerance': 0.01, 'is_simulated': True,
                'paid_total': round(float(headers['paid_amount'].sum()), 2)}

    @app.get('/api/erp/checks')
    def erp_checks(scenario: Literal['snapshot', 'demo'] = 'snapshot',
                   severity: Literal['error', 'warning'] | None = None, rule: str = '',
                   page: int = Query(1, ge=1), limit: int = Query(30, ge=1, le=200), download: bool = False):
        try:
            report = build_erp_checks({key: read(meta[0]) for key, meta in ERP_CHECK_TABLES.items()}, scenario)
        except (ValueError, KeyError) as error:
            raise HTTPException(503, f'ERP核对输入不可用：{error}')
        issues = [item for item in report.pop('issues') if (not severity or item['severity'] == severity)
                  and (not rule or item['rule_code'] == rule)]
        if download:
            output = io.StringIO(newline='')
            writer = csv.writer(output)
            columns = {'issue_id':'异常编号','domain':'业务域','rule':'核对规则','severity':'级别',
                       'source_table':'源表','source_row':'CSV源行号','record_id':'关联记录',
                       'observed':'观测值','expected':'核对依据','action':'复核建议'}
            writer.writerow(['数据范围','库存快照末日',*columns.values()])
            for item in issues:
                writer.writerow([excel_text(report['scope']), report['as_of'] or '',
                                 *[excel_text(item[key]) for key in columns]])
            return Response(output.getvalue().encode('utf-8-sig'), media_type='text/csv; charset=utf-8',
                            headers={'Content-Disposition': f'attachment; filename="erp-checks-{scenario}.csv"'})
        return report | {'items': issues[(page-1)*limit:page*limit], 'issue_total': len(issues), 'page': page, 'limit': limit}

    @app.get('/api/catalog/{domain}')
    def get_catalog(domain: Literal['internal', 'public'], q: str = '', category: str = '', pending: bool = False,
                    page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=500)):
        frame = catalog(domain)
        if category:
            frame = frame[frame['category'].eq(category)]
        if pending:
            frame = frame[frame['verification_status'].eq('pending')] if domain == 'public' else frame[frame['rule_issue_count'].gt(0)]
        if q:
            frame = frame[frame.astype(str).apply(lambda column: column.str.contains(q, regex=False, case=False)).any(axis=1)]
        return {'items': records(frame.iloc[(page-1)*limit:page*limit]), 'total': len(frame), 'page': page}

    @app.patch('/api/catalog/{domain}/{entity_id}')
    def edit_catalog(domain: Literal['internal', 'public'], entity_id: str, edit: CatalogEdit):
        current_rows = catalog(domain)
        match = current_rows[current_rows['entity_id'].eq(entity_id)]
        if match.empty:
            raise HTTPException(404, '商品不存在')
        current = records(match)[0]
        changes = validate(domain, current, edit.changes)
        if not edit.reason.strip():
            raise HTTPException(422, '请填写修改原因')
        with sqlite3.connect(state_path, timeout=10) as connection:
            connection.execute('BEGIN IMMEDIATE')
            saved = connection.execute('SELECT changes, version FROM catalog_overrides WHERE domain=? AND entity_id=?', (domain, entity_id)).fetchone()
            saved_changes, version = (json.loads(saved[0]), saved[1]) if saved else ({}, 0)
            if version != edit.version:
                raise HTTPException(409, '商品已被更新，请刷新后再编辑')
            merged_changes = saved_changes | changes
            connection.execute('INSERT OR REPLACE INTO catalog_overrides VALUES (?,?,?,?)',
                               (domain, entity_id, json.dumps(merged_changes, ensure_ascii=False), version + 1))
            connection.execute('INSERT INTO catalog_audit(domain,entity_id,changed_at,reason,before_json,after_json,version) VALUES (?,?,?,?,?,?,?)',
                               (domain, entity_id, datetime.now(timezone.utc).isoformat(), edit.reason.strip(),
                                json.dumps({key: current.get(key) for key in changes}, ensure_ascii=False),
                                json.dumps(changes, ensure_ascii=False), version + 1))
        return {'status': 'saved', 'version': version + 1, 'entity_id': entity_id,
                'message': '工作主档已更新，历史ERP快照保持原始统计口径'}

    @app.get('/api/audit')
    def audit(entity_id: str = '', limit: int = Query(100, ge=1, le=500)):
        with sqlite3.connect(state_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute('SELECT * FROM catalog_audit WHERE (? = \'\' OR entity_id=?) ORDER BY audit_id DESC LIMIT ?', (entity_id, entity_id, limit)).fetchall()
        return {'items': [dict(row) for row in rows]}

    @app.post('/api/import/preview')
    def preview_import(payload: ImportPreview):
        try:
            reader = csv.DictReader(io.StringIO(payload.csv_text.lstrip('\ufeff')))
            if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames) or 'sku_code' not in reader.fieldnames or set(reader.fieldnames) - INTERNAL_FIELDS - {'sku_code'}:
                raise HTTPException(422, 'CSV需要 sku_code，其他列仅支持可编辑商品字段')
            source_rows = list(reader)
            if not 1 <= len(source_rows) <= 500:
                raise HTTPException(422, '每批支持1至500条商品')
        except csv.Error:
            raise HTTPException(422, 'CSV格式错误')
        existing = {row['sku_code']: row for row in records(catalog('internal'))}
        seen, result = set(), []
        for number, row in enumerate(source_rows, 2):
            key = row.get('sku_code', '')
            changes = {field: value for field, value in row.items() if field != 'sku_code'}
            try:
                if None in row or any(value is None for value in row.values()):
                    raise HTTPException(422, '字段数量与表头不一致')
                if key not in existing or key in seen or not changes:
                    raise HTTPException(422, 'SKU不存在、重复或没有修改字段')
                cleaned = validate('internal', existing[key], changes)
                result.append({'line': number, 'sku_code': key, 'valid': True, 'version': existing[key]['version'], 'changes': cleaned})
            except HTTPException as error:
                result.append({'line': number, 'sku_code': key, 'valid': False, 'error': error.detail})
            seen.add(key)
        return {'items': result, 'valid_count': sum(row['valid'] for row in result), 'total': len(result)}

    @app.get('/api/export/{dataset}')
    def export(dataset: str, q: str = '', category: str = '', channel: str = '', pending: bool = False,
               start_date: date | None = None, end_date: date | None = None):
        if dataset in {'internal', 'public'}:
            frame = catalog(dataset)
        elif dataset in DATASETS:
            frame = read(DATASETS[dataset])
        else:
            raise HTTPException(404, '不支持导出该数据')
        if pending and dataset in {'internal', 'public'}:
            frame = frame[frame['verification_status'].eq('pending')] if dataset == 'public' else frame[frame['rule_issue_count'].gt(0)]
        frame = filter_rows(frame, q, category, channel, start_date, end_date)
        for column in frame.select_dtypes(include=['object', 'string']).columns:
            frame[column] = frame[column].map(lambda value: "'" + value if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')) else value)
        return Response(frame.to_csv(index=False).encode('utf-8-sig'), media_type='text/csv',
                        headers={'Content-Disposition': f'attachment; filename="ark-{dataset}.csv"'})

    @app.get('/metrics')
    def metrics():
        return Response(generate_latest(registry), media_type='text/plain; version=0.0.4')

    dist = root / 'frontend' / 'dist'
    if (dist / 'assets').exists():
        app.mount('/assets', StaticFiles(directory=dist / 'assets'), name='assets')

    @app.get('/')
    def index():
        if not (dist / 'index.html').exists():
            raise HTTPException(503, '请先构建 Vue 前端')
        return FileResponse(dist / 'index.html')

    return app


app = create_app()
