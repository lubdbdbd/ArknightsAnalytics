from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from arknights_merch_analytics.product_catalog import (
    build_internal_product_master,
    build_product_category_health,
    build_product_change_log,
    build_product_field_dictionary,
    build_product_maintenance_queue,
    build_public_listing_master,
    export_product_catalog,
    write_product_catalog_report,
)


ROOT = Path(__file__).resolve().parents[1]


def _internal() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "sku_code": "AK-0001",
                "sku_id": "能天使-亚克力制品",
                "operator": "能天使",
                "category": "亚克力制品",
                "price": 48,
                "unit_cost": 16.8,
                "production_risk": 0.24,
                "launch_inventory": 100,
                "sold_units": 50,
                "product_name": "能天使 亚克力制品",
                "supplier_id": "SUP-01",
                "purchase_lead_time_days": 18,
                "average_daily_demand_plan": 1.2,
                "safety_stock": 8,
                "reorder_point": 20,
                "initial_stock": 30,
                "sku_status": "active",
                "is_simulated": True,
                "simulation_seed": 1,
            }
        ]
    )


def _public() -> pd.DataFrame:
    base = {
        "snapshot_at": "2026-09-02T11:55:00+08:00",
        "query": "明日方舟 周边",
        "query_scope": "market_baseline",
        "target_operator": "",
        "sort": "销量",
        "collection_method": "public_snapshot",
        "url": "https://item.taobao.com/item.htm?id=1",
        "rank": 1,
        "raw_text": "明日方舟 能天使 亚克力 官方正版 48元 现货",
        "price": 48,
        "sales_proxy_min": 100,
        "sales_proxy_censored": True,
        "category": "亚克力制品",
        "rights_type": "官方/授权",
        "fulfillment_type": "现货/在售",
        "free_shipping": True,
        "return_insurance": True,
        "fast_dispatch": True,
        "operator_mentions": "能天使",
        "operator_mention_count": 1,
        "target_relevance": 1.0,
        "ip_scope": "arknights",
        "source_file": "fixture.json",
        "is_simulated": False,
        "rank_weight": 1.0,
        "numeric_sales_available": True,
    }
    rows = []
    for index, price in enumerate([48, 49, 50, 500], 1):
        row = dict(base)
        row["item_id"] = str(index)
        row["url"] = f"https://item.taobao.com/item.htm?id={index}"
        row["price"] = price
        if index == 2:
            row["rights_type"] = "未标明"
            row["operator_mentions"] = ""
        rows.append(row)
    duplicate = dict(rows[0])
    duplicate["query"] = "明日方舟 能天使 周边"
    rows.append(duplicate)
    return pd.DataFrame(rows)


def test_internal_master_builds_spu_and_passes_rules() -> None:
    master = build_internal_product_master(_internal())
    assert master.loc[0, "spu_code"].startswith("SPU-")
    assert master.loc[0, "required_field_completeness"] == 1
    assert master.loc[0, "data_quality_grade"] == "A"
    assert master.loc[0, "maintenance_status"] == "已校验"


def test_internal_master_detects_price_and_supplier_errors() -> None:
    source = _internal()
    source.loc[0, "unit_cost"] = 60
    source.loc[0, "supplier_id"] = ""
    master = build_internal_product_master(source)
    assert master.loc[0, "invalid_cost"]
    assert master.loc[0, "missing_supplier"]
    assert master.loc[0, "maintenance_status"] == "待处理"


def test_public_listing_master_deduplicates_and_builds_queue() -> None:
    master = build_public_listing_master(_public())
    queue = build_product_maintenance_queue(master)
    assert len(master) == 4
    assert master.loc[master["item_id"].eq("1"), "capture_count"].iloc[0] == 2
    assert master["price_outlier"].sum() == 1
    assert queue["maintenance_priority"].eq("P1-待核验").all()
    assert queue["maintenance_action"].str.contains("核验|归因|价格|重复").all()


@pytest.mark.parametrize('identifier', [None, '', '   ', 'nan'])
def test_missing_identifier_cannot_be_merged(identifier):
    source = _public()
    source.loc[0, 'item_id'] = identifier
    with pytest.raises(ValueError, match='禁止'):
        build_public_listing_master(source)


def test_multi_role_listing_requires_review_and_preserves_source():
    source = _public()
    source.loc[1, 'operator_mentions'] = '能天使|德克萨斯'
    original = source.copy(deep=True)
    output = build_public_listing_master(source)
    assert output.loc[output['item_id'].eq('2'), 'identity_review_required'].iloc[0]
    pd.testing.assert_frame_equal(source, original)


def test_same_capture_conflicting_prices_are_not_silently_trusted():
    source = _public()
    source.loc[source.index[-1], 'price'] = 99
    output = build_public_listing_master(source)
    item = output.loc[output['item_id'].eq('1')].iloc[0]
    assert item['identity_review_required']
    assert item['maintenance_priority'] == 'P1-待核验'


def test_category_health_and_change_log_keep_data_boundaries() -> None:
    internal = build_internal_product_master(_internal())
    public = build_public_listing_master(_public())
    health = build_product_category_health(internal, public)
    changes = build_product_change_log(internal, public, "2026-09-05")
    assert health.loc[0, "internal_sku_count"] == 1
    assert len(changes) == len(internal) + len(public)
    assert changes.loc[changes["entity_type"].eq("internal_sku"), "is_simulated"].all()
    assert not changes.loc[changes["entity_type"].eq("public_listing"), "is_simulated"].any()


def test_product_field_dictionary_defines_unique_governed_fields() -> None:
    dictionary = build_product_field_dictionary()
    assert len(dictionary) == 19
    assert dictionary["field_name"].is_unique
    assert dictionary[["business_definition", "validation_rule"]].notna().all().all()


def test_export_builds_auditable_database_and_report(tmp_path: Path) -> None:
    internal = build_internal_product_master(_internal())
    public = build_public_listing_master(_public())
    tables = {
        "product_catalog_internal": internal,
        "product_catalog_public": public,
        "product_maintenance_queue": build_product_maintenance_queue(public),
        "product_category_health": build_product_category_health(internal, public),
        "product_change_log": build_product_change_log(internal, public, "2026-09-05"),
        "product_field_dictionary": build_product_field_dictionary(),
    }
    database_path = tmp_path / "operations.db"
    export_product_catalog(
        tables,
        tmp_path / "processed",
        database_path,
        ROOT / "sql" / "product_catalog_views.sql",
    )
    report_path = tmp_path / "product_catalog_report.md"
    write_product_catalog_report(tables, report_path)

    with sqlite3.connect(database_path) as connection:
        view_count = connection.execute(
            """SELECT COUNT(*) FROM sqlite_master
               WHERE type='view' AND name IN (
                   'vw_product_master_health',
                   'vw_public_listing_quality',
                   'vw_product_maintenance_queue',
                   'vw_product_category_coverage'
               )"""
        ).fetchone()[0]
        index_count = connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name LIKE 'idx_product_%'"
        ).fetchone()[0]
    assert view_count == 4
    assert index_count == 6
    assert (tmp_path / "processed" / "product_catalog_public.csv").exists()
    assert "## 4. SQL 运营化" in report_path.read_text(encoding="utf-8")
