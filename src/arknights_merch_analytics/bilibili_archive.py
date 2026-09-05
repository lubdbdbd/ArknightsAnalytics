from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from arknights_merch_analytics.metrics import (
    EXCLUDED_OPERATOR_ENTITIES,
    extract_operator,
    percentile_score,
)


def classify_bilibili_content(title: str) -> str:
    value = str(title)
    if extract_operator(value):
        return "operator_pv"
    if re.search(r"\bEP\s*-|EP -", value, flags=re.IGNORECASE):
        return "music_ep"
    if any(keyword in value for keyword in ("活动宣传", "活动先导", "先导预告", "SideStory")):
        return "event_pv"
    if any(keyword in value for keyword in ("玩法介绍", "集成战略", "危机合约", "保全派驻")):
        return "gameplay_system"
    if any(keyword in value for keyword in ("音律联觉", "官方录播", "演唱会")):
        return "offline_event"
    if any(keyword in value for keyword in ("动画", "特别映像", "纪念短片", "公益PV")):
        return "animation_brand"
    if "PV" in value or "pv" in value:
        return "other_pv"
    return "other_official"


def build_bilibili_archive(
    raw_archive: pd.DataFrame, as_of: datetime | None = None
) -> pd.DataFrame:
    if raw_archive.empty:
        return raw_archive.copy()
    frame = raw_archive.drop_duplicates("bvid").copy()
    invalid_title = frame["title"].astype(str).map(
        lambda title: any(entity in title for entity in EXCLUDED_OPERATOR_ENTITIES)
    )
    frame = frame.loc[~invalid_title].copy()
    frame["published_at"] = pd.to_datetime(frame["published_at"], errors="coerce", utc=True)
    frame = frame[frame["published_at"].notna()].copy()
    timestamp = pd.Timestamp(as_of or datetime.now().astimezone())
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("Asia/Shanghai")
    published = frame["published_at"].dt.tz_convert(timestamp.tz)
    frame["age_days"] = ((timestamp - published).dt.total_seconds() / 86400).clip(lower=1)
    metric_columns = ["view", "like", "coin", "favorite", "share", "reply", "danmaku"]
    for column in metric_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)
    frame["content_type"] = frame["title"].map(classify_bilibili_content)
    frame["explicit_operator"] = frame["title"].map(extract_operator)
    frame["publication_year"] = frame["published_at"].dt.year.astype(int)
    frame["views_per_day"] = frame["view"] / frame["age_days"]
    frame["weighted_interactions"] = (
        frame["like"]
        + 2 * frame["coin"]
        + 2 * frame["favorite"]
        + 3 * frame["share"]
        + 1.5 * frame["reply"]
        + 0.5 * frame["danmaku"]
    )
    frame["weighted_engagement_rate"] = frame["weighted_interactions"] / frame["view"].clip(lower=1)
    frame["intent_rate"] = (2 * frame["favorite"] + frame["coin"] + frame["share"]) / frame["view"].clip(lower=1)
    frame["discussion_rate"] = (frame["reply"] + frame["danmaku"]) / frame["view"].clip(lower=1)
    frame["archive_reach_score"] = percentile_score(np.log1p(frame["view"]))
    frame["archive_momentum_score"] = percentile_score(np.log1p(frame["views_per_day"]))
    frame["archive_engagement_score"] = percentile_score(frame["weighted_engagement_rate"])
    frame["archive_content_score"] = (
        0.40 * frame["archive_reach_score"]
        + 0.30 * frame["archive_momentum_score"]
        + 0.30 * frame["archive_engagement_score"]
    )
    frame["published_at"] = frame["published_at"].map(lambda value: value.isoformat())
    return frame.sort_values("published_at", ascending=False).reset_index(drop=True)


def build_bilibili_campaign_attribution(
    archive: pd.DataFrame,
    before_days: int = 14,
    after_days: int = 14,
) -> pd.DataFrame:
    if archive.empty:
        return pd.DataFrame()
    frame = archive.copy()
    frame["published_timestamp"] = pd.to_datetime(frame["published_at"], utc=True)
    anchors = frame[frame["explicit_operator"].notna()][
        ["bvid", "explicit_operator", "published_timestamp"]
    ].copy()
    rows: list[dict[str, object]] = []
    for _, content in frame.iterrows():
        explicit = content["explicit_operator"]
        if pd.notna(explicit):
            operator = str(explicit)
            association_type = "direct_operator"
            days_from_anchor = 0.0
            association_weight = 1.0
        else:
            day_delta = (
                content["published_timestamp"] - anchors["published_timestamp"]
            ).dt.total_seconds() / 86400
            candidates = anchors[(day_delta >= -before_days) & (day_delta <= after_days)].copy()
            if candidates.empty:
                continue
            candidates["absolute_days"] = day_delta.loc[candidates.index].abs()
            anchor = candidates.sort_values(
                ["absolute_days", "published_timestamp", "explicit_operator"]
            ).iloc[0]
            operator = str(anchor["explicit_operator"])
            signed_delta = (
                content["published_timestamp"] - anchor["published_timestamp"]
            ).total_seconds() / 86400
            days_from_anchor = round(float(signed_delta), 4)
            association_type = "campaign_window"
            association_weight = max(0.25, 1 - abs(days_from_anchor) / 28)
        row = content.drop(labels=["published_timestamp"]).to_dict()
        row.update(
            {
                "operator": operator,
                "association_type": association_type,
                "association_weight": round(float(association_weight), 4),
                "days_from_anchor": days_from_anchor,
                "window_before_days": before_days,
                "window_after_days": after_days,
            }
        )
        rows.append(row)
    return pd.DataFrame(rows).sort_values(
        ["operator", "published_at", "association_type"],
        ascending=[True, False, True],
    ).reset_index(drop=True)


def build_bilibili_campaign_summary(attributed: pd.DataFrame) -> pd.DataFrame:
    if attributed.empty:
        return pd.DataFrame()
    frame = attributed.copy()
    frame["weighted_views"] = frame["view"] * frame["association_weight"]
    frame["weighted_intent_actions"] = (
        2 * frame["favorite"] + frame["coin"] + frame["share"]
    ) * frame["association_weight"]
    summary = frame.groupby("operator", as_index=False).agg(
        bilibili_campaign_content_count=("bvid", "nunique"),
        bilibili_direct_content_count=(
            "association_type",
            lambda values: (values == "direct_operator").sum(),
        ),
        bilibili_window_content_count=(
            "association_type",
            lambda values: (values == "campaign_window").sum(),
        ),
        bilibili_campaign_content_types=("content_type", "nunique"),
        bilibili_campaign_views=("view", "sum"),
        bilibili_weighted_campaign_views=("weighted_views", "sum"),
        bilibili_weighted_intent_actions=("weighted_intent_actions", "sum"),
        bilibili_campaign_median_views=("view", "median"),
        bilibili_campaign_first_published=("published_at", "min"),
        bilibili_campaign_last_published=("published_at", "max"),
    )
    summary["bilibili_campaign_exposure_score"] = percentile_score(
        np.log1p(summary["bilibili_weighted_campaign_views"])
    )
    summary["bilibili_campaign_depth_score"] = percentile_score(
        summary["bilibili_campaign_content_count"]
        + 0.5 * summary["bilibili_campaign_content_types"]
    )
    return summary.sort_values(
        ["bilibili_campaign_exposure_score", "bilibili_campaign_content_count"],
        ascending=False,
    ).reset_index(drop=True)


def build_bilibili_archive_summaries(
    archive: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if archive.empty:
        return pd.DataFrame(), pd.DataFrame()
    by_type = archive.groupby("content_type", as_index=False).agg(
        content_count=("bvid", "nunique"),
        total_views=("view", "sum"),
        median_views=("view", "median"),
        average_engagement_rate=("weighted_engagement_rate", "mean"),
        average_intent_rate=("intent_rate", "mean"),
        average_momentum=("views_per_day", "mean"),
    )
    by_year = archive.groupby("publication_year", as_index=False).agg(
        content_count=("bvid", "nunique"),
        operator_pv_count=("content_type", lambda values: (values == "operator_pv").sum()),
        music_ep_count=("content_type", lambda values: (values == "music_ep").sum()),
        event_pv_count=("content_type", lambda values: (values == "event_pv").sum()),
        total_views=("view", "sum"),
        median_views=("view", "median"),
        average_engagement_rate=("weighted_engagement_rate", "mean"),
    )
    return (
        by_type.sort_values("content_count", ascending=False).reset_index(drop=True),
        by_year.sort_values("publication_year").reset_index(drop=True),
    )


def write_bilibili_archive_report(
    archive: pd.DataFrame,
    by_type: pd.DataFrame,
    by_year: pd.DataFrame,
    attributed: pd.DataFrame,
    campaign_summary: pd.DataFrame,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Bilibili 官号历史内容与角色 Campaign 分析",
        "",
        "> 官号全量内容与角色直接内容分层保存。Campaign 窗口归因表示角色上线前后共享宣传曝光，不等同于视频只属于该角色。",
        "",
        "## 数据规模",
        "",
        f"- 官号公开视频：{len(archive)} 条。",
        f"- 覆盖年份：{archive['publication_year'].min()}—{archive['publication_year'].max()}。",
        f"- 累计公开播放快照：{archive['view'].sum():,.0f}；单条中位播放：{archive['view'].median():,.0f}。",
        f"- 加权互动动作快照：{archive['weighted_interactions'].sum():,.0f}。",
        f"- 直接识别角色 PV：{int(archive['explicit_operator'].notna().sum())} 条、{archive['explicit_operator'].nunique()} 名角色。",
        f"- 角色上线 Campaign 关联：{len(attributed)} 条，其中窗口关联 {int((attributed['association_type'] == 'campaign_window').sum())} 条。",
        f"- 角色 Campaign 中位内容数：{campaign_summary['bilibili_campaign_content_count'].median():.0f} 条。",
        "",
        "## 内容类型结构",
        "",
        by_type.to_markdown(index=False, floatfmt=".4f"),
        "",
        "## 年度供给趋势",
        "",
        by_year.to_markdown(index=False, floatfmt=".4f"),
        "",
        "## 角色 Campaign 曝光 Top 20",
        "",
        campaign_summary.head(20).to_markdown(index=False, floatfmt=".2f"),
        "",
        "## 归因边界",
        "",
        "- `direct_operator`：标题明确包含干员结构，可作为角色直接内容。",
        "- `campaign_window`：与最近角色 PV 相距不超过前后14天，只作为上线 Campaign 共享曝光。",
        "- 每条非直接内容只分配给最近的一个角色锚点，避免曝光重复累计。",
        "- 单字角色不做普通文本包含匹配，避免把‘望’‘余’等普通汉字误判为角色。",
        "- Campaign 指标当前不直接改写角色热度分，防止共享活动流量替代角色自身表现。",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_bilibili_archive_figures(
    by_type: pd.DataFrame,
    by_year: pd.DataFrame,
    campaign_summary: pd.DataFrame,
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid")
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    yearly = by_year.copy()
    yearly["other_content_count"] = (
        yearly["content_count"]
        - yearly["operator_pv_count"]
        - yearly["music_ep_count"]
        - yearly["event_pv_count"]
    ).clip(lower=0)
    fig, ax = plt.subplots(figsize=(11, 6))
    bottom = np.zeros(len(yearly))
    series = [
        ("operator_pv_count", "角色PV", "#d9485f"),
        ("music_ep_count", "音乐EP", "#7b61a8"),
        ("event_pv_count", "活动PV", "#e59f36"),
        ("other_content_count", "其他内容", "#4f83cc"),
    ]
    for column, label, color in series:
        values = yearly[column].to_numpy()
        ax.bar(yearly["publication_year"].astype(str), values, bottom=bottom, label=label, color=color)
        bottom += values
    ax.set_title("B站官号年度内容供给结构（公开样本）")
    ax.set_xlabel("Year")
    ax.set_ylabel("Content count")
    ax.legend(ncol=4)
    fig.tight_layout()
    fig.savefig(output_dir / "bilibili_yearly_content_supply.png", dpi=180)
    plt.close(fig)

    content = by_type.copy()
    fig, ax = plt.subplots(figsize=(10, 7))
    sizes = 80 + content["content_count"] * 6
    scatter = ax.scatter(
        content["median_views"],
        content["average_engagement_rate"] * 100,
        s=sizes,
        c=content["average_intent_rate"] * 100,
        cmap="viridis",
        alpha=0.85,
    )
    for _, row in content.iterrows():
        ax.annotate(row["content_type"], (row["median_views"], row["average_engagement_rate"] * 100), xytext=(5, 4), textcoords="offset points")
    ax.set_title("B站内容类型：中位播放 × 加权互动率")
    ax.set_xlabel("Median public views")
    ax.set_ylabel("Weighted engagement rate (%)")
    fig.colorbar(scatter, ax=ax, label="Intent rate (%)")
    fig.tight_layout()
    fig.savefig(output_dir / "bilibili_content_type_performance.png", dpi=180)
    plt.close(fig)

    top = campaign_summary.head(15).sort_values("bilibili_weighted_campaign_views")
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh(top["operator"], top["bilibili_weighted_campaign_views"], color="#3a7ca5")
    ax.set_title("角色上线 Campaign 加权公开播放 Top 15")
    ax.set_xlabel("Weighted public views")
    fig.tight_layout()
    fig.savefig(output_dir / "bilibili_campaign_exposure.png", dpi=180)
    plt.close(fig)
