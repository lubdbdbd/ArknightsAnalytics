from pathlib import Path
import io

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from arknights_merch_analytics.platform_api import ROOT, create_app, reconcile_orders


@pytest.fixture
def client(tmp_path: Path):
    with TestClient(create_app(ROOT, tmp_path / "state.db")) as instance:
        yield instance


def first_product(client, domain="internal"):
    response = client.get(f"/api/catalog/{domain}?limit=1")
    assert response.status_code == 200
    return response.json()["items"][0]


def test_overview_and_real_survey_boundary(client):
    data = client.get("/api/overview").json()
    assert data["sku_count"] == 210
    assert data["order_count"] == 6000
    assert data["survey"]["response_count"] == 243
    assert client.get("/api/data/orders").json()["is_simulated"] is True
    assert client.get("/api/data/survey_profile").json()["is_simulated"] is False


@pytest.mark.parametrize("dataset", ["inventory", "replenishment", "reasons", "survey_categories", "survey_prices", "demand", "evidence"])
def test_business_datasets_and_pagination(client, dataset):
    response = client.get(f"/api/data/{dataset}?limit=2")
    assert response.status_code == 200
    assert len(response.json()["items"]) <= 2
    assert response.json()["total"] >= len(response.json()["items"])


def test_edit_persists_and_writes_audit(client):
    product = first_product(client)
    url = f'/api/catalog/internal/{product["entity_id"]}'
    changes = {"product_name": product["product_name"] + " 测试维护"}
    response = client.patch(url, json={"version": 0, "changes": changes, "reason": "核对名称修订"})
    assert response.status_code == 200
    reread = client.get("/api/catalog/internal", params={"q": "测试维护"}).json()["items"]
    assert reread[0]["product_name"] == changes["product_name"]
    assert reread[0]["version"] == 1
    audit = client.get("/api/audit", params={"entity_id": product["entity_id"]}).json()["items"]
    assert len(audit) == 1
    assert audit[0]["reason"] == "核对名称修订"
    assert client.patch(url, json={"version": 0, "changes": changes, "reason": "旧版本覆盖"}).status_code == 409
    assert len(client.get("/api/audit").json()["items"]) == 1


@pytest.mark.parametrize("changes", [
    {"price": -1}, {"price": 0}, {"unit_cost": 1000000}, {"supplier_id": ""},
    {"safety_stock": 1000000}, {"reorder_point": -1},
    {"sku_status": "invalid"}, {"is_simulated": False}, {"price": "NaN"},
])
def test_invalid_edit_rejected_without_side_effects(client, changes):
    product = first_product(client)
    response = client.patch(f'/api/catalog/internal/{product["entity_id"]}',
                            json={"version": 0, "changes": changes, "reason": "异常规则验证"})
    assert response.status_code == 422
    assert client.get("/api/audit").json()["items"] == []


def test_public_authorization_requires_evidence_and_preserves_source(client):
    product = first_product(client, "public")
    url = f'/api/catalog/public/{product["entity_id"]}'
    payload = {"version": 0, "changes": {"verification_status": "verified"}, "reason": "授权核对"}
    assert client.patch(url, json=payload).status_code == 422
    payload["changes"]["evidence_url"] = "https://example.com/evidence"
    assert client.patch(url, json=payload).status_code == 200
    updated = client.get("/api/catalog/public", params={"q": product["entity_id"]}).json()["items"][0]
    assert updated["verification_status"] == "verified"
    assert updated["rights_type"] == product["rights_type"]


def test_public_edit_updates_effective_catalog(client):
    product = first_product(client, "public")
    response = client.patch(f'/api/catalog/public/{product["entity_id"]}', json={
        "version": 0, "changes": {"operator": "能天使", "list_price": 88, "fulfillment_type": "现货/在售"},
        "reason": "复核商品页面信息",
    })
    assert response.status_code == 200
    updated = client.get("/api/catalog/public", params={"q": product["entity_id"]}).json()["items"][0]
    assert updated["operator"] == "能天使"
    assert updated["list_price"] == 88


def test_import_preview_reports_invalid_rows_and_does_not_write(client):
    product = first_product(client)
    data = product["sku_code"]
    response = client.post("/api/import/preview", json={"csv_text": f"sku_code,price\n{data},99\nUNKNOWN,-1\n{data},99"})
    assert response.status_code == 200
    result = response.json()
    assert result["total"] == 3
    assert result["valid_count"] == 1
    assert client.get("/api/audit").json()["items"] == []


def test_order_detail_matches_only_requested_order(client):
    order = client.get("/api/data/orders?limit=1").json()["items"][0]
    lines = client.get("/api/data/order_lines", params={"order_id": order["order_id"]}).json()["items"]
    assert lines
    assert {row["order_id"] for row in lines} == {order["order_id"]}


def test_export_whitelist_and_csv_content(client):
    response = client.get("/api/export/internal")
    assert response.status_code == 200
    assert response.content.startswith(b"\xef\xbb\xbf")
    assert "sku_code" in response.text
    assert client.get("/api/export/raw_survey").status_code == 404
    assert client.get("/api/data/raw_survey").status_code == 404


def test_cross_origin_mutation_blocked(client):
    product = first_product(client)
    response = client.patch(f'/api/catalog/internal/{product["entity_id"]}', headers={"Origin": "https://external.example"},
                            json={"version": 0, "changes": {"price": 99}, "reason": "跨域修改"})
    assert response.status_code == 403


def test_health_and_actual_metrics(client):
    assert client.get("/api/health").json()["status"] == "ok"
    metrics = client.get("/metrics").text
    assert "ark_http_requests_total" in metrics
    assert "ark_http_duration_seconds" in metrics


def test_operations_brief_and_download_use_actual_snapshot(client):
    response = client.get('/api/operations/brief')
    assert response.status_code == 200
    brief = response.json()
    assert len(brief['tasks']) == 3
    assert brief['live_channel']['order_count'] == 153
    assert brief['live_channel']['paid_order_count'] == 144
    export = client.get('/api/operations/brief?download=true')
    assert export.status_code == 200
    assert 'attachment' in export.headers['content-disposition']
    assert '模拟ERP' in export.text
    assert '不能认定为抖音' in export.text
    assert client.get('/api/audit').json()['items'] == []


def test_filtered_orders_export_and_reconciliation_agree(client):
    sample = client.get('/api/data/orders?limit=1').json()['items'][0]
    filters = {'channel': sample['channel'], 'start_date': sample['order_date'], 'end_date': sample['order_date']}
    listed = client.get('/api/data/orders', params=filters | {'limit': 1000}).json()
    exported = pd.read_csv(io.BytesIO(client.get('/api/export/orders', params=filters).content))
    check = client.get('/api/erp/reconciliation', params=filters).json()
    assert listed['total'] > 0
    assert len(exported) == listed['total'] == check['checked_count']
    assert check['issue_count'] == 0
    assert check['paid_total'] == round(exported['paid_amount'].sum(), 2)
    assert set(exported['order_date']) == {sample['order_date']}
    assert set(exported['channel']) == {sample['channel']}


@pytest.mark.parametrize('endpoint', ['/api/data/orders', '/api/export/orders', '/api/erp/reconciliation'])
def test_invalid_date_range_rejected(client, endpoint):
    assert client.get(endpoint, params={'start_date': '2026-08-01', 'end_date': '2026-06-01'}).status_code == 422
    assert client.get(endpoint, params={'start_date': 'invalid'}).status_code == 422


def test_catalog_filtered_export(client):
    product = first_product(client)
    exported = pd.read_csv(io.BytesIO(client.get('/api/export/internal', params={'q': product['sku_code']}).content))
    assert exported['sku_code'].tolist() == [product['sku_code']]


def test_reconciliation_detects_injected_amount_and_missing_line_defects():
    headers = pd.read_csv(ROOT / 'data/processed/erp_order_headers.csv').head(3).copy()
    lines = pd.read_csv(ROOT / 'data/processed/erp_order_lines.csv')
    headers.loc[headers.index[0], 'paid_amount'] += 10
    headers.loc[headers.index[1], 'order_amount'] += 5
    lines = lines[lines['order_id'] != headers.iloc[2]['order_id']]
    checked = reconcile_orders(headers, lines)
    assert checked['passed'].tolist() == [False, False, False]
    assert checked.iloc[0]['paid_difference'] == 10
    assert checked.iloc[1]['gross_difference'] == 5
    assert bool(checked.iloc[2]['missing_lines'])


def test_reconciliation_detects_duplicates_and_invalid_status():
    headers = pd.read_csv(ROOT / 'data/processed/erp_order_headers.csv').head(2).copy()
    lines = pd.read_csv(ROOT / 'data/processed/erp_order_lines.csv')
    selected = lines[lines['order_id'] == headers.iloc[0]['order_id']].head(1)
    lines = pd.concat([lines, selected])
    headers.loc[headers.index[1], 'payment_status'] = 'unknown'
    checked = reconcile_orders(headers, lines)
    assert not checked['passed'].any()
    assert bool(checked.iloc[0]['duplicate_lines'])
    assert bool(checked.iloc[1]['invalid_payment_status'])


def test_empty_reconciliation_scope(client):
    check = client.get('/api/erp/reconciliation', params={'q': 'NONEXISTENT-ORDER'}).json()
    assert check['checked_count'] == check['issue_count'] == 0
    assert check['issues'] == []


@pytest.mark.parametrize('csv_text', ['sku_code,price,price\nAK-0001,99,99', 'sku_code,price\nAK-0001,99,EXTRA', 'sku_code,price\nAK-0001'])
def test_malformed_import_has_no_writes(client, csv_text):
    response = client.post('/api/import/preview', json={'csv_text': csv_text})
    assert response.status_code == 422 or response.json()['valid_count'] == 0
    assert client.get('/api/audit').json()['items'] == []
