from __future__ import annotations

import pandas as pd

from arknights_merch_analytics.tracking import (
    build_sku_timeseries_metrics,
    build_tracking_registry,
)


def _listing_rows() -> pd.DataFrame:
    shared = {
        "item_id": "1001",
        "target_operator": "新约能天使",
        "operator_mentions": "新约能天使",
        "category": "亚克力立牌",
        "raw_text": "明日方舟 新约能天使 亚克力立牌",
        "url": "https://item.taobao.com/item.htm?id=1001",
        "query": "明日方舟 新约能天使 周边",
        "query_scope": "targeted",
        "target_relevance": 1.0,
        "ip_scope": "arknights",
        "rights_type": "官方/授权",
        "fulfillment_type": "现货/在售",
        "sales_proxy_censored": True,
    }
    return pd.DataFrame(
        [
            {
                **shared,
                "snapshot_at": "2026-09-02T12:00:00+08:00",
                "rank": 5,
                "price": 39.0,
                "sales_proxy_min": 100.0,
            },
            {
                **shared,
                "snapshot_at": "2026-09-09T12:00:00+08:00",
                "rank": 3,
                "price": 39.0,
                "sales_proxy_min": 120.0,
            },
        ]
    )


def test_build_fixed_sku_registry_and_timeseries() -> None:
    listings = _listing_rows()
    registry = build_tracking_registry(listings)
    metrics = build_sku_timeseries_metrics(listings)

    assert len(registry) == 1
    assert registry.iloc[0]["tracking_status"] == "tracking_active"
    assert registry.iloc[0]["next_capture_due"] == "2026-09-16"
    assert metrics.iloc[0]["sales_proxy_delta"] == 20.0
    assert metrics.iloc[0]["rank_improvement"] == 2
    assert metrics.iloc[0]["lifecycle_signal"] == "growth_observed"
    assert metrics.iloc[0]["timeseries_evidence_grade"] == "C"


def test_single_snapshot_is_only_baseline() -> None:
    listings = _listing_rows().head(1)
    metrics = build_sku_timeseries_metrics(listings)
    assert metrics.iloc[0]["lifecycle_signal"] == "baseline_pending_recapture"
    assert metrics.iloc[0]["timeseries_evidence_grade"] == "D"
