from __future__ import annotations

import sqlite3

import pandas as pd

from arknights_merch_analytics.erp import export_erp_tables, simulate_erp_operations


def _base_skus() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "sku_id": "能天使-吧唧",
                "operator": "能天使",
                "category": "吧唧（徽章）",
                "price": 18.0,
                "unit_cost": 5.4,
                "heat_score": 90.0,
                "launch_inventory": 100,
                "sold_units": 80,
                "production_risk": 0.15,
            },
            {
                "sku_id": "凯尔希-毛绒",
                "operator": "凯尔希",
                "category": "毛绒玩偶",
                "price": 128.0,
                "unit_cost": 61.44,
                "heat_score": 75.0,
                "launch_inventory": 80,
                "sold_units": 55,
                "production_risk": 0.46,
            },
        ]
    )


def test_builds_reconciled_erp_tables(tmp_path) -> None:
    responses = pd.DataFrame(
        [
            {"category": "吧唧（徽章）", "channel": "官方商城"},
            {"category": "毛绒玩偶", "channel": "淘宝/天猫"},
        ]
    )
    rankings = pd.DataFrame(
        [
            {"operator": "能天使", "preference_weight": 3},
            {"operator": "凯尔希", "preference_weight": 2},
        ]
    )
    tables = simulate_erp_operations(
        _base_skus(), responses, rankings, days=15, order_count=120, seed=7
    )

    assert set(tables) == {
        "erp_sku_master",
        "erp_order_headers",
        "erp_order_lines",
        "erp_inventory_daily",
        "erp_purchase_orders",
        "erp_after_sales",
        "erp_financial_summary",
    }
    assert len(tables["erp_order_headers"]) == 120
    assert len(tables["erp_inventory_daily"]) == 30
    assert tables["erp_sku_master"]["is_simulated"].all()
    assert tables["erp_financial_summary"]["gross_profit"].notna().all()

    database_path = tmp_path / "operations.db"
    views_path = tmp_path / "views.sql"
    views_path.write_text(
        "CREATE VIEW vw_test_erp AS SELECT COUNT(*) AS n FROM erp_order_headers;",
        encoding="utf-8",
    )
    export_erp_tables(tables, tmp_path / "csv", database_path, views_path)
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT n FROM vw_test_erp").fetchone()[0] == 120
        mismatch = connection.execute(
            """
            WITH totals AS (
                SELECT order_id, ROUND(SUM(net_revenue), 2) AS line_total
                FROM erp_order_lines GROUP BY order_id
            )
            SELECT COUNT(*)
            FROM erp_order_headers JOIN totals USING (order_id)
            WHERE ABS(order_amount - discount_amount - line_total) > 0.01
            """
        ).fetchone()[0]
        assert mismatch == 0
