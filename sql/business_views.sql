DROP VIEW IF EXISTS vw_role_commercial_dashboard;
DROP VIEW IF EXISTS vw_sku_portfolio_rank;
DROP VIEW IF EXISTS vw_category_operations;
DROP VIEW IF EXISTS vw_taobao_listing_quality;
DROP VIEW IF EXISTS vw_taobao_category_market;
DROP VIEW IF EXISTS vw_bilibili_campaign_performance;

CREATE VIEW vw_role_commercial_dashboard AS
SELECT
    operator,
    heat_rank,
    commerce_rank,
    ROUND(cross_platform_heat, 2) AS content_heat,
    ROUND(commercial_heat_score, 2) AS commercial_heat,
    ROUND(content_commerce_gap, 2) AS content_commerce_gap,
    ROUND(confidence_score, 2) AS content_confidence,
    ROUND(commerce_confidence_score, 2) AS commerce_confidence,
    data_quality_grade AS content_data_grade,
    commerce_data_grade,
    taobao_observed,
    organic_sku_count,
    sales_proxy_min,
    category_breadth,
    business_quadrant,
    ROUND(commercial_validation_priority, 2) AS validation_priority,
    ROW_NUMBER() OVER (
        ORDER BY commercial_validation_priority DESC, cross_platform_heat DESC
    ) AS validation_queue_rank,
    CASE
        WHEN business_quadrant = '核心商业角色' THEN '扩展品类并测试组合套装'
        WHEN business_quadrant = '内容热、商业供给待验证' THEN '补采淘宝并小批量测试低成本SKU'
        WHEN business_quadrant = '内容长尾但商品信号强' THEN '核查圈层需求与联名活动影响'
        ELSE '维持基础款并观察版本事件'
    END AS recommended_action,
    CASE
        WHEN confidence_score < 50 OR commerce_confidence_score < 50 THEN '高证据风险'
        WHEN confidence_score < 70 OR commerce_confidence_score < 70 THEN '中证据风险'
        ELSE '低证据风险'
    END AS evidence_risk
FROM content_commerce_matrix;

CREATE VIEW vw_sku_portfolio_rank AS
SELECT
    sku_id,
    operator,
    category,
    price,
    unit_cost,
    selection_score,
    recommendation,
    live_fit,
    production_risk,
    gross_margin_rate,
    conversion_rate,
    sell_through_rate,
    return_rate,
    inventory_risk,
    gmv,
    ROUND(gmv * gross_margin_rate, 2) AS simulated_gross_profit,
    ROW_NUMBER() OVER (
        PARTITION BY operator
        ORDER BY selection_score DESC, gross_margin_rate DESC
    ) AS operator_sku_rank,
    ROW_NUMBER() OVER (
        PARTITION BY category
        ORDER BY selection_score DESC, gross_margin_rate DESC
    ) AS category_sku_rank,
    ROUND(
        100 * PERCENT_RANK() OVER (
            PARTITION BY category
            ORDER BY selection_score
        ),
        2
    ) AS category_score_percentile,
    CASE
        WHEN inventory_risk >= 60 OR return_rate >= 0.08 THEN '高风险'
        WHEN inventory_risk >= 35 OR return_rate >= 0.04 THEN '中风险'
        ELSE '低风险'
    END AS risk_tier,
    CASE
        WHEN recommendation = '重点推荐' AND live_fit >= 0.80 THEN '直播核心款'
        WHEN recommendation = '重点推荐' THEN '常规重点款'
        WHEN gross_margin_rate >= 0.65 AND inventory_risk < 40 THEN '利润承接款'
        ELSE '观察款'
    END AS portfolio_role
FROM sku_recommendations;

CREATE VIEW vw_category_operations AS
SELECT
    category,
    COUNT(*) AS sku_count,
    COUNT(DISTINCT operator) AS operator_count,
    ROUND(AVG(price), 2) AS avg_price,
    ROUND(AVG(gross_margin_rate) * 100, 2) AS avg_margin_pct,
    ROUND(SUM(gmv), 2) AS simulated_gmv,
    ROUND(SUM(gmv * gross_margin_rate), 2) AS simulated_gross_profit,
    ROUND(100.0 * SUM(orders) / NULLIF(SUM(page_views), 0), 2) AS weighted_conversion_pct,
    ROUND(100.0 * SUM(sold_units) / NULLIF(SUM(launch_inventory), 0), 2) AS weighted_sell_through_pct,
    ROUND(100.0 * SUM(return_units) / NULLIF(SUM(sold_units), 0), 2) AS weighted_return_pct,
    ROUND(AVG(inventory_risk), 2) AS avg_inventory_risk,
    SUM(CASE WHEN recommendation = '重点推荐' THEN 1 ELSE 0 END) AS priority_sku_count,
    SUM(CASE WHEN live_fit >= 0.80 THEN 1 ELSE 0 END) AS live_ready_sku_count,
    SUM(CASE WHEN production_risk >= 0.60 THEN 1 ELSE 0 END) AS high_production_risk_count
FROM sku_recommendations
GROUP BY category;

CREATE VIEW vw_taobao_listing_quality AS
SELECT
    snapshot_at,
    query_scope,
    target_operator,
    item_id,
    rank,
    category,
    price,
    sales_proxy_min,
    sales_proxy_censored,
    numeric_sales_available,
    target_relevance,
    ip_scope,
    rights_type,
    fulfillment_type,
    free_shipping,
    return_insurance,
    fast_dispatch,
    CASE
        WHEN ip_scope <> 'arknights' THEN '跨IP排除'
        WHEN query_scope = 'targeted' AND target_relevance < 0.50 THEN '目标角色不相关'
        WHEN numeric_sales_available = 0 THEN '缺少销量代理'
        WHEN sales_proxy_censored = 1 THEN '销量档位截断'
        ELSE '可稳定分析'
    END AS listing_quality_status,
    CASE
        WHEN item_id IS NOT NULL
         AND item_id <> ''
         AND ip_scope = 'arknights'
         AND (query_scope <> 'targeted' OR target_relevance >= 0.50)
        THEN 1 ELSE 0
    END AS trackable_for_timeseries
FROM taobao_public_snapshots;

CREATE VIEW vw_taobao_category_market AS
SELECT
    category,
    COUNT(DISTINCT item_id) AS organic_sku_count,
    ROUND(MIN(price), 2) AS min_price,
    ROUND(AVG(price), 2) AS avg_price,
    ROUND(MAX(price), 2) AS max_price,
    ROUND(SUM(sales_proxy_min), 2) AS sales_proxy_lower_bound,
    ROUND(AVG(CASE WHEN rights_type IN ('官方/授权', 'official_or_licensed') THEN 1.0 ELSE 0.0 END) * 100, 2)
        AS official_share_pct,
    ROUND(AVG(CASE WHEN rights_type IN ('同人原创', 'fanmade') THEN 1.0 ELSE 0.0 END) * 100, 2)
        AS fanmade_share_pct,
    ROUND(AVG(CASE WHEN fulfillment_type IN ('预售/补款', 'presale_or_balance') THEN 1.0 ELSE 0.0 END) * 100, 2)
        AS presale_share_pct,
    ROUND(AVG(free_shipping) * 100, 2) AS free_shipping_rate_pct,
    ROUND(AVG(return_insurance) * 100, 2) AS return_insurance_rate_pct,
    ROUND(AVG(fast_dispatch) * 100, 2) AS fast_dispatch_rate_pct
FROM taobao_public_snapshots
WHERE query_scope = 'market_baseline'
  AND ip_scope = 'arknights'
GROUP BY category;

CREATE VIEW vw_bilibili_campaign_performance AS
SELECT
    operator,
    bilibili_campaign_content_count AS campaign_content_count,
    bilibili_direct_content_count AS direct_content_count,
    bilibili_window_content_count AS window_content_count,
    bilibili_campaign_content_types AS content_type_count,
    ROUND(bilibili_weighted_campaign_views, 2) AS weighted_campaign_views,
    ROUND(bilibili_weighted_intent_actions, 2) AS weighted_intent_actions,
    ROUND(bilibili_campaign_exposure_score, 2) AS campaign_exposure_score,
    ROUND(bilibili_campaign_depth_score, 2) AS campaign_depth_score,
    ROW_NUMBER() OVER (
        ORDER BY bilibili_campaign_exposure_score DESC,
                 bilibili_campaign_content_count DESC
    ) AS campaign_rank
FROM bilibili_operator_campaign_summary;
