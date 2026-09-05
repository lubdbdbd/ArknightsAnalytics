from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from arknights_merch_analytics.operations_analytics import (
    build_after_sales_pareto,
    build_category_price_architecture,
    build_channel_profitability,
    build_erp_replenishment_plan,
    build_erp_sku_diagnostics,
    build_erp_category_diagnostics,
    build_erp_daily_kpis,
    build_evidence_inventory,
    build_operator_category_portfolio,
    build_operator_demand_fusion,
    export_operational_outputs,
    write_operational_figures,
    write_operational_report,
    write_operational_workbook,
)


def _read_processed(name: str) -> pd.DataFrame:
    return pd.read_csv(ROOT / "data" / "processed" / name)


def main() -> None:
    heat = _read_processed("character_heat_matrix.csv")
    survey_operator = _read_processed("survey_243_operator_summary.csv")
    skland = _read_processed("skland_operator_summary.csv")
    commerce = _read_processed("content_commerce_matrix.csv")
    category_summary = _read_processed("survey_243_category_summary.csv")
    category_prices = pd.read_csv(ROOT / "data" / "survey" / "anonymous_category_prices_243.csv")
    operator_category = _read_processed("survey_operator_category_summary.csv")
    taobao = _read_processed("taobao_public_snapshots.csv")
    sku_master = _read_processed("erp_sku_master.csv")
    order_headers = _read_processed("erp_order_headers.csv")
    order_lines = _read_processed("erp_order_lines.csv")
    inventory = _read_processed("erp_inventory_daily.csv")
    purchase_orders = _read_processed("erp_purchase_orders.csv")
    after_sales = _read_processed("erp_after_sales.csv")
    financial = _read_processed("erp_financial_summary.csv")
    bilibili_archive = _read_processed("bilibili_official_archive.csv")
    bilibili_campaigns = _read_processed("bilibili_operator_campaign_content.csv")
    skland_snapshot = pd.read_csv(
        ROOT / "data" / "public" / "skland_strategy_operator_search_snapshot.csv"
    )
    survey_responses = pd.read_csv(ROOT / "data" / "survey" / "anonymous_responses_243.csv")
    survey_rankings = pd.read_csv(
        ROOT / "data" / "survey" / "anonymous_operator_rankings_243.csv"
    )
    weibo_count = len(
        json.loads((ROOT / "data" / "public" / "weibo_official_recent_posts.json").read_text(encoding="utf-8"))
    )
    xiaohongshu_count = len(
        json.loads((ROOT / "data" / "public" / "xiaohongshu_brand_snapshots.json").read_text(encoding="utf-8"))
    )

    demand, sensitivity = build_operator_demand_fusion(
        heat, survey_operator, skland, commerce
    )
    category_price = build_category_price_architecture(
        category_summary, category_prices, taobao, sku_master
    )
    portfolio = build_operator_category_portfolio(demand, operator_category)
    diagnostics = build_erp_sku_diagnostics(financial, order_lines, inventory, after_sales)
    replenishment = build_erp_replenishment_plan(sku_master, inventory, purchase_orders)
    pareto = build_after_sales_pareto(after_sales, sku_master)
    channels = build_channel_profitability(order_headers, order_lines, after_sales)
    category_diagnostics = build_erp_category_diagnostics(diagnostics)
    daily_kpis = build_erp_daily_kpis(order_headers, order_lines, inventory, after_sales)
    evidence = build_evidence_inventory(
        bilibili_archive,
        bilibili_campaigns,
        weibo_count,
        xiaohongshu_count,
        skland_snapshot,
        survey_responses,
        survey_rankings,
        category_prices,
        taobao,
        order_headers,
        order_lines,
        inventory,
        purchase_orders,
        after_sales,
    )
    tables = {
        "evidence_inventory": evidence,
        "operator_demand_fusion": demand,
        "operator_rank_sensitivity": sensitivity,
        "category_price_architecture": category_price,
        "operator_category_portfolio": portfolio,
        "erp_sku_diagnostics": diagnostics,
        "erp_replenishment_plan": replenishment,
        "erp_after_sales_pareto": pareto,
        "erp_channel_profitability": channels,
        "erp_category_diagnostics": category_diagnostics,
        "erp_daily_kpis": daily_kpis,
    }
    export_operational_outputs(
        tables,
        ROOT / "data" / "processed",
        ROOT / "reports" / "generated" / "operations.db",
        ROOT / "sql" / "operational_analytics_views.sql",
    )
    write_operational_report(
        tables, ROOT / "reports" / "generated" / "operational_analytics_report.md"
    )
    write_operational_workbook(
        tables, ROOT / "reports" / "generated" / "operational_analytics.xlsx"
    )
    write_operational_figures(tables, ROOT / "reports" / "figures")
    print("Built operational analytics: " + ", ".join(f"{name}={len(frame)}" for name, frame in tables.items()))


if __name__ == "__main__":
    main()
