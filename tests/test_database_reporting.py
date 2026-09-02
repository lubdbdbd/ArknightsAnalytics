from __future__ import annotations

import sqlite3

import pandas as pd

from arknights_merch_analytics.database import export_sqlite
from arknights_merch_analytics.reporting import write_report, write_workbook


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
                "sell_through_rate": 0.8,
                "gross_margin_rate": 0.7,
                "gmv": 1800.0,
            }
        ]
    )
    taobao_listings = pd.DataFrame(
        [
            {
                "item_id": "1",
                "query_scope": "market_baseline",
                "ip_scope": "arknights",
                "category": "亚克力立牌",
                "price": 39.0,
                "sales_proxy_min": 100.0,
            }
        ]
    )
    taobao_signals = pd.DataFrame(
        [{"operator": "甲", "taobao_observed": True, "commercial_heat_score": 80.0}]
    )
    content_commerce = pd.DataFrame(
        [{"operator": "甲", "business_quadrant": "核心商业角色"}]
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
