DROP VIEW IF EXISTS vw_operator_demand_decision_board;
DROP VIEW IF EXISTS vw_category_price_decision_board;
DROP VIEW IF EXISTS vw_erp_abc_xyz_portfolio;
DROP VIEW IF EXISTS vw_erp_replenishment_budget;
DROP VIEW IF EXISTS vw_erp_after_sales_pareto;
DROP VIEW IF EXISTS vw_erp_category_operating_health;
DROP VIEW IF EXISTS vw_erp_daily_rolling_kpis;

CREATE VIEW vw_operator_demand_decision_board AS
SELECT
    demand_rank,
    operator,
    ROUND(demand_score, 2) AS demand_score,
    demand_tier,
    ROUND(content_signal, 2) AS content_signal,
    ROUND(survey_signal, 2) AS survey_signal,
    ROUND(skland_signal, 2) AS skland_signal,
    ROUND(commerce_signal, 2) AS commerce_signal,
    evidence_source_count,
    ROUND(evidence_confidence, 2) AS evidence_confidence,
    ROUND(scenario_rank_range, 2) AS scenario_rank_range,
    decision_note
FROM operator_demand_fusion;

CREATE VIEW vw_category_price_decision_board AS
SELECT
    category,
    ROUND(category_demand_score, 2) AS category_demand_score,
    respondent_count,
    ROUND(100.0 * high_intent_share, 2) AS high_intent_share_pct,
    recommended_entry_price,
    recommended_core_price,
    recommended_premium_price,
    observed_official_sku_count,
    observed_market_price_median,
    market_evidence_grade,
    pricing_action
FROM category_price_architecture;

CREATE VIEW vw_erp_abc_xyz_portfolio AS
SELECT
    abc_xyz_class,
    COUNT(*) AS sku_count,
    ROUND(SUM(net_sales_after_refund), 2) AS net_sales_after_refund,
    ROUND(100.0 * SUM(net_sales_after_refund)
        / NULLIF((SELECT SUM(net_sales_after_refund) FROM erp_sku_diagnostics), 0), 2)
        AS sales_share_pct,
    ROUND(AVG(demand_cv), 3) AS average_demand_cv,
    ROUND(AVG(days_of_inventory), 2) AS average_days_of_inventory,
    ROUND(SUM(lost_sales_value_proxy), 2) AS lost_sales_value_proxy
FROM erp_sku_diagnostics
GROUP BY abc_xyz_class;

CREATE VIEW vw_erp_replenishment_budget AS
SELECT
    replenishment_priority,
    COUNT(*) AS sku_count,
    SUM(suggested_po_quantity) AS suggested_po_units,
    ROUND(SUM(suggested_purchase_amount), 2) AS suggested_purchase_amount
FROM erp_replenishment_plan
GROUP BY replenishment_priority;

CREATE VIEW vw_erp_after_sales_pareto AS
SELECT
    category,
    reason,
    case_count,
    affected_units,
    ROUND(refund_amount, 2) AS refund_amount,
    ROUND(100.0 * case_share, 2) AS case_share_pct,
    ROUND(100.0 * cumulative_case_share, 2) AS cumulative_case_share_pct,
    ROUND(average_resolution_days, 2) AS average_resolution_days,
    pareto_priority
FROM erp_after_sales_pareto;

CREATE VIEW vw_erp_category_operating_health AS
SELECT
    category,
    sku_count,
    sold_units,
    ROUND(net_sales_after_refund, 2) AS net_sales_after_refund,
    ROUND(gross_profit, 2) AS gross_profit,
    ROUND(100.0 * gross_margin_rate, 2) AS gross_margin_pct,
    ROUND(100.0 * return_rate, 2) AS return_rate_pct,
    ROUND(100.0 * stockout_rate, 2) AS stockout_rate_pct,
    ROUND(average_days_of_inventory, 2) AS average_days_of_inventory,
    ROUND(average_gmroi, 2) AS average_gmroi,
    category_action
FROM erp_category_diagnostics;

CREATE VIEW vw_erp_daily_rolling_kpis AS
SELECT
    date,
    order_count,
    paid_order_count,
    ROUND(100.0 * payment_rate, 2) AS payment_rate_pct,
    ROUND(product_net_revenue, 2) AS product_net_revenue,
    sold_units,
    stockout_units,
    ROUND(100.0 * fill_rate, 2) AS fill_rate_pct,
    after_sales_case_count,
    ROUND(refund_amount, 2) AS refund_amount,
    ROUND(rolling_7d_revenue, 2) AS rolling_7d_revenue,
    rolling_7d_units,
    ROUND(rolling_7d_refund_amount, 2) AS rolling_7d_refund_amount
FROM erp_daily_kpis;
