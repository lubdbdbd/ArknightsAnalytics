WITH line_totals AS (
    SELECT order_id,
           SUM(quantity) AS units,
           SUM(ROUND(quantity * unit_price * 100)) AS gross_cents,
           SUM(ROUND(discount_amount * 100)) AS discount_cents
    FROM erp_order_lines
    GROUP BY order_id
), refund_totals AS (
    SELECT order_id, SUM(ROUND(refund_amount * 100)) AS refund_cents
    FROM erp_after_sales
    WHERE case_status = 'closed'
    GROUP BY order_id
)
SELECT orders.channel,
       COUNT(*) AS paid_orders,
       SUM(lines.units) AS units,
       SUM(ROUND(orders.paid_amount * 100)) / 100.0 AS paid_amount,
       SUM(COALESCE(refunds.refund_cents, 0)) / 100.0 AS closed_refund_amount,
       (SUM(ROUND(orders.paid_amount * 100)) - SUM(COALESCE(refunds.refund_cents, 0))) / 100.0 AS paid_less_closed_refunds,
       SUM(CASE WHEN lines.order_id IS NULL THEN 1 ELSE 0 END) AS missing_line_orders,
       SUM(CASE WHEN ABS(ROUND(orders.order_amount * 100) - lines.gross_cents) > 1
                     OR ABS(ROUND(orders.discount_amount * 100) - lines.discount_cents) > 1
                THEN 1 ELSE 0 END) AS line_mismatch_orders
FROM erp_order_headers AS orders
LEFT JOIN line_totals AS lines ON orders.order_id = lines.order_id
LEFT JOIN refund_totals AS refunds ON orders.order_id = refunds.order_id
WHERE orders.payment_status = 'paid'
GROUP BY orders.channel
ORDER BY paid_amount DESC, orders.channel;
