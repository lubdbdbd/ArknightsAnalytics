from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import json

import pytest
from fastapi.testclient import TestClient

from arknights_merch_analytics.lifecycle import (build_lifecycle, classify_stage,
    event_windows, render_lifecycle, snapshot_deltas, trend_signal)
from arknights_merch_analytics.platform_api import create_app

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT/'config/lifecycle_policy.json').read_text(encoding='utf-8'))


def observation(when, views, key='A'):
    return {'platform':'bilibili','content_id':key,'collected_at':when,
            'published_at':'2026-01-01T00:00:00Z','view':views,'source_url':'https://example.com/'+key}


def test_duplicate_sources_do_not_double_count_and_negative_counters_not_hidden():
    first = observation('2026-09-01T00:00:00Z',100)
    result = snapshot_deltas([first,dict(first),observation('2026-09-08T00:00:00Z',170),
                              observation('2026-09-15T00:00:00Z',160)])
    assert len(result)==2
    assert result[0]['view_delta']==70 and result[0]['views_per_day']==10
    assert result[1]['status']=='counter_decreased' and result[1]['views_per_day'] is None


def test_conflicting_capture_is_rejected():
    with pytest.raises(ValueError,match='冲突'):
        snapshot_deltas([observation('2026-09-01',100),observation('2026-09-01',101)])


def test_two_captures_cannot_establish_a_trend():
    result=snapshot_deltas([observation('2026-09-01',100),observation('2026-09-08',10000)])
    assert trend_signal(result,{('bilibili','A')},POLICY)['label']=='待验证'


def make_intervals(increments, keys=('A','B'), dates=None):
    dates=dates or ['2026-08-01','2026-08-08','2026-08-15','2026-08-22']
    rows=[]
    for key in keys:
        total=100
        rows.append(observation(dates[0],total,key))
        for day,delta in zip(dates[1:],increments):
            total+=delta
            rows.append(observation(day,total,key))
    return snapshot_deltas(rows)


@pytest.mark.parametrize('increments,label',[
    ([70,140,280],'内容增速上升'),([280,140,70],'内容增速回落'),
    ([70,70,70],'内容增速相对平稳'),([70,140,70],'内容增速波动')])
def test_equal_window_trends(increments,label):
    signal=trend_signal(make_intervals(increments),{('bilibili','A'),('bilibili','B')},POLICY)
    assert signal['label']==label
    assert signal['sample_count']==2


def test_missing_cohort_and_irregular_intervals_are_not_interpolated():
    keys={('bilibili','A'),('bilibili','B')}
    assert trend_signal(make_intervals([70,140,280],keys=('A',)),keys,POLICY)['label']=='待验证'
    irregular=make_intervals([70,140,280],dates=['2026-08-01','2026-08-08','2026-08-16','2026-08-23'])
    assert trend_signal(irregular,keys,POLICY)['label']=='待验证'


def test_zero_baseline_is_not_infinite_growth():
    assert trend_signal(make_intervals([0,140,280]),{('bilibili','A'),('bilibili','B')},POLICY)['change'] is None


def test_event_type_and_age_do_not_fabricate_maturity_or_decline():
    promotion={'event_at':'2026-09-01','event_type':'promotion','verified':True}
    assert classify_stage([promotion],date(2026,9,12),POLICY)[0]=='事件观察期'
    assert classify_stage([{**promotion,'event_type':'release'}],date(2026,9,12),POLICY)[0]=='导入观察期'
    assert classify_stage([promotion],date(2026,11,1),POLICY)[0]=='阶段待验证'
    assert classify_stage([],date(2026,9,12),POLICY)[0]=='观察不足'


def test_event_window_excludes_its_own_anchor_and_flags_unfinished_period():
    event={'operator':'A','event_id':'e1','event_type':'promotion','event_at':'2026-09-01',
           'content_key':'bilibili:1','source_url':'https://example.com/1'}
    content={'operators':['A'],'key':'bilibili:1','published_at':'2026-09-01'}
    row=event_windows([event],[content],date(2026,9,12),28)[0]
    assert row['pre_other_content_in_sample']==row['post_other_content_in_sample']==0
    assert row['window_elapsed'] is False and row['demand_uplift'] is None


@pytest.fixture(scope='module')
def report():
    return build_lifecycle(ROOT)


def test_real_inputs_keep_unknown_roles_and_cross_sectional_boundary(report):
    assert len(report['operators'])==60
    assert len(report['weekly'])==60*POLICY['weekly_history']
    assert all(row['demand_stage']=='待验证' for row in report['operators'])
    assert any(row['stage']=='观察不足' for row in report['operators'])
    assert all(row['event_type']=='promotion' for row in report['events'])
    assert report['summary']['trend_ready_operators']==0
    assert sum(row['fractional_content_in_sample'] for row in report['weekly']) <= sum(
        row['bilibili_content_in_sample']+row['weibo_content_in_sample'] for row in report['weekly'])
    assert '不是新增采集数据' in render_lifecycle(report)
    json.dumps(report,allow_nan=False)


def test_historical_cutoff_does_not_use_later_expansion():
    early=build_lifecycle(ROOT,date(2026,9,3))
    assert early['summary']['all_content_intervals']==0
    assert all(row['last_capture'] is None or row['last_capture']<='2026-09-03' for row in early['operators'])


def test_api_and_download_contract(tmp_path):
    with TestClient(create_app(ROOT,tmp_path/'state.db')) as client:
        response=client.get('/api/lifecycle')
        assert response.status_code==200 and response.json()['summary']['operator_count']==60
        response=client.get('/api/lifecycle?download=markdown')
        assert response.status_code==200 and '角色生命周期' in response.text
        assert 'attachment' in response.headers['content-disposition']
        assert client.get('/api/lifecycle?as_of=not-a-date').status_code==422
        assert client.get('/api/lifecycle?as_of=2000-01-01').status_code==503
