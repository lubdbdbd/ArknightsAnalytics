DROP VIEW IF EXISTS vw_erp_executive_dashboard;
DROP VIEW IF EXISTS vw_erp_channel_performance;
DROP VIEW IF EXISTS vw_erp_inventory_health;
DROP VIEW IF EXISTS vw_erp_replenishment_queue;
DROP VIEW IF EXISTS vw_erp_after_sales_quality;
DROP VIEW IF EXISTS vw_erp_daily_operations;

CREATE VIEW vw_erp_executive_dashboard AS
SELECT
    COUNT(*) AS sku_count,
    ROUND(SUM(net_sales_after_refund), 2) AS net_sales_after_refund,
    ROUND(SUM(gross_profit), 2) AS gross_profit,
    ROUND(100.0 * SUM(gross_profit) / NULLIF(SUM(net_sales_after_refund), 0), 2)
        AS gross_margin_pct,
    SUM(sold_units) AS sold_units,
    SUM(return_units) AS return_units,
    ROUND(100.0 * SUM(return_units) / NULLIF(SUM(sold_units), 0), 2) AS return_rate_pct,
    ROUND(AVG(days_of_inventory), 2) AS average_days_of_inventory,
    ROUND(100.0 * SUM(stockout_units) / NULLIF(SUM(sold_units + stockout_units), 0), 2)
        AS stockout_rate_pct,
    SUM(CASE WHEN inventory_status = 'replenish_now' THEN 1 ELSE 0 END) AS replenish_sku_count,
    SUM(CASE WHEN inventory_status = 'slow_moving' THEN 1 ELSE 0 END) AS slow_moving_sku_count,
    SUM(CASE WHEN inventory_status = 'high_return' THEN 1 ELSE 0 END) AS high_return_sku_count
FROM erp_financial_summary;

CREATE VIEW vw_erp_channel_performance AS
WITH channel_sales AS (
    SELECT
        order_id,
        channel,
        paid_amount,
        discount_amount
    FROM erp_order_headers
    WHERE payment_status = 'paid'
), channel_refunds AS (
    SELECT
        orders.channel,
        SUM(after_sales.refund_amount) AS refund_amount
    FROM erp_after_sales AS after_sales
    JOIN erp_order_headers AS orders USING (order_id)
    GROUP BY orders.channel
)
SELECT
    sales.channel,
    COUNT(DISTINCT sales.order_id) AS paid_order_count,
    ROUND(SUM(sales.paid_amount), 2) AS paid_amount,
    ROUND(SUM(sales.discount_amount), 2) AS discount_amount,
    ROUND(COALESCE(refunds.refund_amount, 0), 2) AS refund_amount,
    ROUND(SUM(sales.paid_amount) - COALESCE(refunds.refund_amount, 0), 2)
        AS net_sales_after_refund,
    ROUND(AVG(sales.paid_amount), 2) AS average_order_value,
    ROUND(100.0 * COALESCE(refunds.refund_amount, 0) / NULLIF(SUM(sales.paid_amount), 0), 2)
        AS refund_amount_rate_pct
FROM channel_sales AS sales
LEFT JOIN channel_refunds AS refunds USING (channel)
GROUP BY sales.channel;

CREATE VIEW vw_erp_inventory_health AS
SELECT
    sku_id,
    operator,
    category,
    sold_units,
    return_units,
    ROUND(return_rate * 100, 2) AS return_rate_pct,
    ending_inventory,
    ROUND(days_of_inventory, 2) AS days_of_inventory,
    ROUND(inventory_turnover, 2) AS inventory_turnover,
    ROUND(sell_through_rate * 100, 2) AS sell_through_rate_pct,
    ROUND(stockout_rate * 100, 2) AS stockout_rate_pct,
    inventory_status,
    recommended_action
FROM erp_financial_summary;

CREATE VIEW vw_erp_replenishment_queue AS
SELECT
    sku_id,
    operator,
    category,
    ending_inventory,
    reorder_point,
    purchase_lead_time_days,
    ROUND(days_of_inventory, 2) AS days_of_inventory,
    ROUND(stockout_rate * 100, 2) AS stockout_rate_pct,
    CASE
        WHEN stockout_rate >= 0.02 THEN 1
        WHEN ending_inventory <= reorder_point THEN 2
        WHEN days_of_inventory < purchase_lead_time_days + 7 THEN 3
        ELSE 4
    END AS replenishment_priority,
    CASE
        WHEN stockout_rate >= 0.02 THEN '补偿缺货并提高安全库存'
        WHEN ending_inventory <= reorder_point THEN '立即创建采购单'
        WHEN days_of_inventory < purchase_lead_time_days + 7 THEN '进入补货观察'
        ELSE '暂不补货'
    END AS replenishment_action
FROM erp_financial_summary
WHERE stockout_rate >= 0.02
   OR ending_inventory <= reorder_point
   OR days_of_inventory < purchase_lead_time_days + 7;

CREATE VIEW vw_erp_after_sales_quality AS
SELECT
    finance.sku_id,
    finance.operator,
    finance.category,
    finance.sold_units,
    COUNT(after_sales.case_id) AS after_sales_case_count,
    COALESCE(SUM(after_sales.units), 0) AS after_sales_units,
    ROUND(100.0 * COALESCE(SUM(after_sales.units), 0) / NULLIF(finance.sold_units, 0), 2)
        AS return_rate_pct,
    ROUND(COALESCE(SUM(after_sales.refund_amount), 0), 2) AS refund_amount,
    ROUND(AVG(julianday(after_sales.resolved_at) - julianday(after_sales.requested_at)), 2)
        AS average_resolution_days
FROM erp_financial_summary AS finance
LEFT JOIN erp_after_sales AS after_sales USING (sku_id)
GROUP BY finance.sku_id, finance.operator, finance.category, finance.sold_units;

CREATE VIEW vw_erp_daily_operations AS
SELECT
    inventory.snapshot_date,
    SUM(inventory.sold_units) AS sold_units,
    SUM(inventory.stockout_units) AS stockout_units,
    SUM(inventory.inbound_units) AS inbound_units,
    SUM(inventory.returned_units) AS returned_units,
    SUM(inventory.closing_stock) AS closing_stock,
    ROUND(
        100.0 * SUM(inventory.stockout_units)
        / NULLIF(SUM(inventory.sold_units + inventory.stockout_units), 0),
        2
    ) AS stockout_rate_pct
FROM erp_inventory_daily AS inventory
GROUP BY inventory.snapshot_date;
