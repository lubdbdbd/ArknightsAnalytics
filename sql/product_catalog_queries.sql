-- 1. 内部商品主数据健康度：检查各品类完整率与规则异常
SELECT *
FROM vw_product_master_health
ORDER BY completeness_pct, rule_issue_count DESC, category;

-- 2. 待维护商品队列：先处理高优先级和低质量记录
SELECT external_sku_id, operator, category, rights_type, list_price,
       data_quality_score, maintenance_priority, maintenance_action, source_url
FROM vw_product_maintenance_queue
ORDER BY maintenance_priority, data_quality_score, external_sku_id;

-- 3. 授权核验积压：按品类确定补证顺序
SELECT category, COUNT(*) AS pending_rights_count,
       ROUND(AVG(data_quality_score), 2) AS average_quality_score
FROM product_catalog_public
WHERE rights_unverified = 1
GROUP BY category
ORDER BY pending_rights_count DESC, category;

-- 4. 角色未归因清单：回看标题和搜索词补充角色标签
SELECT external_sku_id, product_title, query, category, source_url
FROM product_catalog_public
WHERE operator_unassigned = 1
ORDER BY category, external_sku_id;

-- 5. 履约信息缺失清单：补充现货、预售或补款状态
SELECT external_sku_id, operator, category, fulfillment_type,
       product_title, source_url
FROM product_catalog_public
WHERE fulfillment_unknown = 1
ORDER BY operator, category;

-- 6. 价格异常复核：异常只触发人工检查，不直接删除
SELECT external_sku_id, operator, category, list_price,
       product_title, source_url
FROM product_catalog_public
WHERE price_outlier = 1
ORDER BY category, list_price DESC;

-- 7. 内部规划价与公开市场价差：为价格带复核提供方向
SELECT category, internal_price_median, public_price_median,
       market_price_gap_pct, category_action
FROM product_category_health
WHERE internal_price_median IS NOT NULL
  AND public_price_median IS NOT NULL
ORDER BY ABS(market_price_gap_pct) DESC;

-- 8. 重复采集记录：合并同一外部商品的多查询快照
SELECT external_sku_id, product_title, capture_count, snapshot_at, source_url
FROM product_catalog_public
WHERE duplicate_capture = 1
ORDER BY capture_count DESC, external_sku_id;

-- 9. 各品类正版样本覆盖率：决定下一轮公开商品补采方向
SELECT *
FROM vw_product_category_coverage
ORDER BY official_listing_share_pct, official_listing_count, public_listing_count DESC;

-- 10. 数据质量等级分布：监控可入库比例和维护工作量
SELECT data_quality_grade, maintenance_priority,
       COUNT(*) AS listing_count,
       ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS listing_share_pct
FROM product_catalog_public
GROUP BY data_quality_grade, maintenance_priority
ORDER BY maintenance_priority, data_quality_grade;

-- 11. 商品变更审计：区分模拟内部建档与真实公开快照观测
SELECT event_at, entity_type, change_type, source, is_simulated,
       COUNT(*) AS event_count
FROM product_change_log
GROUP BY event_at, entity_type, change_type, source, is_simulated
ORDER BY event_at DESC, entity_type, source;
