DROP VIEW IF EXISTS vw_pilot_content_funnel;
DROP VIEW IF EXISTS vw_pilot_supplier_scorecard;
DROP VIEW IF EXISTS vw_pilot_order_kpis;
DROP VIEW IF EXISTS vw_pilot_fulfillment_kpis;
DROP VIEW IF EXISTS vw_pilot_after_sales_kpis;
DROP VIEW IF EXISTS vw_pilot_candidate_decision;

CREATE VIEW vw_pilot_content_funnel AS
WITH intent AS (
    SELECT
        candidate_id,
        COUNT(*) AS intent_count,
        SUM(CASE WHEN qualified_intent = 1 THEN 1 ELSE 0 END) AS qualified_intent_count,
        ROUND(AVG(accepted_price), 2) AS average_accepted_price,
        ROUND(AVG(preorder_tolerance_days), 2) AS average_preorder_tolerance_days
    FROM pilot_intent_leads
    GROUP BY candidate_id
)
SELECT
    campaigns.candidate_id,
    COUNT(DISTINCT campaigns.campaign_id) AS campaign_count,
    SUM(campaigns.impressions) AS impressions,
    SUM(campaigns.clicks) AS clicks,
    SUM(campaigns.landing_uv) AS landing_uv,
    ROUND(100.0 * SUM(campaigns.clicks) / NULLIF(SUM(campaigns.impressions), 0), 2) AS ctr_pct,
    COALESCE(intent.intent_count, 0) AS intent_count,
    COALESCE(intent.qualified_intent_count, 0) AS qualified_intent_count,
    ROUND(100.0 * COALESCE(intent.qualified_intent_count, 0) / NULLIF(SUM(campaigns.landing_uv), 0), 2)
        AS qualified_intent_conversion_pct,
    intent.average_accepted_price,
    intent.average_preorder_tolerance_days
FROM pilot_campaigns AS campaigns
LEFT JOIN intent USING (candidate_id)
GROUP BY campaigns.candidate_id;

CREATE VIEW vw_pilot_supplier_scorecard AS
SELECT
    quote_id,
    candidate_id,
    supplier_code,
    rights_verified,
    moq,
    unit_cost,
    sample_cost,
    lead_time_days,
    defect_allowance_pct,
    quote_status,
    CASE
        WHEN rights_verified = 0 THEN 0
        ELSE ROUND(
            100
            - MIN(moq, 100) * 0.20
            - MIN(lead_time_days, 120) * 0.25
            - MIN(defect_allowance_pct, 10) * 2,
            2
        )
    END AS supplier_score,
    CASE
        WHEN rights_verified = 1 AND quote_status IN ('qualified', 'accepted') THEN 1
        ELSE 0
    END AS eligible_for_pilot
FROM pilot_supplier_quotes;

CREATE VIEW vw_pilot_order_kpis AS
SELECT
    candidate_id,
    COUNT(*) AS order_count,
    SUM(CASE WHEN payment_status = 'paid' THEN 1 ELSE 0 END) AS paid_order_count,
    SUM(CASE WHEN payment_status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled_order_count,
    SUM(CASE WHEN payment_status = 'paid' THEN quantity ELSE 0 END) AS paid_units,
    ROUND(SUM(CASE WHEN payment_status = 'paid' THEN paid_amount ELSE 0 END), 2) AS paid_amount,
    ROUND(AVG(CASE WHEN payment_status = 'paid' THEN paid_amount END), 2) AS average_order_value,
    ROUND(100.0 * SUM(CASE WHEN payment_status = 'paid' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2)
        AS paid_conversion_pct,
    ROUND(100.0 * SUM(CASE WHEN payment_status = 'cancelled' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2)
        AS cancellation_rate_pct
FROM pilot_orders
GROUP BY candidate_id;

CREATE VIEW vw_pilot_fulfillment_kpis AS
WITH delivered AS (
    SELECT order_id, MIN(event_at) AS delivered_at
    FROM pilot_fulfillment_events
    WHERE event_type = 'delivered'
    GROUP BY order_id
), shipped AS (
    SELECT order_id, MIN(event_at) AS shipped_at
    FROM pilot_fulfillment_events
    WHERE event_type = 'shipped'
    GROUP BY order_id
)
SELECT
    orders.candidate_id,
    COUNT(DISTINCT CASE WHEN orders.payment_status = 'paid' THEN orders.order_id END) AS paid_order_count,
    COUNT(DISTINCT delivered.order_id) AS delivered_order_count,
    ROUND(
        100.0 * COUNT(DISTINCT delivered.order_id)
        / NULLIF(COUNT(DISTINCT CASE WHEN orders.payment_status = 'paid' THEN orders.order_id END), 0),
        2
    ) AS delivery_completion_pct,
    ROUND(AVG(julianday(shipped.shipped_at) - julianday(orders.order_date)), 2) AS average_ship_days,
    ROUND(AVG(julianday(delivered.delivered_at) - julianday(orders.order_date)), 2) AS average_delivery_days
FROM pilot_orders AS orders
LEFT JOIN shipped USING (order_id)
LEFT JOIN delivered USING (order_id)
GROUP BY orders.candidate_id;

CREATE VIEW vw_pilot_after_sales_kpis AS
SELECT
    orders.candidate_id,
    COUNT(DISTINCT orders.order_id) AS paid_order_count,
    COUNT(DISTINCT after_sales.case_id) AS after_sales_case_count,
    ROUND(COALESCE(SUM(after_sales.refund_amount), 0), 2) AS refund_amount,
    ROUND(
        100.0 * COUNT(DISTINCT after_sales.case_id) / NULLIF(COUNT(DISTINCT orders.order_id), 0),
        2
    ) AS after_sales_case_rate_pct,
    ROUND(AVG(julianday(after_sales.resolved_at) - julianday(after_sales.requested_at)), 2)
        AS average_resolution_days
FROM pilot_orders AS orders
LEFT JOIN pilot_after_sales AS after_sales USING (order_id)
WHERE orders.payment_status = 'paid'
GROUP BY orders.candidate_id;

CREATE VIEW vw_pilot_candidate_decision AS
SELECT
    candidates.candidate_id,
    candidates.operator,
    candidates.base_operator,
    candidates.category,
    ROUND(candidates.pilot_score, 2) AS pilot_score,
    candidates.evidence_status,
    COALESCE(decisions.candidate_approved, 0) AS candidate_approved,
    COALESCE(funnel.qualified_intent_count, 0) AS qualified_intent_count,
    COALESCE(suppliers.verified_quote_count, 0) AS verified_quote_count,
    COALESCE(orders.paid_order_count, 0) AS paid_order_count,
    COALESCE(fulfillment.delivered_order_count, 0) AS delivered_order_count,
    CASE
        WHEN COALESCE(decisions.candidate_approved, 0) = 0 THEN '待人工审批'
        WHEN COALESCE(funnel.qualified_intent_count, 0) < 30 THEN '继续需求验证'
        WHEN COALESCE(suppliers.verified_quote_count, 0) < 3 THEN '进入供应商比价'
        WHEN COALESCE(orders.paid_order_count, 0) < 10 THEN '可申请小批量订单试点'
        WHEN COALESCE(fulfillment.delivery_completion_pct, 0) < 90 THEN '暂停扩量并修复履约'
        ELSE '完成试点并进入复盘'
    END AS recommended_stage
FROM pilot_candidate_shortlist AS candidates
LEFT JOIN vw_pilot_content_funnel AS funnel USING (candidate_id)
LEFT JOIN (
    SELECT
        candidate_id,
        MAX(CASE WHEN decision = 'approved' THEN 1 ELSE 0 END) AS candidate_approved
    FROM pilot_candidate_decisions
    GROUP BY candidate_id
) AS decisions USING (candidate_id)
LEFT JOIN (
    SELECT
        candidate_id,
        COUNT(DISTINCT CASE WHEN rights_verified = 1 THEN supplier_code END) AS verified_quote_count
    FROM pilot_supplier_quotes
    GROUP BY candidate_id
) AS suppliers USING (candidate_id)
LEFT JOIN vw_pilot_order_kpis AS orders USING (candidate_id)
LEFT JOIN vw_pilot_fulfillment_kpis AS fulfillment USING (candidate_id);
