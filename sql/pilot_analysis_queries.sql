-- 1. 商业试点阶段门禁
SELECT * FROM pilot_readiness;

-- 2. 数据驱动候选池
SELECT * FROM vw_pilot_candidate_decision
ORDER BY pilot_score DESC
LIMIT 20;

-- 3. 内容预热与意向转化漏斗
SELECT * FROM vw_pilot_content_funnel
ORDER BY qualified_intent_count DESC, ctr_pct DESC;

-- 4. 合规供应商比价
SELECT * FROM vw_pilot_supplier_scorecard
ORDER BY eligible_for_pilot DESC, supplier_score DESC;

-- 5. 真实订单转化与取消
SELECT * FROM vw_pilot_order_kpis
ORDER BY paid_amount DESC;

-- 6. 履约完成率与交付时长
SELECT * FROM vw_pilot_fulfillment_kpis
ORDER BY delivery_completion_pct DESC;

-- 7. 售后率与处理时长
SELECT * FROM vw_pilot_after_sales_kpis
ORDER BY after_sales_case_rate_pct DESC;

-- 8. 订单金额对账
SELECT
    COUNT(*) AS mismatched_order_count,
    ROUND(MAX(ABS(paid_amount - (quantity * unit_price - discount_amount + shipping_fee))), 2)
        AS maximum_difference
FROM pilot_orders
WHERE payment_status = 'paid'
  AND ABS(paid_amount - (quantity * unit_price - discount_amount + shipping_fee)) > 0.01;
