import json,sqlite3
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from arknights_merch_analytics.public_data_api import register_public_data


@pytest.fixture
def client(tmp_path):
    folder=tmp_path/'reports/generated/public_expansion/2026-09-12'
    folder.mkdir(parents=True)
    with sqlite3.connect(folder/'public_expansion.db') as con:
        pd.DataFrame([{'title':'Amiya','price':18},{'title':'=HYPERLINK("bad")','price':9}]).to_sql('official_store_products',con,index=False)
    (folder/'summary.json').write_text(json.dumps({'run_date':'2026-09-12','tables':{'official_store_products':{'rows':2}}}),encoding='utf-8')
    app=FastAPI();register_public_data(app,tmp_path)
    return TestClient(app)


def test_public_data_summary_and_filtered_pagination(client):
    assert client.get('/api/public-expansion').json()['included_in_original_rankings'] is False
    body=client.get('/api/public-expansion/data/official_store_products',params={'q':'amiya','limit':1}).json()
    assert body['total']==1 and body['items'][0]['price']==18


def test_export_uses_same_filter_and_escapes_formula_text(client):
    result=client.get('/api/public-expansion/export/official_store_products',params={'q':'HYPERLINK'})
    assert result.status_code==200 and "'=HYPERLINK" in result.text and 'Amiya' not in result.text
    assert client.get('/api/public-expansion/data/official_store_products').json()['items'][1]['title'].startswith('=')


def test_unknown_table_and_invalid_page_rejected(client):
    assert client.get('/api/public-expansion/data/sqlite_master').status_code==404
    assert client.get('/api/public-expansion/data/official_store_products?limit=-1').status_code==422


def test_missing_batch_is_explicit(tmp_path):
    app=FastAPI();register_public_data(app,tmp_path)
    assert TestClient(app).get('/api/public-expansion').status_code==503
