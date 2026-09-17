from pathlib import Path
import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from arknights_merch_analytics.gmv import (Scenario, build_gmv_report, calculate_scenario,
    compare_scenario, decompose_periods, observed_order_analysis)
from arknights_merch_analytics.platform_api import create_app

ROOT=Path(__file__).resolve().parents[1]
BASE=json.loads((ROOT/'config/gmv_scenarios.json').read_text(encoding='utf-8'))['baseline']


def test_buyer_identity_and_contribution_ledger():
    parameters={**BASE,'purchase_frequency':2,'discount_rate':.1,'gift_per_order':3}
    r=calculate_scenario(parameters)
    assert r['expected_paid_orders']==600
    assert r['paid_merchandise_gmv']==64800
    assert r['contribution_profit']==pytest.approx(r['paid_merchandise_gmv']-r['expected_refund']-
        r['platform_fees']-r['total_variable_cost']-parameters['marketing_spend'])


def test_discount_can_raise_gmv_while_lowering_contribution():
    r=compare_scenario(BASE,{**BASE,'visitors':14000,'discount_rate':.2})
    assert r['gmv_up_profit_down'] is True
    assert r['gmv_change']>0 and r['contribution_change']<0


def test_capacity_limits_demand_and_breakeven():
    r=calculate_scenario({**BASE,'order_capacity':10})
    assert r['potential_orders']==300 and r['expected_paid_orders']==10
    assert r['breakeven_feasible'] is False
    assert r['contribution_profit']<0


@pytest.mark.parametrize('overrides',[
    {'buyer_conversion':1.01},{'buyer_conversion':-.01},{'purchase_frequency':.5},
    {'discount_rate':1.1},{'visitors':-1},{'visitors':1.5},{'cogs_per_order':float('nan')},
    {'marketing_spend':float('inf')},{'order_capacity':-1}])
def test_invalid_assumptions_are_rejected(overrides):
    with pytest.raises(ValidationError):
        calculate_scenario({**BASE,**overrides})


@pytest.mark.parametrize('overrides',[{'visitors':0},{'buyer_conversion':0},{'order_capacity':0}])
def test_zero_demand_still_bears_marketing_cost(overrides):
    r=calculate_scenario({**BASE,**overrides})
    assert r['paid_merchandise_gmv']==0
    assert r['contribution_profit']==-BASE['marketing_spend']


def test_negative_unit_margin_has_no_finite_break_even():
    r=calculate_scenario({**BASE,'cogs_per_order':200})
    assert r['unit_contribution']<0 and r['breakeven_orders'] is None
    assert r['breakeven_buyer_conversion'] is None


def period(values):
    return pd.DataFrame([{'payment_status':'paid','merchandise_paid':v,'units':1,
                         'shipping_fee':0,'paid_amount':v,'discount_amount':0} for v in values],
                        columns=['payment_status','merchandise_paid','units','shipping_fee','paid_amount','discount_amount'])


def test_two_factor_decomposition_reconciles_without_order_dependence():
    r=decompose_periods(period([10,20]),period([20,30,40]))
    assert r['gmv_change']==60
    assert r['order_count_contribution']==22.5
    assert r['aov_contribution']==37.5
    assert r['reconciled'] is True
    reverse=decompose_periods(period([20,30,40]),period([10,20]))
    assert reverse['order_count_contribution']==-r['order_count_contribution']


def test_zero_order_period_leaves_aov_undefined():
    r=decompose_periods(period([]),period([20,30]))
    assert r['before']['paid_aov'] is None
    assert r['gmv_change']==50 and r['reconciled'] is None


@pytest.fixture(scope='module')
def report():
    return build_gmv_report(ROOT)


def test_real_snapshot_is_explicitly_simulated_and_missing_metrics_stay_null(report):
    o=report['observed'];s=o['summary']
    assert o['is_simulated'] is True
    assert s['order_count']==6000 and s['paid_orders']==5793
    assert s['paid_merchandise_gmv']==1268567.9
    assert s['paid_merchandise_gmv']+s['shipping_collected']==pytest.approx(s['paid_cash_including_shipping'])
    assert sum(r['paid_merchandise_gmv'] for r in o['channels'])==pytest.approx(s['paid_merchandise_gmv'])
    assert s['purchase_frequency'] is None and s['visitor_conversion'] is None and s['repeat_purchase_rate'] is None
    assert o['refund_audit']['orders_exceeding_cash']==44
    assert o['refund_audit']['net_sales_after_refund'] is None
    assert len(report['strategies'])==4 and len(report['sensitivity'])==12
    assert report['risk_examples'] and all(r['gmv_change']>0 and r['contribution_change']<0 for r in report['risk_examples'])
    assert all(r['is_hypothetical'] for r in report['strategies'])
    json.dumps(report,allow_nan=False)


def test_broken_order_contract_rejects_double_counting():
    h=pd.read_csv(ROOT/'data/processed/erp_order_headers.csv')
    lines=pd.read_csv(ROOT/'data/processed/erp_order_lines.csv')
    after=pd.read_csv(ROOT/'data/processed/erp_after_sales.csv')
    with pytest.raises(ValueError,match='订单核对'):
        observed_order_analysis(pd.concat([h,h.iloc[:1]]),lines,after)
    lines.loc[0,'net_revenue']=float('nan')
    with pytest.raises(ValueError,match='明细净额'):
        observed_order_analysis(h,lines,after)


def test_api_scenarios_are_stateless_and_bad_values_fail(tmp_path):
    with TestClient(create_app(ROOT,tmp_path/'state.db')) as client:
        before=client.get('/api/gmv-drivers').json()
        r=client.post('/api/gmv-drivers/scenario',json={'base':BASE,'candidate':{**BASE,'order_capacity':1}})
        assert r.status_code==200 and r.json()['expected_paid_orders']==1
        assert client.get('/api/gmv-drivers').json()==before
        assert client.post('/api/gmv-drivers/scenario',json={'base':BASE,'candidate':{**BASE,'discount_rate':1.01}}).status_code==422
        export=client.get('/api/gmv-drivers?download=markdown')
        assert export.status_code==200 and '全部为假设' in export.text
