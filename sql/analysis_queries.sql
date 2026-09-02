-- 1. 角色热度排名
SELECT
    heat_rank,
    operator,
    ROUND(heat_score, 2) AS heat_score,
    ROUND(reach_score, 2) AS reach_score,
    ROUND(engagement_score, 2) AS engagement_score,
    ROUND(confidence_score, 2) AS confidence_score,
    data_quality_grade
FROM operator_heat
ORDER BY heat_rank;

-- 2. 每个角色最值得优先验证的商品
WITH ranked AS (
    SELECT
        operator,
        category,
        selection_score,
        recommendation,
        sell_through_rate,
        gross_margin_rate,
        ROW_NUMBER() OVER (
            PARTITION BY operator
            ORDER BY selection_score DESC
        ) AS category_rank
    FROM sku_recommendations
)
SELECT *
FROM ranked
WHERE category_rank <= 3
ORDER BY operator, category_rank;

-- 3. 品类组合：高 GMV 不代表高推荐度
SELECT
    category,
    ROUND(AVG(selection_score), 2) AS avg_selection_score,
    ROUND(SUM(gmv), 2) AS simulated_gmv,
    ROUND(AVG(return_rate) * 100, 2) AS avg_return_rate_pct,
    ROUND(AVG(inventory_risk), 2) AS avg_inventory_risk
FROM sku_recommendations
GROUP BY category
ORDER BY avg_selection_score DESC;

-- 4. 直播重点候选
SELECT
    sku_id,
    operator,
    category,
    ROUND(selection_score, 2) AS selection_score,
    ROUND(conversion_rate * 100, 2) AS simulated_conversion_rate_pct,
    ROUND(gross_margin_rate * 100, 2) AS simulated_margin_rate_pct
FROM sku_recommendations
WHERE recommendation = '重点推荐'
  AND live_fit >= 0.80
ORDER BY selection_score DESC;

-- 5. 跨平台角色热度矩阵
SELECT
    heat_rank,
    operator,
    ROUND(cross_platform_heat, 2) AS cross_platform_heat,
    ROUND(bilibili_heat, 2) AS bilibili_heat,
    ROUND(weibo_heat, 2) AS weibo_heat,
    ROUND(cross_platform_consistency, 2) AS consistency,
    ROUND(confidence_score, 2) AS confidence_score,
    data_quality_grade
FROM operator_heat
ORDER BY heat_rank;

-- 6. 高热度但低置信度：优先补采淘宝或其他平台数据
SELECT
    operator,
    ROUND(cross_platform_heat, 2) AS cross_platform_heat,
    ROUND(confidence_score, 2) AS confidence_score,
    ROUND(merch_opportunity_score, 2) AS merch_opportunity_score,
    commerce_validation_status,
    data_quality_grade
FROM operator_heat
WHERE cross_platform_heat >= 55
  AND confidence_score < 70
ORDER BY merch_opportunity_score DESC;

-- 7. 平台分歧：识别单平台爆发与跨平台稳定角色
SELECT
    operator,
    ROUND(bilibili_heat, 2) AS bilibili_heat,
    ROUND(weibo_heat, 2) AS weibo_heat,
    ROUND(ABS(bilibili_heat - weibo_heat), 2) AS platform_gap,
    ROUND(evergreen_score, 2) AS evergreen_score,
    ROUND(viral_potential_score, 2) AS viral_potential
FROM operator_heat
WHERE weibo_role_data_available = 1
ORDER BY platform_gap DESC;

-- 8. 小红书品牌生态快照；统计窗口不同，只做独立观察
SELECT
    snapshot_date,
    window,
    rank AS brand_rank,
    note_count,
    interaction_total,
    ROUND(interaction_per_note, 2) AS interactions_per_note
FROM xiaohongshu_ecosystem
WHERE platform = 'xiaohongshu'
ORDER BY snapshot_date;

-- 9. 淘宝全 IP 自然销量页角色商业信号
SELECT
    commerce_rank,
    operator,
    organic_sku_count,
    ROUND(sales_proxy_min, 2) AS sales_proxy_lower_bound,
    ROUND(median_price, 2) AS median_price,
    ROUND(commercial_heat_score, 2) AS commercial_heat_score,
    ROUND(commerce_confidence_score, 2) AS confidence,
    commerce_data_grade
FROM taobao_role_signals
WHERE taobao_observed = 1
ORDER BY commerce_rank;

-- 10. 内容热但淘宝商业数据不足：下一轮采集优先级
SELECT
    operator,
    ROUND(cross_platform_heat, 2) AS content_heat,
    ROUND(commercial_heat_score, 2) AS commercial_heat,
    ROUND(content_commerce_gap, 2) AS content_commerce_gap,
    business_quadrant,
    ROUND(commercial_validation_priority, 2) AS validation_priority
FROM content_commerce_matrix
ORDER BY commercial_validation_priority DESC
LIMIT 15;

-- 11. 淘宝公开商品品类价格带与销量代理
SELECT
    category,
    COUNT(DISTINCT item_id) AS organic_sku_count,
    ROUND(MIN(price), 2) AS min_price,
    ROUND(AVG(price), 2) AS avg_price,
    ROUND(MAX(price), 2) AS max_price,
    ROUND(SUM(sales_proxy_min), 2) AS displayed_recipient_lower_bound
FROM taobao_public_snapshots
WHERE query_scope = 'market_baseline'
  AND ip_scope = 'arknights'
GROUP BY category
ORDER BY displayed_recipient_lower_bound DESC;

-- 12. 角色商业验证决策看板：JOIN 后的内容、商业与证据风险
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
LIMIT 15;

-- 13. 每名角色的 Top 2 SKU：窗口函数避免全局排名挤压长尾角色
SELECT
    operator,
    operator_sku_rank,
    sku_id,
    category,
    ROUND(selection_score, 2) AS selection_score,
    risk_tier,
    portfolio_role
FROM vw_sku_portfolio_rank
WHERE operator_sku_rank <= 2
ORDER BY selection_score DESC;

-- 14. 品类经营漏斗：使用加权口径而不是简单平均
SELECT
    category,
    sku_count,
    operator_count,
    weighted_conversion_pct,
    weighted_sell_through_pct,
    weighted_return_pct,
    simulated_gross_profit,
    avg_inventory_risk,
    priority_sku_count
FROM vw_category_operations
ORDER BY simulated_gross_profit DESC;

-- 15. 淘宝价格带结构：CTE + CASE WHEN + 条件聚合
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
ORDER BY avg_price;

-- 16. 正版/同人 × 履约方式交叉分析
SELECT
    rights_type,
    fulfillment_type,
    COUNT(DISTINCT item_id) AS sku_count,
    ROUND(AVG(price), 2) AS avg_price,
    ROUND(SUM(sales_proxy_min), 2) AS sales_proxy_lower_bound,
    ROUND(AVG(free_shipping) * 100, 2) AS free_shipping_rate_pct,
    ROUND(AVG(return_insurance) * 100, 2) AS return_insurance_rate_pct
FROM taobao_public_snapshots
WHERE ip_scope = 'arknights'
GROUP BY rights_type, fulfillment_type
ORDER BY sales_proxy_lower_bound DESC;

-- 17. 数据质量审计：确认多少商品能进入固定 SKU 时间序列
SELECT
    listing_quality_status,
    COUNT(*) AS listing_count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS listing_share_pct,
    SUM(trackable_for_timeseries) AS trackable_count
FROM vw_taobao_listing_quality
GROUP BY listing_quality_status
ORDER BY listing_count DESC;

-- 18. 市场集中度：计算销量代理 Top 10 占比
WITH ranked AS (
    SELECT
        item_id,
        sales_proxy_min,
        ROW_NUMBER() OVER (ORDER BY sales_proxy_min DESC, rank) AS sales_rank,
        SUM(sales_proxy_min) OVER () AS total_sales_proxy
    FROM taobao_public_snapshots
    WHERE query_scope = 'market_baseline'
      AND ip_scope = 'arknights'
), concentration AS (
    SELECT
        SUM(CASE WHEN sales_rank <= 10 THEN sales_proxy_min ELSE 0 END) AS top10_sales_proxy,
        MAX(total_sales_proxy) AS total_sales_proxy
    FROM ranked
)
SELECT
    ROUND(top10_sales_proxy, 2) AS top10_sales_proxy,
    ROUND(total_sales_proxy, 2) AS total_sales_proxy,
    ROUND(100.0 * top10_sales_proxy / NULLIF(total_sales_proxy, 0), 2) AS top10_concentration_pct
FROM concentration;

-- 19. 分品类库存风险队列：每个品类保留风险最高的 3 个 SKU
WITH risk_ranked AS (
    SELECT
        sku_id,
        operator,
        category,
        ROUND(inventory_risk, 2) AS inventory_risk,
        ROUND(return_rate * 100, 2) AS return_rate_pct,
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
ORDER BY inventory_risk DESC;

-- 20. 商业分高于内容分的角色：检查圈层购买力或活动影响
SELECT
    operator,
    content_heat,
    commercial_heat,
    ROUND(commercial_heat - content_heat, 2) AS commerce_over_content,
    organic_sku_count,
    sales_proxy_min,
    recommended_action
FROM vw_role_commercial_dashboard
WHERE taobao_observed = 1
  AND commercial_heat > content_heat
ORDER BY commerce_over_content DESC;

-- 21. B站官号内容类型结构：比较供给规模、触达与互动质量
SELECT
    content_type,
    content_count,
    ROUND(total_views, 0) AS total_views,
    ROUND(median_views, 0) AS median_views,
    ROUND(average_engagement_rate * 100, 2) AS avg_weighted_engagement_pct,
    ROUND(average_intent_rate * 100, 2) AS avg_intent_pct
FROM bilibili_content_type_summary
ORDER BY content_count DESC;

-- 22. 年度内容供给趋势：观察内容规模与角色PV、EP、活动PV结构变化
SELECT
    publication_year,
    content_count,
    operator_pv_count,
    music_ep_count,
    event_pv_count,
    ROUND(total_views, 0) AS total_views,
    ROUND(median_views, 0) AS median_views
FROM bilibili_yearly_summary
ORDER BY publication_year;

-- 23. 角色上线Campaign排名：直接内容与共享宣传内容分开统计
SELECT *
FROM vw_bilibili_campaign_performance
ORDER BY campaign_rank
LIMIT 20;

-- 24. Campaign内容类型组合：识别角色上线传播依赖的内容形态
SELECT
    operator,
    content_type,
    COUNT(DISTINCT bvid) AS content_count,
    ROUND(SUM(view * association_weight), 0) AS weighted_views,
    ROUND(AVG(weighted_engagement_rate) * 100, 2) AS avg_engagement_pct
FROM bilibili_operator_campaign_content
GROUP BY operator, content_type
ORDER BY weighted_views DESC;

-- 25. 直接角色PV与Campaign窗口内容对比：避免共享活动流量冒充角色表现
SELECT
    association_type,
    COUNT(DISTINCT bvid) AS content_count,
    COUNT(DISTINCT operator) AS operator_count,
    ROUND(SUM(view * association_weight), 0) AS weighted_views,
    ROUND(AVG(intent_rate) * 100, 2) AS avg_intent_pct
FROM bilibili_operator_campaign_content
GROUP BY association_type
ORDER BY association_type;
