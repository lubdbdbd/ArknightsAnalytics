from __future__ import annotations

import pandas as pd

from arknights_merch_analytics.skland import build_skland_operator_summary, is_operator_title_match


def test_skland_summary_deduplicates_sorts_and_filters_false_matches() -> None:
    snapshot = pd.DataFrame(
        [
            {
                "query_operator": "能天使",
                "item_id": "1",
                "title": "能天使干员攻略",
                "viewed": 100,
                "liked": 10,
                "collected": 5,
                "commented": 2,
                "reposted": 1,
                "direct_name_match": True,
            },
            {
                "query_operator": "能天使",
                "item_id": "1",
                "title": "能天使干员攻略",
                "viewed": 100,
                "liked": 10,
                "collected": 5,
                "commented": 2,
                "reposted": 1,
                "direct_name_match": True,
            },
            {
                "query_operator": "能天使",
                "item_id": "2",
                "title": "狙击干员攻略",
                "viewed": 1000,
                "liked": 100,
                "collected": 50,
                "commented": 20,
                "reposted": 10,
                "direct_name_match": False,
            },
        ]
    )
    summary = build_skland_operator_summary(snapshot)
    row = summary.iloc[0]
    assert row["skland_content_count"] == 1
    assert row["skland_total_views"] == 100
    assert row["skland_top_content_title"] == "能天使干员攻略"


def test_operator_match_rejects_alias_collisions_and_single_character_noise() -> None:
    operators = ["能天使", "新约能天使", "W", "年"]
    assert not is_operator_title_match("能天使", "新约能天使或成最大赢家", operators)
    assert is_operator_title_match("新约能天使", "【新约能天使】培养攻略", operators)
    assert not is_operator_title_match("W", "36w总伤害测试", operators)
    assert is_operator_title_match("W", "六星干员攻略【W】", operators)
    assert not is_operator_title_match("年", "4.5周年活动攻略", operators)
    assert is_operator_title_match("年", "【年】模组测评", operators)
