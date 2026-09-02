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
