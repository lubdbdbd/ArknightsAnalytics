from copy import deepcopy
from pathlib import Path
import json
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from arknights_merch_analytics.channel_strategy import (
    build_channel_strategy, observed_channel_matrix, review_price_gaps, sku_fit, validate_policy)
from arknights_merch_analytics.platform_api import create_app

ROOT=Path(__file__).resolve().parents[1]
POLICY=json.loads((ROOT/'config/channel_strategy.json').read_text(encoding='utf-8'))

@pytest.fixture(scope='module')
def report():
    return build_channel_strategy(ROOT)

def test_cardinality_and_independent_gmv_reconciliation(report):
    assert len(report['matrix'])==1470
    assert len(report['category_matrix'])==49
    assert len({(r['sku_id'],r['channel']) for r in report['matrix']})==1470
    assert report['observed']['paid_orders']==5793
    assert report['observed']['paid_merchandise_gmv']==pytest.approx(1268567.9)
    assert sum(r['merchandise_gmv'] for r in report['observed']['summary'])==pytest.approx(1268567.9)
    json.dumps(report,allow_nan=False)

def test_missing_channel_observations_are_not_zero(report):
    prospective=[r for r in report['matrix'] if r['channel_status']=='规划待验证']
    assert len(prospective)==420
    assert all(r['observed_paid_orders'] is None and r['observed_gmv'] is None for r in prospective)
    assert set(r['channel'] for r in report['matrix']).isdisjoint({'二手平台','其他'})

def test_zero_in_observed_window_is_explicit():
    headers=pd.read_csv(ROOT/'data/processed/erp_order_headers.csv')
    lines=pd.read_csv(ROOT/'data/processed/erp_order_lines.csv')
    skus=pd.read_csv(ROOT/'data/processed/erp_sku_master.csv')
    extra=skus.iloc[[0]].copy()
    extra['sku_id']='unused';extra['sku_code']='unused'
    result=observed_channel_matrix(headers,lines,pd.concat([skus,extra],ignore_index=True))
    unused=[r for r in result['sku_channel'] if r['sku_id']=='unused']
    assert len(unused)==7 and all(r['paid_orders']==0 for r in unused)
    assert all(r['average_paid_unit_price'] is None for r in unused)

def test_margin_guard_precedes_fit_score():
    sku=pd.read_csv(ROOT/'data/processed/erp_sku_master.csv').iloc[0].to_dict()
    sku['unit_cost']=sku['price']*2
    r=sku_fit(sku,POLICY['profiles'][0],POLICY)
    assert r['unit_margin']<0 and r['decision']=='成本待复核'
    sku['sku_status']='inactive'
    assert sku_fit(sku,POLICY['profiles'][0],POLICY)['decision']=='状态待核验'

def test_price_review_is_same_sku_retail_only():
    row={'sku_id':'A','operator':'角色','category':'徽章','channel':'商城',
         'proposed_price':100,'decision':'优先评审','price_basis':'retail'}
    rows=[row,{**row,'channel':'平台'}, {**row,'channel':'代理','price_basis':'wholesale','proposed_price':50},
          {**row,'channel':'别的SKU','sku_id':'B','proposed_price':50}]
    assert review_price_gaps(rows,.1)==[]
    rows.append({**row,'channel':'促销渠道','proposed_price':90})
    assert len(review_price_gaps(rows,.1))==2
    rows[-1]['decision']='成本待复核'
    assert review_price_gaps(rows,.1)==[]

@pytest.mark.parametrize('mode',['duplicate_sku','unknown_sku','duplicate_order','wrong_net','missing_channel'])
def test_bad_source_data_rejected(mode):
    headers=pd.read_csv(ROOT/'data/processed/erp_order_headers.csv')
    lines=pd.read_csv(ROOT/'data/processed/erp_order_lines.csv')
    skus=pd.read_csv(ROOT/'data/processed/erp_sku_master.csv')
    if mode=='duplicate_sku': skus=pd.concat([skus,skus.iloc[[0]]],ignore_index=True)
    if mode=='unknown_sku': lines.loc[0,'sku_id']='unknown'
    if mode=='duplicate_order': headers=pd.concat([headers,headers.iloc[[0]]],ignore_index=True)
    if mode=='wrong_net': lines.loc[0,'net_revenue']+=1
    if mode=='missing_channel': headers.loc[0,'channel']=None
    with pytest.raises(ValueError):
        observed_channel_matrix(headers,lines,skus)

@pytest.mark.parametrize('field',['price_min','price_max','preferred_replenishment_days'])
def test_nonfinite_policy_rejected(field):
    policy=deepcopy(POLICY);policy['profiles'][0][field]=float('inf')
    with pytest.raises(ValueError): validate_policy(policy,{'亚克力制品'})

def test_api_and_exports_use_same_report(tmp_path,report):
    with TestClient(create_app(ROOT,tmp_path/'state.db')) as client:
        response=client.get('/api/channel-strategy')
        assert response.status_code==200
        assert response.json()['summary']==report['summary']
        export=client.get('/api/channel-strategy?download=json')
        assert export.json()['manifest']==report['manifest']
        markdown=client.get('/api/channel-strategy?download=markdown')
        assert '众筹及零售代理为待验证规划' in markdown.text
        assert 'attachment' in markdown.headers['content-disposition']
        assert client.get('/api/channel-strategy?download=bad').status_code==422
