from __future__ import annotations

import re
from datetime import datetime

import numpy as np
import pandas as pd


OPERATOR_PATTERNS = (
    re.compile(r"(?:限定)?干员[「『“\"]([^」』”\"]+)[」』”\"]"),
    re.compile(r"角色[「『“\"]([^」』”\"]+)[」』”\"]"),
)
EXCLUDED_OPERATOR_ENTITIES = {"丰川祥子"}


def extract_operator(title: str) -> str | None:
    for pattern in OPERATOR_PATTERNS:
        match = pattern.search(str(title))
        if match:
            operator = match.group(1).strip()
            return None if operator in EXCLUDED_OPERATOR_ENTITIES else operator
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


def _age_days(values: pd.Series, as_of: datetime | None) -> pd.Series:
    timestamp = pd.Timestamp(as_of or datetime.now().astimezone())
    published = pd.to_datetime(values, utc=True).dt.tz_convert(timestamp.tz)
    return ((timestamp - published).dt.total_seconds() / 86400).clip(lower=1)


def score_bilibili_posts(videos: pd.DataFrame, as_of: datetime | None = None) -> pd.DataFrame:
    frame = videos.copy()
    frame["operator"] = frame["title"].map(extract_operator)
    frame = frame[frame["operator"].notna()].copy()
    if frame.empty:
        return frame
    age_days = _age_days(frame["published_at"], as_of)
    view = pd.to_numeric(frame["view"], errors="coerce").fillna(0).clip(lower=1)
    like = pd.to_numeric(frame["like"], errors="coerce").fillna(0)
    coin = pd.to_numeric(frame["coin"], errors="coerce").fillna(0)
    favorite = pd.to_numeric(frame["favorite"], errors="coerce").fillna(0)
    reply = pd.to_numeric(frame["reply"], errors="coerce").fillna(0)
    danmaku = pd.to_numeric(frame["danmaku"], errors="coerce").fillna(0)
    frame["reach_score"] = percentile_score(np.log1p(view))
    frame["momentum_score"] = percentile_score(np.log1p(view / age_days))
    frame["engagement_rate"] = (like + 2 * coin + 2 * favorite + 1.5 * reply + 0.5 * danmaku) / view
    frame["engagement_score"] = percentile_score(frame["engagement_rate"])
    frame["intent_rate"] = (2 * favorite + coin) / view
    frame["intent_score"] = percentile_score(frame["intent_rate"])
    frame["discussion_rate"] = (reply + danmaku) / view
    frame["discussion_score"] = percentile_score(frame["discussion_rate"])
    frame["platform_heat_score"] = (
        0.25 * frame["reach_score"]
        + 0.25 * frame["momentum_score"]
        + 0.25 * frame["engagement_score"]
        + 0.15 * frame["intent_score"]
        + 0.10 * frame["discussion_score"]
    )
    frame["platform"] = "bilibili"
    return frame


def _weibo_operator_mentions(text: str, roster: list[str]) -> list[str]:
    value = str(text)
    explicit = re.findall(r"(?:干员)?[「『“\"]([^」』”\"]+)[」』”\"]", value)
    explicit.extend(re.findall(r"//\s*([^\s，。；：、]{1,16})", value))
    matches = [name for name in roster if name in explicit]
    if matches:
        return matches
    direct = [name for name in roster if len(name) >= 2 and name in value]
    return direct[:3] if len(direct) <= 3 else []


def score_weibo_posts(
    posts: pd.DataFrame, roster: list[str], as_of: datetime | None = None
) -> pd.DataFrame:
    if posts.empty:
        return pd.DataFrame()
    expanded: list[dict[str, object]] = []
    for _, row in posts.iterrows():
        for operator in _weibo_operator_mentions(str(row.get("text", "")), roster):
            item = row.to_dict()
            item["operator"] = operator
            expanded.append(item)
    frame = pd.DataFrame(expanded)
    if frame.empty:
        return frame
    repost = pd.to_numeric(frame["repost"], errors="coerce").fillna(0)
    comment = pd.to_numeric(frame["comment"], errors="coerce").fillna(0)
    like = pd.to_numeric(frame["like"], errors="coerce").fillna(0)
    weighted = 2 * repost + 1.5 * comment + like
    age_days = _age_days(frame["published_at"], as_of)
    frame["reach_score"] = percentile_score(np.log1p(weighted))
    frame["momentum_score"] = percentile_score(np.log1p(weighted / age_days))
    frame["engagement_score"] = percentile_score(weighted)
    frame["intent_score"] = percentile_score(repost)
    frame["discussion_score"] = percentile_score(comment)
    frame["platform_heat_score"] = (
        0.30 * frame["reach_score"]
        + 0.25 * frame["momentum_score"]
        + 0.20 * percentile_score(repost)
        + 0.15 * frame["discussion_score"]
        + 0.10 * percentile_score(like)
    )
    frame["platform"] = "weibo"
    return frame


def _aggregate_platform(scored: pd.DataFrame, prefix: str) -> pd.DataFrame:
    if scored.empty:
        return pd.DataFrame(
            columns=[
                "operator",
                f"{prefix}_content_count",
                f"{prefix}_heat",
                f"{prefix}_reach",
                f"{prefix}_momentum",
                f"{prefix}_engagement",
                f"{prefix}_intent",
                f"{prefix}_discussion",
            ]
        )
    ordered = scored.sort_values("platform_heat_score", ascending=False).copy()
    ordered["content_order"] = ordered.groupby("operator").cumcount()
    top = ordered[ordered["content_order"] < 3]
    output = top.groupby("operator", as_index=False).agg(
        **{
            f"{prefix}_content_count": ("platform_heat_score", "count"),
            f"{prefix}_heat": ("platform_heat_score", "mean"),
            f"{prefix}_reach": ("reach_score", "mean"),
            f"{prefix}_momentum": ("momentum_score", "mean"),
            f"{prefix}_engagement": ("engagement_score", "mean"),
            f"{prefix}_intent": ("intent_score", "mean"),
            f"{prefix}_discussion": ("discussion_score", "mean"),
        }
    )
    return output


def build_character_heat_matrix(
    bilibili_posts: pd.DataFrame,
    weibo_posts: pd.DataFrame | None = None,
    as_of: datetime | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    bilibili_scored = score_bilibili_posts(bilibili_posts, as_of=as_of)
    roster = sorted(bilibili_scored["operator"].dropna().unique().tolist())
    weibo_scored = score_weibo_posts(
        weibo_posts if weibo_posts is not None else pd.DataFrame(), roster, as_of=as_of
    )
    bilibili_agg = _aggregate_platform(bilibili_scored, "bilibili")
    weibo_agg = _aggregate_platform(weibo_scored, "weibo")
    matrix = bilibili_agg.merge(weibo_agg, on="operator", how="left")
    matrix["weibo_role_data_available"] = matrix["weibo_heat"].notna()
    matrix["xiaohongshu_role_data_available"] = False
    matrix["weibo_heat_imputed"] = matrix["weibo_heat"].fillna(50.0)
    matrix["cross_platform_heat"] = (
        0.70 * matrix["bilibili_heat"] + 0.30 * matrix["weibo_heat_imputed"]
    )
    for dimension in ("reach", "momentum", "engagement", "intent", "discussion"):
        matrix[f"{dimension}_score"] = (
            0.70 * matrix[f"bilibili_{dimension}"]
            + 0.30 * matrix[f"weibo_{dimension}"].fillna(50.0)
        )
    matrix["cross_platform_consistency"] = np.where(
        matrix["weibo_role_data_available"],
        100 - (matrix["bilibili_heat"] - matrix["weibo_heat"]).abs(),
        np.nan,
    )
    matrix["role_level_platform_coverage"] = (
        1 + matrix["weibo_role_data_available"].astype(int)
    ) / 3
    matrix["confidence_score"] = (
        45
        + 20 * matrix["weibo_role_data_available"].astype(int)
        + 15 * np.minimum(matrix["bilibili_content_count"], 3) / 3
        + 20 * matrix["role_level_platform_coverage"]
    ).clip(upper=100)
    matrix["data_quality_grade"] = pd.cut(
        matrix["confidence_score"],
        bins=[-np.inf, 60, 75, 90, np.inf],
        labels=["D", "C", "B", "A"],
    ).astype(str)
    matrix["heat_score"] = matrix["cross_platform_heat"]
    matrix["evergreen_score"] = 0.60 * matrix["reach_score"] + 0.40 * matrix["engagement_score"]
    matrix["viral_potential_score"] = (
        0.60 * matrix["momentum_score"] + 0.40 * matrix["discussion_score"]
    )
    matrix["merch_opportunity_score"] = (
        0.45 * matrix["cross_platform_heat"]
        + 0.25 * matrix["intent_score"]
        + 0.15 * matrix["cross_platform_consistency"].fillna(50.0)
        + 0.15 * matrix["confidence_score"]
    )
    matrix["commerce_validation_status"] = np.where(
        matrix["cross_platform_heat"] >= 60,
        "优先补充淘宝销量/收藏加购",
        np.where(matrix["cross_platform_heat"] >= 45, "常规补充商业数据", "低成本观察"),
    )
    matrix = matrix.sort_values(
        ["cross_platform_heat", "confidence_score"], ascending=False
    ).reset_index(drop=True)
    matrix["heat_rank"] = np.arange(1, len(matrix) + 1)
    matrix["platform_gap"] = (
        matrix["bilibili_heat"] - matrix["weibo_heat"]
    ).abs()
    content_scores = pd.concat([bilibili_scored, weibo_scored], ignore_index=True, sort=False)
    return matrix, content_scores
