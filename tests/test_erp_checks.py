import io

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from arknights_merch_analytics.erp_checks import TABLES, build_erp_checks
from arknights_merch_analytics.erp_reconciliation import reconcile_orders
from arknights_merch_analytics.platform_api import ROOT, create_app


@pytest.fixture
def tables():
    return {
        'sku': pd.DataFrame([{'sku_id':'S1'}, {'sku_id':'S2'}]),
        'headers': pd.DataFrame([dict(order_id='O1', order_amount=100., discount_amount=10., shipping_fee=5., paid_amount=95., payment_status='paid')]),
        'lines': pd.DataFrame([dict(order_line_id='L1', order_id='O1', sku_id='S1', quantity=1, unit_price=60., discount_amount=6., net_revenue=54.),
                               dict(order_line_id='L2', order_id='O1', sku_id='S2', quantity=1, unit_price=40., discount_amount=4., net_revenue=36.)]),
        'inventory': pd.DataFrame([dict(sku_id='S1', snapshot_date='2026-01-01', opening_stock=10, inbound_units=3, sold_units=2, restockable_return_units=1, closing_stock=12, locked_stock=2, available_stock=10),
                                   dict(sku_id='S1', snapshot_date='2026-01-02', opening_stock=12, inbound_units=0, sold_units=1, restockable_return_units=0, closing_stock=11, locked_stock=2, available_stock=9)]),
        'purchases': pd.DataFrame([dict(po_id='P1', sku_id='S1', order_date='2026-01-01', expected_date='2026-01-02', received_date='', quantity_ordered=5, quantity_received=0, unit_purchase_cost=10., purchase_amount=50., purchase_status='open')]),
        'aftersales': pd.DataFrame([dict(case_id='A1', order_id='O1', sku_id='S1', units=1, refund_amount=54., case_status='closed'),
                                    dict(case_id='A2', order_id='O1', sku_id='S2', units=1, refund_amount=36., case_status='closed')]),
    }


def codes(report):
    return {item['rule_code'] for item in report['issues']}


def test_clean_fixture_and_order_grain_refunds(tables):
    report = build_erp_checks(tables)
    assert report['summary']['error_count'] == report['summary']['warning_count'] == 0
    assert report['as_of'] == '2026-01-02'
    assert report['issues'] == []  # 90 refund vs 95 paid, not a multiplied many-to-many sum.


@pytest.mark.parametrize('value', [np.nan, np.inf, -1, 'bad'])
def test_missing_invalid_header_amount_never_passes(tables, value):
    tables['headers']['paid_amount'] = value
    checked = reconcile_orders(tables['headers'], tables['lines'])
    assert not checked['passed'].any()
    report = build_erp_checks(tables)
    assert {'headers_numbers','order_reconciliation'} <= codes(report)


@pytest.mark.parametrize('field,value', [('quantity',None), ('quantity',1.5), ('unit_price','bad'), ('discount_amount',np.inf)])
def test_invalid_line_not_hidden_by_group_sum(tables, field, value):
    tables['lines'][field] = tables['lines'][field].astype(object)
    tables['lines'].at[0,field] = value
    assert not reconcile_orders(tables['headers'], tables['lines'])['passed'].any()


def test_inventory_balance_and_return_semantics(tables):
    assert 'inventory_balance' not in codes(build_erp_checks(tables))
    tables['inventory'].at[0,'closing_stock'] = 14
    result = codes(build_erp_checks(tables))
    assert {'inventory_balance','inventory_available','inventory_continuity'} <= result


def test_inventory_gaps_not_counted_as_successful_continuity(tables):
    tables['inventory'].at[1,'snapshot_date'] = '2026-01-04'
    report = build_erp_checks(tables)
    assert 'inventory_gaps' in codes(report)
    rule = next(rule for rule in report['rules'] if rule['code']=='inventory_continuity')
    assert rule['checked_count'] == 0 and rule['state'] == '无可核对数据'


def test_purchase_overdue_uses_snapshot_not_today(tables):
    assert 'purchase_overdue' not in codes(build_erp_checks(tables))
    tables['purchases'].at[0,'expected_date'] = '2026-01-01'
    report = build_erp_checks(tables)
    overdue = next(item for item in report['issues'] if item['rule_code']=='purchase_overdue')
    assert overdue['severity'] == 'warning'
    tables['purchases'].at[0,'quantity_received'] = 6
    assert 'purchase_quantity' in codes(build_erp_checks(tables))


def test_missing_snapshot_date_cannot_pass_overdue_rule(tables):
    tables['inventory']['snapshot_date'] = 'bad'
    report = build_erp_checks(tables)
    assert report['as_of'] is None
    rule = next(rule for rule in report['rules'] if rule['code']=='purchase_overdue')
    assert rule['state'] == '无可核对数据'


def test_aftersales_requires_matching_order_sku_pair(tables):
    tables['sku'] = pd.concat([tables['sku'],pd.DataFrame([{'sku_id':'S3'}])],ignore_index=True)
    tables['aftersales'].at[0,'sku_id']='S3'
    result = codes(build_erp_checks(tables))
    assert 'aftersales_pair' in result and 'aftersales_sku' not in result


def test_refund_cap_uses_closed_cases_only(tables):
    tables['aftersales'].at[0,'refund_amount'] = 100
    assert 'refund_cap' in codes(build_erp_checks(tables))
    tables['aftersales'].at[0,'case_status'] = 'open'
    assert 'refund_cap' not in codes(build_erp_checks(tables))


def test_duplicate_inventory_composite_key_and_source_row(tables):
    tables['inventory'] = pd.concat([tables['inventory'],tables['inventory'].head(1)],ignore_index=True)
    issues = [item for item in build_erp_checks(tables)['issues'] if item['rule_code']=='inventory_identity']
    assert {item['source_row'] for item in issues} == {2,4}
    assert len({item['issue_id'] for item in issues}) == 2


def test_demo_isolated_and_reproducible(tables):
    before = {key: frame.copy(deep=True) for key,frame in tables.items()}
    demo = build_erp_checks(tables,'demo')
    assert len(demo['injections']) == 4
    assert {'order_reconciliation','inventory_balance','purchase_quantity','aftersales_order'} <= codes(demo)
    assert demo['issues'] == build_erp_checks(tables,'demo')['issues']
    for key,frame in tables.items():
        pd.testing.assert_frame_equal(frame,before[key])
    assert not build_erp_checks(tables)['issues']


def test_missing_columns_and_empty_tables(tables):
    empty = {key:frame.iloc[0:0] for key,frame in tables.items()}
    report = build_erp_checks(empty)
    assert report['as_of'] is None
    assert all(rule['state']=='无可核对数据' for rule in report['rules'])
    tables['inventory'] = tables['inventory'].drop(columns='opening_stock')
    with pytest.raises(ValueError, match='opening_stock'):
        build_erp_checks(tables)


def test_api_pagination_and_export_same_scope(tmp_path):
    with TestClient(create_app(ROOT,tmp_path/'state.db')) as client:
        query = {'scenario':'demo','severity':'error','limit':1}
        result = client.get('/api/erp/checks',params=query).json()
        assert len(result['items']) == 1 and result['issue_total'] >= 4
        assert result['summary']['error_count'] == result['issue_total']
        csv = client.get('/api/erp/checks',params=query|{'download':'true'})
        rows = pd.read_csv(io.BytesIO(csv.content))
        assert len(rows) == result['issue_total']
        assert rows['数据范围'].str.contains('演练').all()
        assert set(rows['级别']) == {'error'}
        assert client.get('/api/erp/checks?scenario=invalid').status_code == 422
        assert client.get('/api/erp/checks?page=0').status_code == 422


def test_real_snapshot_no_mutation():
    tables = {key:pd.read_csv(ROOT/'data/processed'/f'{meta[0]}.csv') for key,meta in TABLES.items()}
    report = build_erp_checks(tables)
    assert report['source_counts']['erp_inventory_daily'] == 18900
    assert report['as_of'] == '2026-08-29'
