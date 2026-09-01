from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from arknights_merch_analytics.metrics import build_operator_heat, extract_operator


def test_extract_operator_from_official_title() -> None:
    assert extract_operator("《明日方舟》限定干员「望」前瞻PV") == "望"
    assert extract_operator("《明日方舟》干员『逻各斯』角色PV") == "逻各斯"


def test_build_operator_heat_is_bounded_and_ranked() -> None:
    frame = pd.DataFrame(
        [
            {
                "title": "干员「甲」前瞻PV",
                "published_at": "2026-01-01T00:00:00+00:00",
                "view": 1000,
                "like": 100,
                "coin": 30,
                "favorite": 20,
                "share": 10,
                "reply": 20,
                "danmaku": 15,
            },
            {
                "title": "干员「乙」前瞻PV",
                "published_at": "2026-01-01T00:00:00+00:00",
                "view": 500,
                "like": 20,
                "coin": 5,
                "favorite": 3,
                "share": 1,
                "reply": 2,
                "danmaku": 2,
            },
        ]
    )
    output = build_operator_heat(frame, as_of=datetime(2026, 2, 1, tzinfo=timezone.utc))
    assert output["heat_score"].between(0, 100).all()
    assert output.iloc[0]["operator"] == "甲"
    assert output.iloc[0]["heat_rank"] == 1

