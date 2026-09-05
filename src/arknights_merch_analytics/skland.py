from __future__ import annotations

import time
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests


SKLAND_STRATEGY_ITEMS_ENDPOINT = "https://strategy.skland.com/api/resources/items"
SKLAND_ARTICLE_URL = "https://www.skland.com/article?id={item_id}"


def is_operator_title_match(operator: str, title: str, operator_pool: Iterable[str]) -> bool:
    normalized_operator = operator.casefold().strip()
    normalized_title = title.casefold().strip()
    if not normalized_operator or normalized_operator not in normalized_title:
        return False
    longer_matches = [
        value
        for value in operator_pool
        if len(value) > len(operator) and operator in value and value.casefold() in normalized_title
    ]
    if longer_matches:
        return False
    if len(operator) > 1:
        return True
    escaped = re.escape(operator)
    explicit_patterns = (
        rf"[【「『\[]\s*{escaped}\s*[】」』\]]",
        rf"干员\s*{escaped}(?:\s|$|[，。：:、—-])",
        rf"{escaped}\s*(?:干员|攻略|测评|速评|培养|专精|模组|作业|实战|解析)",
    )
    return any(re.search(pattern, title, flags=re.IGNORECASE) for pattern in explicit_patterns)


def collect_skland_strategy_search(
    operators: Iterable[str],
    page_size: int = 20,
    sorts: tuple[str, ...] = ("hot", "time"),
    request_interval_seconds: float = 0.15,
    session: requests.Session | None = None,
) -> pd.DataFrame:
    """Collect public search-result snapshots without opening articles.

    The strategy portal exposes aggregate engagement fields in its public search
    endpoint. The collector deliberately avoids the article-view PUT endpoint so
    data collection does not increment view counters.
    """

    if page_size <= 0:
        raise ValueError("page_size must be positive")
    unsupported = set(sorts).difference({"hot", "time"})
    if unsupported:
        raise ValueError(f"Unsupported sort values: {sorted(unsupported)}")

    client = session or requests.Session()
    client.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (ArknightsAnalytics/0.2; public research snapshot)",
            "Referer": "https://strategy.skland.com/",
        }
    )
    operator_pool = sorted({str(value).strip() for value in operators if str(value).strip()})
    snapshot_at = datetime.now().astimezone().isoformat(timespec="seconds")
    rows: list[dict[str, object]] = []
    for operator in operator_pool:
        keyword = operator
        for sort in sorts:
            response = client.get(
                SKLAND_STRATEGY_ITEMS_ENDPOINT,
                params={"keyword": keyword, "current": 1, "pageSize": min(page_size, 20), "sort": sort},
                timeout=20,
            )
            if response.status_code in {412, 429}:
                raise RuntimeError(
                    f"Skland strategy endpoint returned HTTP {response.status_code}; stop collection."
                )
            response.raise_for_status()
            payload = response.json()
            if payload.get("code") != 0:
                raise RuntimeError(
                    f"Skland strategy API error: {payload.get('code')} {payload.get('message')}"
                )
            items = payload.get("data", {}).get("list") or []
            for rank, aggregate in enumerate(items, start=1):
                item = aggregate.get("item") or {}
                item_rts = aggregate.get("itemRts") or {}
                user = aggregate.get("user") or {}
                title = str(aggregate.get("title") or "").strip()
                item_id = str(item.get("id") or "").strip()
                rows.append(
                    {
                        "snapshot_at": snapshot_at,
                        "query_operator": operator,
                        "keyword": keyword,
                        "sort": sort,
                        "result_rank": rank,
                        "resource_id": aggregate.get("id"),
                        "item_id": item_id,
                        "title": title,
                        "posted_at": pd.to_datetime(
                            aggregate.get("postedAt"), unit="ms", utc=True, errors="coerce"
                        ).isoformat(),
                        "author_id": str(user.get("id") or ""),
                        "author_name": str(user.get("nickname") or ""),
                        "viewed": int(item_rts.get("viewed") or 0),
                        "video_viewed": int(item_rts.get("videoViewed") or 0),
                        "liked": int(item_rts.get("liked") or 0),
                        "collected": int(item_rts.get("collected") or 0),
                        "reposted": int(item_rts.get("reposted") or 0),
                        "commented": int(item_rts.get("commented") or 0),
                        "direct_name_match": is_operator_title_match(operator, title, operator_pool),
                        "source_url": SKLAND_ARTICLE_URL.format(item_id=item_id),
                        "source_api": SKLAND_STRATEGY_ITEMS_ENDPOINT,
                        "source_scope": "skland_strategy_public_search_top20",
                        "is_simulated": False,
                    }
                )
            if request_interval_seconds:
                time.sleep(request_interval_seconds)
    return pd.DataFrame(rows)


def build_skland_operator_summary(snapshot: pd.DataFrame) -> pd.DataFrame:
    if snapshot.empty:
        return pd.DataFrame(
            columns=[
                "operator",
                "skland_content_count",
                "skland_total_views",
                "skland_median_views",
                "skland_total_engagement",
                "skland_interaction_rate",
                "skland_top_content_title",
                "skland_top_content_views",
            ]
        )
    required = {
        "query_operator",
        "item_id",
        "title",
        "viewed",
        "liked",
        "collected",
        "commented",
        "reposted",
        "direct_name_match",
    }
    missing = required.difference(snapshot.columns)
    if missing:
        raise ValueError(f"Missing Skland snapshot columns: {sorted(missing)}")
    relevant = snapshot.loc[snapshot["direct_name_match"].astype(bool)].copy()
    if relevant.empty:
        return pd.DataFrame(
            columns=[
                "operator",
                "skland_content_count",
                "skland_total_views",
                "skland_median_views",
                "skland_total_engagement",
                "skland_interaction_rate",
                "skland_top_content_title",
                "skland_top_content_views",
            ]
        )
    numeric_columns = ["viewed", "liked", "collected", "commented", "reposted"]
    for column in numeric_columns:
        relevant[column] = pd.to_numeric(relevant[column], errors="coerce").fillna(0)
    relevant = relevant.sort_values(
        ["query_operator", "viewed", "item_id"], ascending=[True, False, True]
    ).drop_duplicates(["query_operator", "item_id"])
    relevant["engagement"] = (
        relevant["liked"]
        + 2 * relevant["collected"]
        + 2 * relevant["commented"]
        + 3 * relevant["reposted"]
    )
    relevant["interaction_rate"] = relevant["engagement"] / relevant["viewed"].clip(lower=1)
    summary = (
        relevant.groupby("query_operator", as_index=False)
        .agg(
            skland_content_count=("item_id", "nunique"),
            skland_total_views=("viewed", "sum"),
            skland_median_views=("viewed", "median"),
            skland_total_engagement=("engagement", "sum"),
            skland_interaction_rate=("interaction_rate", "mean"),
        )
        .rename(columns={"query_operator": "operator"})
    )
    top = relevant.drop_duplicates("query_operator")[["query_operator", "title", "viewed"]].rename(
        columns={
            "query_operator": "operator",
            "title": "skland_top_content_title",
            "viewed": "skland_top_content_views",
        }
    )
    return summary.merge(top, on="operator", how="left").sort_values(
        ["skland_total_views", "skland_content_count"], ascending=False
    )


def export_skland_snapshot(snapshot: pd.DataFrame, raw_path: Path, summary_path: Path) -> None:
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot.to_csv(raw_path, index=False, encoding="utf-8-sig")
    build_skland_operator_summary(snapshot).to_csv(summary_path, index=False, encoding="utf-8-sig")
