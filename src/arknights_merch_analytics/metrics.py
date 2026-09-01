from __future__ import annotations

import re
from datetime import datetime

import numpy as np
import pandas as pd


OPERATOR_PATTERNS = (
    re.compile(r"(?:限定)?干员[「『“\"]([^」』”\"]+)[」』”\"]"),
    re.compile(r"角色[「『“\"]([^」』”\"]+)[」』”\"]"),
)


def extract_operator(title: str) -> str | None:
    for pattern in OPERATOR_PATTERNS:
        match = pattern.search(str(title))
        if match:
            return match.group(1).strip()
    return None


def percentile_score(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce").fillna(0)
    if numeric.nunique() <= 1:
        return pd.Series(np.full(len(numeric), 50.0), index=numeric.index)
    return numeric.rank(method="average", pct=True) * 100


def build_operator_heat(videos: pd.DataFrame, as_of: datetime | None = None) -> pd.DataFrame:
    required = {
        "title",
        "published_at",
        "view",
        "like",
        "coin",
        "favorite",
        "share",
        "reply",
        "danmaku",
    }
    missing = required.difference(videos.columns)
    if missing:
        raise ValueError(f"Missing video columns: {sorted(missing)}")

    frame = videos.copy()
    frame["operator"] = frame["title"].map(extract_operator)
    frame = frame[frame["operator"].notna()].copy()
    if frame.empty:
        raise ValueError("No operator names could be extracted from video titles")

    timestamp = pd.Timestamp(as_of or datetime.now().astimezone())
    published = pd.to_datetime(frame["published_at"], utc=True).dt.tz_convert(timestamp.tz)
    age_days = ((timestamp - published).dt.total_seconds() / 86400).clip(lower=1)
    view = pd.to_numeric(frame["view"], errors="coerce").fillna(0).clip(lower=1)
    frame["views_per_day"] = view / age_days
    frame["engagement_rate"] = (
        pd.to_numeric(frame["like"], errors="coerce").fillna(0)
        + 2 * pd.to_numeric(frame["coin"], errors="coerce").fillna(0)
        + 2 * pd.to_numeric(frame["favorite"], errors="coerce").fillna(0)
        + 3 * pd.to_numeric(frame["share"], errors="coerce").fillna(0)
        + 2 * pd.to_numeric(frame["reply"], errors="coerce").fillna(0)
        + 0.5 * pd.to_numeric(frame["danmaku"], errors="coerce").fillna(0)
    ) / view
    frame["favorite_rate"] = pd.to_numeric(frame["favorite"], errors="coerce").fillna(0) / view
    frame["share_rate"] = pd.to_numeric(frame["share"], errors="coerce").fillna(0) / view
    frame["velocity_score"] = percentile_score(np.log1p(frame["views_per_day"]))
    frame["engagement_score"] = percentile_score(frame["engagement_rate"])
    frame["favorite_score"] = percentile_score(frame["favorite_rate"])
    frame["share_score"] = percentile_score(frame["share_rate"])
    frame["heat_score"] = (
        0.40 * frame["velocity_score"]
        + 0.30 * frame["engagement_score"]
        + 0.15 * frame["favorite_score"]
        + 0.15 * frame["share_score"]
    )

    output = (
        frame.groupby("operator", as_index=False)
        .agg(
            video_count=("title", "count"),
            total_views=("view", "sum"),
            views_per_day=("views_per_day", "sum"),
            engagement_rate=("engagement_rate", "mean"),
            favorite_rate=("favorite_rate", "mean"),
            share_rate=("share_rate", "mean"),
            heat_score=("heat_score", "mean"),
        )
        .sort_values(["heat_score", "total_views"], ascending=False)
        .reset_index(drop=True)
    )
    output["heat_rank"] = np.arange(1, len(output) + 1)
    return output


def build_sku_recommendations(erp: pd.DataFrame) -> pd.DataFrame:
    frame = erp.copy()
    frame["gross_margin_rate"] = (frame["price"] - frame["unit_cost"]) / frame["price"]
    frame["sell_through_rate"] = frame["sold_units"] / frame["launch_inventory"].clip(lower=1)
    frame["conversion_rate"] = frame["orders"] / frame["page_views"].clip(lower=1)
    frame["return_rate"] = frame["return_units"] / frame["sold_units"].clip(lower=1)
    frame["gmv"] = frame["price"] * frame["sold_units"]
    frame["inventory_risk"] = (
        0.55 * (100 - percentile_score(frame["sell_through_rate"]))
        + 0.45 * percentile_score(frame["return_rate"])
    )
    frame["selection_score"] = (
        0.30 * frame["heat_score"]
        + 0.30 * percentile_score(frame["conversion_rate"])
        + 0.20 * percentile_score(frame["gross_margin_rate"])
        + 0.10 * frame["live_fit"] * 100
        - 0.10 * frame["inventory_risk"]
    )
    frame["recommendation"] = pd.cut(
        frame["selection_score"],
        bins=[-np.inf, 45, 65, np.inf],
        labels=["谨慎测试", "常规上架", "重点推荐"],
    ).astype(str)
    return frame.sort_values("selection_score", ascending=False).reset_index(drop=True)

