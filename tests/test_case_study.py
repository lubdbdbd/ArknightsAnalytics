from __future__ import annotations

import pandas as pd

from arknights_merch_analytics.case_study import build_selection_case


def test_selection_case_requires_longitudinal_and_survey_evidence() -> None:
    operator = "新约能天使"
    content = pd.DataFrame(
        {
            "operator": [operator],
            "cross_platform_heat": [71.35],
            "intent_score": [82.67],
        }
    )
    targeted = pd.DataFrame(
        {
            "operator": [operator],
            "search_precision": [0.70],
            "sales_proxy_min_total": [249.0],
        }
    )
    listings = pd.DataFrame(
        {
            "target_operator": [operator],
            "target_relevance": [1.0],
            "category": ["亚克力立牌"],
            "item_id": ["1001"],
            "sales_proxy_min": [100.0],
            "price": [39.0],
            "rights_type": ["官方/授权"],
        }
    )
    sku = pd.DataFrame(
        {
            "operator": [operator],
            "category": ["亚克力立牌"],
            "selection_score": [70.0],
        }
    )

    evidence, categories = build_selection_case(
        operator, content, targeted, listings, sku
    )

    assert evidence["case_status"].eq("conditional_pilot").all()
    assert not evidence.loc[
        evidence["evidence_layer"] == "fixed_sku_timeseries", "gate_passed"
    ].item()
    assert not categories.empty
