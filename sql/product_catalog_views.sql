DROP VIEW IF EXISTS vw_product_master_health;
DROP VIEW IF EXISTS vw_public_listing_quality;
DROP VIEW IF EXISTS vw_product_maintenance_queue;
DROP VIEW IF EXISTS vw_product_category_coverage;

CREATE INDEX IF NOT EXISTS idx_product_internal_operator_category
ON product_catalog_internal(operator, category);

CREATE INDEX IF NOT EXISTS idx_product_internal_spu_sku
ON product_catalog_internal(spu_code, sku_code);

CREATE INDEX IF NOT EXISTS idx_product_public_priority_quality
ON product_catalog_public(maintenance_priority, data_quality_score);

CREATE INDEX IF NOT EXISTS idx_product_public_rights_category
ON product_catalog_public(rights_type, category);

CREATE INDEX IF NOT EXISTS idx_product_public_operator_category
ON product_catalog_public(operator, category);

CREATE INDEX IF NOT EXISTS idx_product_change_log_entity
ON product_change_log(entity_type, entity_id, event_at);

CREATE VIEW vw_product_master_health AS
SELECT
    category,
    COUNT(DISTINCT spu_code) AS spu_count,
    COUNT(DISTINCT sku_code) AS sku_count,
    ROUND(AVG(required_field_completeness) * 100, 2) AS completeness_pct,
    SUM(rule_issue_count) AS rule_issue_count,
    ROUND(AVG(data_quality_score), 2) AS average_quality_score
FROM product_catalog_internal
GROUP BY category;

CREATE VIEW vw_public_listing_quality AS
SELECT
    rights_type,
    maintenance_priority,
    COUNT(*) AS listing_count,
    ROUND(AVG(data_quality_score), 2) AS average_quality_score,
    SUM(operator_unassigned) AS operator_unassigned_count,
    SUM(fulfillment_unknown) AS fulfillment_unknown_count,
    SUM(price_outlier) AS price_outlier_count
FROM product_catalog_public
GROUP BY rights_type, maintenance_priority;

CREATE VIEW vw_product_maintenance_queue AS
SELECT
    external_sku_id,
    operator,
    category,
    rights_type,
    list_price,
    data_quality_score,
    data_quality_grade,
    maintenance_priority,
    maintenance_action,
    source_url,
    snapshot_at
FROM product_maintenance_queue
ORDER BY maintenance_priority, data_quality_score, external_sku_id;

CREATE VIEW vw_product_category_coverage AS
SELECT
    category,
    internal_spu_count,
    internal_sku_count,
    public_listing_count,
    official_listing_count,
    ROUND(official_listing_share * 100, 2) AS official_listing_share_pct,
    ROUND(internal_price_median, 2) AS internal_price_median,
    ROUND(public_price_median, 2) AS public_price_median,
    ROUND(market_price_gap_pct * 100, 2) AS market_price_gap_pct,
    maintenance_queue_count,
    category_action
FROM product_category_health
ORDER BY official_listing_count, public_listing_count DESC;
