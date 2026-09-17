import csv
import io
from datetime import date

import pytest
from fastapi.testclient import TestClient

from arknights_merch_analytics.platform_api import ROOT, create_app
from arknights_merch_analytics.operations_tasks import task_view


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(ROOT, tmp_path / 'tasks.db')) as client:
        yield client


def create(client, **overrides):
    return client.post('/api/operations/tasks', json=dict(
        title='商品资料交接', category='商品维护', description='核对角色、规格和授权资料',
        acceptance='记录缺失字段及资料出处', **overrides))


def update_payload(task, **updates):
    fields = ['title', 'category', 'description', 'acceptance', 'assignee', 'due_date', 'priority', 'version', 'status']
    return {key: task[key] for key in fields} | {'note': '补充工作进度记录'} | updates


def test_brief_import_preserves_sources_and_deduplicates(client):
    first = client.post('/api/operations/tasks/from-brief').json()
    assert len(first['created']) == 3
    assert {t['category'] for t in first['created']} == {'商品维护', 'ERP核对', '用户调研'}
    erp = next(t for t in first['created'] if t['category'] == 'ERP核对')
    assert '模拟' in erp['nature'] and erp['status'] == 'todo'
    assert erp['assignee'] == '' and erp['due_date'] is None
    second = client.post('/api/operations/tasks/from-brief').json()
    assert second == {'created': [], 'existing_count': 3}
    assert client.get('/api/operations/tasks').json()['total'] == 3
    assert len(client.get(f"/api/operations/tasks/{erp['id']}/history").json()['items']) == 1


def test_workflow_history_conflict_and_reopen(client):
    task = create(client).json()
    url = '/api/operations/tasks/' + task['id']
    payload = update_payload(task, status='in_progress', assignee='演练负责人')
    response = client.patch(url, json=payload)
    assert response.status_code == 200
    current = response.json()
    assert current['version'] == 1
    assert client.patch(url, json=payload).status_code == 409
    done = client.patch(url, json=update_payload(current, status='done', note='已完成资料交接演练，核对依据见演练记录')).json()
    assert done['status'] == 'done'
    reopened = client.patch(url, json=update_payload(done, status='todo', note='资料发生变化，重新核查')).json()
    assert reopened['status'] == 'todo' and reopened['version'] == 3
    history = client.get(url + '/history').json()['items']
    assert len(history) == 4
    assert history[0]['before']['status'] == 'done' and history[0]['after']['status'] == 'todo'


@pytest.mark.parametrize('changes', [
    {'status': 'done', 'assignee': ''},
    {'status': 'in_progress', 'assignee': '   '},
    {'status': 'done', 'assignee': '演练人', 'note': '已完成'},
    {'status': 'blocked', 'note': '有问题'},
    {'status': 'invalid'}, {'due_date': '2026-02-30'}, {'title': '  '},
    {'nature': '真实收入'}, {'source_key': 'fake'},
])
def test_invalid_progress_does_not_write_history(client, changes):
    task = create(client).json()
    url = '/api/operations/tasks/' + task['id']
    assert client.patch(url, json=update_payload(task, **changes)).status_code == 422
    assert len(client.get(url + '/history').json()['items']) == 1
    assert client.get('/api/operations/tasks').json()['items'][0]['version'] == 0


def test_filtered_export_matches_list_and_neutralizes_formulas(client):
    task = create(client, assignee='=HYPERLINK("bad")', due_date='2020-01-01').json()
    client.post('/api/operations/tasks/live-checklist')
    filters = {'category': '商品维护', 'overdue': 'true'}
    listed = client.get('/api/operations/tasks', params=filters).json()
    response = client.get('/api/operations/tasks/export', params=filters)
    assert response.content.startswith(b'\xef\xbb\xbf')
    rows = list(csv.DictReader(io.StringIO(response.content.decode('utf-8-sig'))))
    assert len(rows) == listed['total'] == 1
    assert rows[0]['任务编号'] == task['id']
    assert rows[0]['负责人'].startswith("'=") and rows[0]['是否逾期'] == '是'
    assert rows[0]['状态'] == '待处理' and rows[0]['数据性质'] == task['nature']
    assert listed['overdue_count'] == 1 and listed['counts']['todo'] == 1


def test_empty_export_has_headers_and_live_template_is_labeled(client):
    response = client.get('/api/operations/tasks/export')
    reader = csv.DictReader(io.StringIO(response.content.decode('utf-8-sig')))
    assert '验收要求' in reader.fieldnames and list(reader) == []
    task = client.post('/api/operations/tasks/live-checklist').json()
    assert '演练' in task['nature'] and task['status'] == 'todo'
    assert '库存' in task['description'] and 'FAQ' in task['description']


def test_persistence_and_same_origin(client, tmp_path):
    with TestClient(create_app(ROOT, tmp_path / 'persist.db')) as one:
        task = create(one).json()
    with TestClient(create_app(ROOT, tmp_path / 'persist.db')) as two:
        assert two.get('/api/operations/tasks').json()['items'][0]['id'] == task['id']
    response = client.post('/api/operations/tasks/live-checklist', headers={'origin':'https://unrelated.example'})
    assert response.status_code == 403
    assert client.get('/api/operations/tasks').json()['total'] == 0


def test_due_date_boundary_and_completed_tasks():
    base = {'due_date':'2026-09-10','status':'todo'}
    assert not task_view(base, date(2026,9,10))['overdue']
    assert task_view(base, date(2026,9,11))['overdue']
    assert not task_view(base | {'status':'done'}, date(2026,9,11))['overdue']
    assert not task_view(base | {'due_date':None}, date(2026,9,11))['overdue']


def test_missing_task(client):
    assert client.get('/api/operations/tasks/unknown/history').status_code == 404
    task = create(client).json()
    assert client.patch('/api/operations/tasks/unknown', json=update_payload(task)).status_code == 404
