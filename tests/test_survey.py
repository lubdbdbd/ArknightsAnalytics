from __future__ import annotations

import pandas as pd

from arknights_merch_analytics.survey import (
    build_survey_barrier_summary,
    build_survey_price_summary,
    build_survey_segment_summary,
    build_survey_summary,
    validate_survey_responses,
)


def test_survey_quality_gate_and_summary() -> None:
    base = {
        "submitted_at": "2026-09-02T12:00:00+08:00",
        "consent": 1,
        "response_source": "community_recruitment",
        "completion_seconds": 120,
        "attention_check": "通过",
        "player_tenure_months": 48,
        "monthly_merch_budget": 200,
        "has_purchased_merch": 1,
        "operator": "新约能天使",
        "category": "亚克力立牌",
        "purchase_intent": 5,
        "acceptable_price": 49,
        "channel": "淘宝",
        "limited_preference": 4,
    }
    responses = pd.DataFrame(
        [
            {**base, "response_id": "R-001", "respondent_id": "U-001"},
            {
                **base,
                "response_id": "TEST-001",
                "respondent_id": "U-002",
                "completion_seconds": 10,
            },
        ]
    )
    valid, audit = validate_survey_responses(responses)
    summary = build_survey_summary(valid)

    assert len(valid) == 1
    assert audit["valid"].tolist() == [True, False]
    assert "too_fast" in audit.iloc[1]["exclusion_reason"]
    assert summary.iloc[0]["respondent_count"] == 1
    assert summary.iloc[0]["survey_evidence_grade"] == "D"


def test_survey_segmentation_barriers_and_price_ladder() -> None:
    base = {
        "submitted_at": "2026-09-03T12:00:00+08:00",
        "consent": 1,
        "response_source": "community_recruitment",
        "completion_seconds": 240,
        "attention_check": "通过",
        "player_tenure_months": 60,
        "monthly_merch_budget": 300,
        "has_purchased_merch": 1,
        "operator": "新约能天使",
        "category": "亚克力立牌",
        "purchase_intent": 5,
        "acceptable_price": 59,
        "channel": "官方商城",
        "limited_preference": 4,
        "activity_days_30d": 25,
        "annual_merch_spend": 1800,
        "purchase_frequency_12m": 6,
        "purchase_barrier": "价格偏高|预售周期过长",
        "preorder_tolerance_days": 45,
        "price_too_cheap": 19,
        "price_good_value": 39,
        "price_expensive": 69,
        "price_too_expensive": 99,
        "concept_appeal": 5,
        "concept_uniqueness": 4,
        "authenticity_importance": 5,
        "design_importance": 5,
        "practicality_importance": 3,
    }
    responses = pd.DataFrame(
        [
            {**base, "response_id": "R-101", "respondent_id": "U-101"},
            {
                **base,
                "response_id": "R-102",
                "respondent_id": "U-102",
                "has_purchased_merch": 0,
                "annual_merch_spend": 0,
                "purchase_frequency_12m": 0,
                "purchase_barrier": "价格偏高",
                "purchase_intent": 4,
            },
        ]
    )
    valid, audit = validate_survey_responses(responses)
    segments = build_survey_segment_summary(valid)
    barriers = build_survey_barrier_summary(valid)
    prices = build_survey_price_summary(valid)

    assert audit["valid"].all()
    assert set(valid["user_segment"]) == {"core_buyer", "potential_buyer"}
    assert segments["respondent_count"].sum() == 2
    assert barriers.iloc[0]["purchase_barrier"] == "价格偏高"
    assert barriers.iloc[0]["respondent_share"] == 1.0
    assert prices.iloc[0]["directional_price_floor"] == 39
    assert prices.iloc[0]["directional_price_ceiling"] == 69


def test_survey_rejects_inconsistent_price_ladder() -> None:
    response = pd.DataFrame(
        [
            {
                "response_id": "R-201",
                "respondent_id": "U-201",
                "submitted_at": "2026-09-03T12:00:00+08:00",
                "consent": 1,
                "response_source": "pilot",
                "completion_seconds": 180,
                "attention_check": "通过",
                "player_tenure_months": 48,
                "monthly_merch_budget": 200,
                "has_purchased_merch": 1,
                "operator": "新约能天使",
                "category": "亚克力立牌",
                "purchase_intent": 5,
                "acceptable_price": 59,
                "channel": "淘宝",
                "limited_preference": 4,
                "price_too_cheap": 39,
                "price_good_value": 29,
                "price_expensive": 69,
                "price_too_expensive": 99,
            }
        ]
    )
    valid, audit = validate_survey_responses(response)

    assert valid.empty
    assert "invalid_price_ladder" in audit.iloc[0]["exclusion_reason"]
