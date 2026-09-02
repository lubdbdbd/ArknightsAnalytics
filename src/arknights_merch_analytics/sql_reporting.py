from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


SQL_REPORT_QUERIES = {
    "role_decision_board": """
        SELECT
            validation_queue_rank,
            operator,
            content_heat,
            commercial_heat,
            content_commerce_gap,
            business_quadrant,
            recommended_action,
            evidence_risk
        FROM vw_role_commercial_dashboard
        ORDER BY validation_queue_rank
        LIMIT 15
    """,
    "category_operations": """
        SELECT *
        FROM vw_category_operations
        ORDER BY simulated_gross_profit DESC
    """,
    "top_sku_portfolio": """
        SELECT
            operator,
            operator_sku_rank,
            sku_id,
            category,
            ROUND(selection_score, 2) AS selection_score,
            ROUND(simulated_gross_profit, 2) AS simulated_gross_profit,
            risk_tier,
            portfolio_role
        FROM vw_sku_portfolio_rank
        WHERE operator_sku_rank <= 2
        ORDER BY selection_score DESC
        LIMIT 20
    """,
    "taobao_quality_audit": """
        SELECT
            listing_quality_status,
            COUNT(*) AS listing_count,
            ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS listing_share_pct,
            SUM(trackable_for_timeseries) AS trackable_count,
            ROUND(SUM(sales_proxy_min), 2) AS sales_proxy_lower_bound
        FROM vw_taobao_listing_quality
        GROUP BY listing_quality_status
        ORDER BY listing_count DESC
    """,
    "taobao_category_market": """
        SELECT *
        FROM vw_taobao_category_market
        ORDER BY sales_proxy_lower_bound DESC
    """,
    "price_band_structure": """
        WITH priced AS (
            SELECT
                CASE
                    WHEN price < 20 THEN '入门款(<20元)'
                    WHEN price < 50 THEN '主力款(20-49元)'
                    WHEN price < 100 THEN '中高客单(50-99元)'
                    ELSE '高客单(>=100元)'
                END AS price_band,
                item_id,
                price,
                sales_proxy_min,
                rights_type,
                fulfillment_type
            FROM taobao_public_snapshots
            WHERE query_scope = 'market_baseline'
              AND ip_scope = 'arknights'
        )
        SELECT
            price_band,
            COUNT(DISTINCT item_id) AS sku_count,
            ROUND(AVG(price), 2) AS avg_price,
            ROUND(SUM(sales_proxy_min), 2) AS sales_proxy_lower_bound,
            ROUND(AVG(CASE WHEN rights_type IN ('官方/授权', 'official_or_licensed') THEN 1.0 ELSE 0.0 END) * 100, 2)
                AS official_share_pct,
            ROUND(AVG(CASE WHEN fulfillment_type IN ('预售/补款', 'presale_or_balance') THEN 1.0 ELSE 0.0 END) * 100, 2)
                AS presale_share_pct
        FROM priced
        GROUP BY price_band
        ORDER BY avg_price
    """,
    "inventory_risk_queue": """
        WITH risk_ranked AS (
            SELECT
                sku_id,
                operator,
                category,
                ROUND(inventory_risk, 2) AS inventory_risk,
                ROUND(return_rate * 100, 2) AS return_rate_pct,
                ROUND(sell_through_rate * 100, 2) AS sell_through_rate_pct,
                risk_tier,
                ROW_NUMBER() OVER (
                    PARTITION BY category
                    ORDER BY inventory_risk DESC, return_rate DESC
                ) AS category_risk_rank
            FROM vw_sku_portfolio_rank
        )
        SELECT *
        FROM risk_ranked
        WHERE category_risk_rank <= 3
        ORDER BY inventory_risk DESC
    """,
    "index_plan_audit": """
        EXPLAIN QUERY PLAN
        SELECT item_id, category, price, sales_proxy_min
        FROM taobao_public_snapshots
        WHERE query_scope = 'market_baseline'
          AND ip_scope = 'arknights'
          AND category = '亚克力立牌'
    """,
}


def build_sql_analysis_outputs(
    database_path: Path,
    output_dir: Path,
    report_path: Path,
) -> dict[str, pd.DataFrame]:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(database_path) as connection:
        results = {
            name: pd.read_sql_query(query, connection)
            for name, query in SQL_REPORT_QUERIES.items()
        }
        kpis = pd.read_sql_query(
            """
            SELECT
                (SELECT COUNT(*) FROM operator_heat) AS operator_count,
                (SELECT COUNT(*) FROM sku_recommendations) AS simulated_sku_count,
                (SELECT COUNT(*) FROM taobao_public_snapshots) AS taobao_snapshot_count,
                (SELECT COUNT(*) FROM vw_role_commercial_dashboard
                    WHERE business_quadrant = '核心商业角色') AS core_commercial_roles,
                (SELECT COUNT(*) FROM vw_taobao_listing_quality
                    WHERE trackable_for_timeseries = 1) AS trackable_listing_count,
                (SELECT COUNT(*) FROM vw_sku_portfolio_rank
                    WHERE portfolio_role = '直播核心款') AS live_core_sku_count
            """,
            connection,
        )

    for name, frame in results.items():
        frame.to_csv(output_dir / f"sql_{name}.csv", index=False, encoding="utf-8-sig")
    kpi = kpis.iloc[0]
    sections = [
        "# SQL 运营分析成果报告",
        "",
        "## SQL 数据资产概览",
        "",
        f"- 角色主数据：{int(kpi['operator_count'])} 名。",
        f"- 模拟 SKU：{int(kpi['simulated_sku_count'])} 个。",
        f"- 淘宝公开快照：{int(kpi['taobao_snapshot_count'])} 条。",
        f"- 核心商业角色：{int(kpi['core_commercial_roles'])} 名。",
        f"- 可进入固定商品 ID 时间序列：{int(kpi['trackable_listing_count'])} 条。",
        f"- SQL 识别直播核心款：{int(kpi['live_core_sku_count'])} 个。",
        "",
        "## SQL 技术应用",
        "",
        "- 使用 `JOIN` 和角色主键统一内容热度、淘宝商业信号及 SKU 经营指标。",
        "- 使用 `WITH` CTE 拆分价格带、库存风险和业务决策链路。",
        "- 使用 `ROW_NUMBER`、`PERCENT_RANK` 和窗口聚合完成分角色、分品类排名。",
        "- 使用 `CASE WHEN` 将指标转换为业务象限、风险等级、价格带和商品角色。",
        "- 使用条件聚合与 `NULLIF` 计算加权转化率、售罄率、退货率及服务覆盖率。",
        "- 使用复合索引优化角色选品、商品快照、品类分析和商业验证队列查询。",
        "",
    ]
    titles = {
        "role_decision_board": "角色商业验证决策队列",
        "category_operations": "品类经营表现",
        "top_sku_portfolio": "角色 Top SKU 组合",
        "taobao_quality_audit": "淘宝公开数据质量审计",
        "taobao_category_market": "淘宝品类市场结构",
        "price_band_structure": "价格带结构",
        "inventory_risk_queue": "库存风险队列",
        "index_plan_audit": "索引执行计划审计",
    }
    for name, frame in results.items():
        sections.extend([f"## {titles[name]}", "", frame.to_markdown(index=False), ""])
    report_path.write_text("\n".join(sections), encoding="utf-8")
    return results
