-- 1. 角色热度排名
SELECT
    heat_rank,
    operator,
    ROUND(heat_score, 2) AS heat_score,
    total_views,
    ROUND(engagement_rate * 100, 2) AS engagement_rate_pct
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

