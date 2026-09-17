from pathlib import Path

import pandas as pd
import pytest

from arknights_merch_analytics.decision_evidence import (
    build_decision_evidence, catalog_identity_audit, content_comparability,
    rank_robustness, render_decision_evidence, sql_order_case,
)

ROOT = Path(__file__).resolve().parents[1]


def demand_fixture():
    return pd.DataFrame([
        {'operator': '甲', 'content_signal': 100, 'survey_signal': 90, 'skland_signal': 80, 'commerce_signal': None},
        {'operator': '乙', 'content_signal': 10, 'survey_signal': 20, 'skland_signal': 30, 'commerce_signal': 40},
        {'operator': '丙', 'content_signal': None, 'survey_signal': None, 'skland_signal': None, 'commerce_signal': None},
    ])


def test_robustness_is_seeded_and_does_not_mutate_input():
    frame = demand_fixture()
    original = frame.copy(deep=True)
    first = rank_robustness(frame, runs=10, top_k=1)
    assert first == rank_robustness(frame, runs=10, top_k=1)
    pd.testing.assert_frame_equal(frame, original)
    assert first['scenario_count'] == 19
    assert first['excluded_no_signal'] == 1
    assert first['operators'][0]['operator'] == '甲'
    assert first['operators'][0]['perturb_top_k_share'] == 1


def test_missing_signal_is_not_a_zero_vote():
    report = rank_robustness(demand_fixture(), runs=1)
    baseline = next(row for row in report['experiments'] if row['scenario'] == 'balanced' and row['operator'] == '甲')
    assert baseline['score'] == pytest.approx((32 + 25.2 + 20) / .85)


def test_top_k_keeps_ties_and_leave_out_can_remove_only_source():
    frame = pd.DataFrame([{'operator': name, 'content_signal': 50, 'survey_signal': None,
                           'skland_signal': None, 'commerce_signal': None} for name in ['甲', '乙']])
    report = rank_robustness(frame, runs=1, top_k=1)
    assert report['scenarios'][0]['top_k_count'] == 2
    dropped = next(row for row in report['scenarios'] if row['scenario'] == 'without_content')
    assert dropped['ranked_count'] == 0
    assert dropped['rank_correlation'] is None


@pytest.mark.parametrize('change', ['duplicate', 'out_of_range', 'missing_operator'])
def test_invalid_rank_input_rejected(change):
    frame = demand_fixture()
    if change == 'duplicate':
        frame.loc[1, 'operator'] = '甲'
    elif change == 'missing_operator':
        frame.loc[0, 'operator'] = None
    else:
        frame.loc[0, 'content_signal'] = 101
    with pytest.raises(ValueError):
        rank_robustness(frame, runs=1)


def test_content_associations_conserve_unique_content():
    frame = pd.DataFrame([{'platform': 'weibo', 'bvid': None, 'post_id': '1', 'operator': name,
                           'published_at': '2026-09-01', 'collected_at': '2026-09-03'} for name in ['甲', '乙', '乙']])
    report = content_comparability(frame)
    assert report['unique_content'] == 1
    assert report['fractional_content_total'] == 1
    assert report['duplicate_role_links'] == 1


def test_content_missing_ids_and_bad_dates_are_reported():
    frame = pd.DataFrame([{'platform': 'bilibili', 'bvid': identifier, 'post_id': None, 'operator': '甲',
                           'published_at': '2026-09-05', 'collected_at': '2026-09-01'} for identifier in [None, 'a']])
    report = content_comparability(frame)
    assert report['missing_id_rows'] == 1
    assert report['time_invalid_rows'] == 1


def test_catalog_does_not_merge_same_title_different_ids():
    base = {'snapshot_at': '2026-09-01', 'category': '通行证', 'target_operator': '甲',
            'fulfillment_type': '预售', 'price': 10, 'operator_mentions': '甲', 'raw_text': '相同标题'}
    rows = [{**base, 'item_id': value} for value in ['1', '2', None]]
    rows.append({**base, 'item_id': '1', 'price': 20})
    report = catalog_identity_audit(pd.DataFrame(rows))
    assert report['unique_item_links'] == 2
    assert report['missing_id_rows'] == 1
    assert report['review_count'] == 1
    assert '价格冲突' in report['conflicts'][0]['reason']


def sql_fixture():
    headers = pd.DataFrame([{'order_id': 'O1', 'channel': '测试渠道', 'payment_status': 'paid',
                             'paid_amount': 100, 'order_amount': 100, 'discount_amount': 0}])
    lines = pd.DataFrame([{'order_line_id': name, 'order_id': 'O1', 'quantity': 1,
                           'unit_price': 50, 'discount_amount': 0} for name in ['L1', 'L2']])
    refunds = pd.DataFrame([{'case_id': name, 'order_id': 'O1', 'case_status': status, 'refund_amount': amount}
                            for name, status, amount in [('R1', 'closed', 10), ('R2', 'closed', 5), ('R3', 'open', 20)]])
    return headers, lines, refunds


def test_sql_two_one_to_many_relationships_do_not_inflate_amounts():
    report = sql_order_case(*sql_fixture(), (ROOT / 'sql/decision_order_case.sql').read_text())
    assert report['sql_paid_amount'] == 100
    assert report['naive_join_paid_amount_incorrect'] == 200
    assert report['channels'][0]['closed_refund_amount'] == 15
    assert report['channels'][0]['paid_less_closed_refunds'] == 85
    assert report['reconciliation_passed'] is True


@pytest.mark.parametrize('target', ['header', 'line', 'refund', 'orphan'])
def test_sql_bad_grain_is_rejected(target):
    frames = list(sql_fixture())
    if target == 'orphan':
        frames[1].loc[0, 'order_id'] = 'missing'
    else:
        position = ['header', 'line', 'refund'].index(target)
        frames[position] = pd.concat([frames[position], frames[position].iloc[:1]])
    with pytest.raises(ValueError):
        sql_order_case(*frames, (ROOT / 'sql/decision_order_case.sql').read_text())


def test_real_report_separates_approval_from_orders_and_has_fingerprints():
    report = build_decision_evidence(ROOT)
    assert report['survey']['response_count'] == 243
    assert report['robustness']['scenario_count'] == 209
    assert report['sql_case']['reconciliation_passed']
    assert all(len(row['sha256']) == 64 for row in report['manifest'])
    assert '不是新增真实订单' in render_decision_evidence(report)
    assert 'query' in report['sql_case']


def test_evidence_api_and_download(client):
    response = client.get('/api/decision-evidence')
    assert response.status_code == 200
    assert 'experiments' not in response.json()['robustness']
    download = client.get('/api/decision-evidence?download=true')
    assert download.status_code == 200
    assert 'attachment' in download.headers['content-disposition']
    assert 'SQL订单案例' in download.text


@pytest.fixture
def client(tmp_path):
    from fastapi.testclient import TestClient
    from arknights_merch_analytics.platform_api import create_app
    with TestClient(create_app(ROOT, tmp_path / 'state.db')) as instance:
        yield instance
