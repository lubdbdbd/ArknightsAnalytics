from copy import deepcopy
from pathlib import Path
import json
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from arknights_merch_analytics.business_decisions import (
 build_business_decisions,inventory_decisions,validate_inventory,scenario_economics)
from arknights_merch_analytics.platform_api import create_app

ROOT=Path(__file__).resolve().parents[1]
POLICY=json.loads((ROOT/'config/business_decisions.json').read_text(encoding='utf-8'))

@pytest.fixture(scope='module')
def report():
    return build_business_decisions(ROOT)

def test_reconciled_inventory_not_order_quantity(report):
    s=report['summary']
    assert s['inventory_snapshots']==18900 and s['days']==90
    assert s['outbound_units']==8227 and s['ending_units']==4914
    assert s['period_sell_through']==pytest.approx(8227/(8227+4914))
    assert report['quality']['paid_order_units']==8368
    assert s['inventory_turnover_days']==pytest.approx(82.6034,abs=.0001)
    assert report['ltv']['value'] is None
    json.dumps(report,allow_nan=False)

def fixture_data(sold,ending,available=None):
    inv=pd.DataFrame([{'sku_id':'A','snapshot_date':pd.Timestamp('2026-01-01'),
        'sold_units':sold,'opening_stock':sold+ending,'closing_stock':ending,
        'available_stock':ending if available is None else available,'inbound_units':0,
        'restockable_return_units':0,'stockout_units':0,'requested_sales_units':sold}])
    skus=pd.DataFrame([{'sku_id':'A','operator':'A','category':'徽章','unit_cost':2,'price':10,'purchase_lead_time_days':7}])
    return inv,skus

def test_no_sales_is_unknown_turnover_not_zero_days():
    inv,skus=fixture_data(0,100)
    rows,summary=inventory_decisions(inv,skus,POLICY)
    assert rows[0]['inventory_turnover_days'] is None
    assert rows[0]['available_cover_days'] is None
    assert '近期无出库' in rows[0]['flags']
    assert summary['slow_stock_cost']==200
    assert summary['period_sell_through']==0

def test_turnover_and_cover_use_different_denominators():
    inv,skus=fixture_data(10,100,20)
    r=inventory_decisions(inv,skus,POLICY)[0][0]
    assert r['inventory_turnover_days']==10
    assert r['available_cover_days']==2
    assert '覆盖不足' in r['flags']

def test_slow_rule_and_no_forced_slow_results(report):
    inv,skus=fixture_data(1,1000)
    r=inventory_decisions(inv,skus,POLICY)[0][0]
    assert '去化缓慢' in r['flags']
    assert report['summary']['slow_skus']==0

def test_stockout_does_not_imply_unbounded_demand():
    inv,skus=fixture_data(1,0)
    inv.loc[0,['requested_sales_units','stockout_units']]=[5,4]
    r=inventory_decisions(inv,skus,POLICY)[0][0]
    assert r['unmet_rate']==.8 and '供给受限' in r['flags']
    assert '供给' in r['suggested_action']

@pytest.mark.parametrize('defect',['duplicate','missing_day','balance','continuity','negative','nan','purchase','request'])
def test_ledger_corruption_fails_closed(defect):
    frames=[pd.read_csv(ROOT/f'data/processed/{name}.csv') for name in [
        'erp_inventory_daily','erp_sku_master','erp_order_headers','erp_order_lines','erp_purchase_orders']]
    inv,skus,headers,lines,po=frames
    if defect=='duplicate':inv=pd.concat([inv,inv.iloc[[0]]])
    if defect=='missing_day':inv=inv.iloc[1:]
    if defect=='balance':inv.loc[0,'closing_stock']+=1
    if defect=='continuity':
        inv.loc[1,['opening_stock','closing_stock','available_stock']]+=1
    if defect=='negative':inv.loc[0,'available_stock']=-1
    if defect=='nan':inv.loc[0,'closing_stock']=float('nan')
    if defect=='purchase':po.loc[0,'quantity_received']-=1
    if defect=='request':
        inv.loc[0,['requested_sales_units','stockout_units']]+=1
    with pytest.raises(ValueError):
        validate_inventory(inv,skus,headers,lines,po)

def test_roi_cost_denominator_and_zero_spend():
    base=json.loads((ROOT/'config/gmv_scenarios.json').read_text(encoding='utf-8'))['baseline']
    r=scenario_economics(base)
    assert r['modeled_total_cost']==22480
    assert r['modeled_roi']==pytest.approx(11720/22480)
    assert r['scenario_revenue_to_ad_spend']==36
    zero={**base,'cogs_per_order':0,'fulfillment_per_order':0,'platform_fee_rate':0,'marketing_spend':0}
    r=scenario_economics(zero)
    assert r['modeled_roi'] is None and r['scenario_revenue_to_ad_spend'] is None

def test_api_report_exports(tmp_path,report):
    with TestClient(create_app(ROOT,tmp_path/'state.db')) as client:
        r=client.get('/api/business-decisions')
        assert r.status_code==200 and r.json()['summary']==report['summary']
        assert client.get('/api/business-decisions?download=json').json()['ltv']['value'] is None
        assert '不是节省金额' in client.get('/api/business-decisions?download=markdown').text
        assert client.get('/api/business-decisions?download=invalid').status_code==422
