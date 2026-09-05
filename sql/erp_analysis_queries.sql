-- 1. ERP 经营总览
SELECT * FROM vw_erp_executive_dashboard;

-- 2. 渠道成交、客单价与退款金额率
SELECT * FROM vw_erp_channel_performance ORDER BY net_sales_after_refund DESC;

-- 3. 需要立即补货的 SKU
SELECT * FROM vw_erp_replenishment_queue ORDER BY replenishment_priority, stockout_rate_pct DESC;

-- 4. 库存周转超过 180 天的滞销 SKU
SELECT * FROM vw_erp_inventory_health
WHERE inventory_status = 'slow_moving'
ORDER BY days_of_inventory DESC;

-- 5. 退货率最高的 SKU
SELECT * FROM vw_erp_after_sales_quality
ORDER BY return_rate_pct DESC
LIMIT 20;

-- 6. 各品类收入、毛利和库存健康度
SELECT
    category,
    COUNT(*) AS sku_count,
    ROUND(SUM(net_sales_after_refund), 2) AS net_sales,
    ROUND(SUM(gross_profit), 2) AS gross_profit,
    ROUND(100.0 * SUM(gross_profit) / NULLIF(SUM(net_sales_after_refund), 0), 2) AS margin_pct,
    ROUND(AVG(days_of_inventory), 2) AS average_days_of_inventory,
    ROUND(100.0 * SUM(return_units) / NULLIF(SUM(sold_units), 0), 2) AS return_rate_pct
FROM erp_financial_summary
GROUP BY category
ORDER BY gross_profit DESC;

-- 7. 采购到货完整率与延期状态
SELECT
    supplier_id,
    COUNT(*) AS purchase_order_count,
    SUM(quantity_ordered) AS ordered_units,
    SUM(quantity_received) AS received_units,
    ROUND(100.0 * SUM(quantity_received) / NULLIF(SUM(quantity_ordered), 0), 2) AS receipt_rate_pct,
    SUM(CASE WHEN purchase_status = 'open' THEN 1 ELSE 0 END) AS open_po_count
FROM erp_purchase_orders
GROUP BY supplier_id
ORDER BY receipt_rate_pct;

-- 8. 售后原因 Pareto
SELECT
    reason,
    COUNT(*) AS case_count,
    SUM(units) AS affected_units,
    ROUND(SUM(refund_amount), 2) AS refund_amount,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS case_share_pct
FROM erp_after_sales
GROUP BY reason
ORDER BY case_count DESC;

-- 9. 每日销量与缺货趋势
SELECT * FROM vw_erp_daily_operations ORDER BY snapshot_date;

-- 10. 订单头与订单明细金额对账
WITH line_total AS (
    SELECT order_id, ROUND(SUM(net_revenue), 2) AS line_net_revenue
    FROM erp_order_lines
    GROUP BY order_id
)
SELECT
    COUNT(*) AS mismatched_order_count,
    ROUND(MAX(ABS(headers.order_amount - headers.discount_amount - lines.line_net_revenue)), 2)
        AS maximum_difference
FROM erp_order_headers AS headers
JOIN line_total AS lines USING (order_id)
WHERE ABS(headers.order_amount - headers.discount_amount - lines.line_net_revenue) > 0.01;
