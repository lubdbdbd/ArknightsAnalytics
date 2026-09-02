from __future__ import annotations

import pandas as pd

from arknights_merch_analytics.survey import (
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
