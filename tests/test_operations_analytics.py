from __future__ import annotations

import pandas as pd

from arknights_merch_analytics.operations_analytics import (
    build_after_sales_pareto,
    build_category_price_architecture,
    build_erp_replenishment_plan,
    build_operator_demand_fusion,
)


def test_demand_fusion_does_not_treat_missing_commerce_as_zero() -> None:
    heat = pd.DataFrame(
        [{"operator": "甲", "cross_platform_heat": 80, "merch_opportunity_score": 70, "confidence_score": 80}]
    )
    survey = pd.DataFrame(
        [{"operator": "甲", "preference_mentions": 20, "weighted_preference_score": 40, "first_choice_count": 10, "mention_share": 0.2}]
    )
    skland = pd.DataFrame(
        [{"operator": "甲", "skland_content_count": 10, "skland_total_views": 1000, "skland_total_engagement": 100}]
    )
    commerce = pd.DataFrame(
        [{"operator": "甲", "taobao_observed": False, "commercial_heat_score": 0, "commerce_confidence_score": 10}]
    )
    demand, sensitivity = build_operator_demand_fusion(heat, survey, skland, commerce)
    assert pd.isna(demand.loc[0, "commerce_signal"])
    assert demand.loc[0, "evidence_source_count"] == 3
    assert set(sensitivity["scenario"]) == {
        "balanced",
        "content_led",
        "survey_led",
        "community_led",
        "commerce_led",
    }


def test_price_ladder_is_monotonic_and_official_only() -> None:
    summary = pd.DataFrame(
        [{"category": "亚克力制品", "respondent_count": 30, "buyer_share": 0.5, "purchase_intent_mean": 4.0, "high_intent_share": 0.5, "selection_share": 0.3}]
    )
    prices = pd.DataFrame(
        [
            {"response_id": str(index), "category": "亚克力制品", "price_midpoint_proxy": value, "is_simulated": False}
            for index, value in enumerate([20, 30, 40, 50, 60])
        ]
    )
    taobao = pd.DataFrame(
        [
            {"item_id": "1", "category": "亚克力制品", "price": 39, "sales_proxy_min": 10, "rights_type": "官方/授权", "is_simulated": False},
            {"item_id": "2", "category": "亚克力制品", "price": 9, "sales_proxy_min": 999, "rights_type": "同人原创", "is_simulated": False},
        ]
    )
    skus = pd.DataFrame(
        [{"sku_id": "s1", "category": "亚克力制品", "price": 48, "unit_cost": 16}]
    )
    result = build_category_price_architecture(summary, prices, taobao, skus).iloc[0]
    assert result["recommended_entry_price"] <= result["recommended_core_price"]
    assert result["recommended_core_price"] <= result["recommended_premium_price"]
    assert result["observed_official_sku_count"] == 1
    assert result["observed_market_price_median"] == 39


def test_replenishment_quantity_is_nonnegative_and_simulated() -> None:
    skus = pd.DataFrame(
        [{"sku_id": "s1", "operator": "甲", "category": "吧唧（徽章）", "purchase_lead_time_days": 10, "unit_cost": 5}]
    )
    inventory = pd.DataFrame(
        [
            {"snapshot_date": f"2026-01-{day:02d}", "sku_id": "s1", "requested_sales_units": 2, "available_stock": 3, "closing_stock": 3, "locked_stock": 0}
            for day in range(1, 29)
        ]
    )
    purchase_orders = pd.DataFrame(
        [{"sku_id": "s1", "purchase_status": "open", "quantity_ordered": 5, "quantity_received": 0}]
    )
    result = build_erp_replenishment_plan(skus, inventory, purchase_orders)
    assert result.loc[0, "suggested_po_quantity"] >= 0
    assert result.loc[0, "is_simulated"]


def test_after_sales_pareto_reaches_one_and_remains_simulated() -> None:
    cases = pd.DataFrame(
        [
            {"case_id": "1", "sku_id": "s1", "reason": "划痕", "units": 1, "refund_amount": 10, "requested_at": "2026-01-01", "resolved_at": "2026-01-03"},
            {"case_id": "2", "sku_id": "s1", "reason": "破损", "units": 1, "refund_amount": 10, "requested_at": "2026-01-01", "resolved_at": "2026-01-04"},
        ]
    )
    skus = pd.DataFrame([{"sku_id": "s1", "category": "亚克力制品", "operator": "甲"}])
    result = build_after_sales_pareto(cases, skus)
    assert round(result["cumulative_case_share"].iloc[-1], 6) == 1.0
    assert result["is_simulated"].all()
