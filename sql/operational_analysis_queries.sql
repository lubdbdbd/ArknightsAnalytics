-- 1. 多源角色需求决策榜：优先查看证据充分且对权重不敏感的角色
SELECT *
FROM vw_operator_demand_decision_board
ORDER BY demand_rank;

-- 2. 内容热、问卷弱：防止把传播热度直接等同于购买需求
SELECT operator, content_signal, survey_signal, scenario_rank_range, decision_note
FROM operator_demand_fusion
WHERE content_signal >= 70 AND COALESCE(survey_signal, 0) < 45
ORDER BY content_signal DESC;

-- 3. 问卷偏好强但缺少正版淘宝样本：形成下一轮采集清单
SELECT operator, survey_signal, organic_sku_count, decision_note
FROM operator_demand_fusion
WHERE survey_signal >= 70 AND commerce_signal IS NULL
ORDER BY survey_signal DESC;

-- 4. 七类正版周边价格梯度与公开市场中位价
SELECT *
FROM vw_category_price_decision_board
ORDER BY category_demand_score DESC;

-- 5. 角色×品类组合：只把样本量足够的高分组合送入概念测试
SELECT operator, category, respondent_count, portfolio_score, acceptable_price_median,
       high_intent_share, portfolio_action
FROM operator_category_portfolio
WHERE respondent_count >= 5
ORDER BY portfolio_score DESC
LIMIT 30;

-- 6. ABC-XYZ库存组合与销售贡献
SELECT *
FROM vw_erp_abc_xyz_portfolio
ORDER BY abc_xyz_class;

-- 7. AX核心稳定SKU：滚动补货
SELECT sku_id, operator, category, net_sales_after_refund, demand_cv,
       days_of_inventory, gmroi, operating_action
FROM erp_sku_diagnostics
WHERE abc_xyz_class = 'AX'
ORDER BY net_sales_after_refund DESC;

-- 8. AZ核心波动SKU：小批量高频补货
SELECT sku_id, operator, category, net_sales_after_refund, demand_cv,
       stockout_rate, operating_action
FROM erp_sku_diagnostics
WHERE abc_xyz_class = 'AZ'
ORDER BY net_sales_after_refund DESC;

-- 9. 补货预算与建议采购量
SELECT *
FROM vw_erp_replenishment_budget
ORDER BY replenishment_priority;

-- 10. 售后80%核心原因
SELECT *
FROM vw_erp_after_sales_pareto
WHERE pareto_priority = '核心原因'
ORDER BY cumulative_case_share_pct;

-- 11. 品类收入、毛利、退货、缺货和库存天数联合诊断
SELECT *
FROM vw_erp_category_operating_health
ORDER BY gross_profit DESC;

-- 12. 每日订单、收入、满足率和7日滚动售后趋势
SELECT *
FROM vw_erp_daily_rolling_kpis
ORDER BY date;
