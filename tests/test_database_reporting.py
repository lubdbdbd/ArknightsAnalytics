from __future__ import annotations

import sqlite3

import pandas as pd

from arknights_merch_analytics.database import export_sqlite
from arknights_merch_analytics.reporting import write_report, write_workbook
from arknights_merch_analytics.sql_reporting import build_sql_analysis_outputs


def test_exports_sqlite_and_reports(tmp_path) -> None:
    videos = pd.DataFrame([{"bvid": "BV1", "title": "干员「甲」前瞻PV"}])
    heat = pd.DataFrame(
        [
            {
                "heat_rank": 1,
                "operator": "甲",
                "heat_score": 80.0,
                "total_views": 1000,
            }
        ]
    )
    erp = pd.DataFrame([{"operator": "甲", "category": "徽章"}])
    sku = pd.DataFrame(
        [
            {
                "sku_id": "甲-徽章",
                "operator": "甲",
                "category": "徽章",
                "selection_score": 75.0,
                "recommendation": "重点推荐",
                "price": 18.0,
                "unit_cost": 5.4,
                "live_fit": 0.9,
                "production_risk": 0.15,
                "page_views": 1000,
                "orders": 100,
                "launch_inventory": 120,
                "sold_units": 100,
                "return_units": 2,
                "sell_through_rate": 0.8,
                "gross_margin_rate": 0.7,
                "conversion_rate": 0.1,
                "return_rate": 0.02,
                "inventory_risk": 10.0,
                "gmv": 1800.0,
            }
        ]
    )
    taobao_listings = pd.DataFrame(
        [
            {
                "item_id": "1",
                "snapshot_at": "2026-09-02T00:00:00+08:00",
                "query_scope": "market_baseline",
                "target_operator": "",
                "ip_scope": "arknights",
                "category": "亚克力立牌",
                "rank": 1,
                "price": 39.0,
                "sales_proxy_min": 100.0,
                "sales_proxy_censored": True,
                "numeric_sales_available": True,
                "target_relevance": 1.0,
                "rights_type": "official_or_licensed",
                "fulfillment_type": "in_stock",
                "free_shipping": True,
                "return_insurance": True,
                "fast_dispatch": True,
            }
        ]
    )
    taobao_signals = pd.DataFrame(
        [
            {
                "operator": "甲",
                "taobao_observed": True,
                "commercial_heat_score": 80.0,
                "commerce_rank": 1,
            }
        ]
    )
    content_commerce = pd.DataFrame(
        [
            {
                "operator": "甲",
                "heat_rank": 1,
                "commerce_rank": 1,
                "cross_platform_heat": 80.0,
                "commercial_heat_score": 80.0,
                "content_commerce_gap": 0.0,
                "confidence_score": 90.0,
                "commerce_confidence_score": 80.0,
                "data_quality_grade": "A",
                "commerce_data_grade": "B",
                "taobao_observed": True,
                "organic_sku_count": 1.0,
                "sales_proxy_min": 100.0,
                "category_breadth": 1.0,
                "business_quadrant": "核心商业角色",
                "commercial_validation_priority": 70.0,
            }
        ]
    )
    targeted_summary = pd.DataFrame(
        [{"operator": "甲", "search_precision": 0.8}]
    )

    database_path = tmp_path / "operations.db"
    export_sqlite(
        videos,
        heat,
        erp,
        sku,
        database_path,
        taobao_listings=taobao_listings,
        taobao_market_signals=taobao_signals,
        content_commerce=content_commerce,
        targeted_query_summary=targeted_summary,
    )
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM public_videos").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM taobao_public_snapshots").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM vw_role_commercial_dashboard").fetchone()[0] == 1
        assert connection.execute("SELECT operator_sku_rank FROM vw_sku_portfolio_rank").fetchone()[0] == 1

    sql_report_path = tmp_path / "sql_report.md"
    sql_outputs = build_sql_analysis_outputs(database_path, tmp_path / "sql_outputs", sql_report_path)
    assert len(sql_outputs) == 11
    assert "SQL 运营分析成果报告" in sql_report_path.read_text(encoding="utf-8")
    assert (tmp_path / "sql_outputs" / "sql_role_decision_board.csv").exists()
    assert "idx_taobao_scope_ip_category" in sql_outputs["index_plan_audit"].iloc[0]["detail"]

    report_path = tmp_path / "report.md"
    workbook_path = tmp_path / "dashboard.xlsx"
    write_report(heat, sku, report_path)
    write_workbook(
        heat,
        erp,
        sku,
        workbook_path,
        taobao_listings=taobao_listings,
        taobao_market_signals=taobao_signals,
        content_commerce=content_commerce,
        targeted_query_summary=targeted_summary,
    )
    assert "角色榜单规模：1" in report_path.read_text(encoding="utf-8")
    assert workbook_path.exists()
