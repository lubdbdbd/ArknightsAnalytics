from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = {
    "response_id",
    "respondent_id",
    "submitted_at",
    "consent",
    "response_source",
    "completion_seconds",
    "player_tenure_months",
    "monthly_merch_budget",
    "has_purchased_merch",
    "operator",
    "category",
    "purchase_intent",
    "acceptable_price",
    "channel",
    "limited_preference",
}

OPTIONAL_COLUMNS_DEFAULTS = {
    "questionnaire_version": "v2.0",
    "randomization_group": "A",
    "age_band": "未回答",
    "region_tier": "未回答",
    "activity_days_30d": np.nan,
    "annual_merch_spend": np.nan,
    "purchase_frequency_12m": np.nan,
    "fandom_identity": "未回答",
    "preferred_operator_1": "",
    "preferred_operator_2": "",
    "preferred_operator_3": "",
    "purchase_motivation": "",
    "purchase_barrier": "",
    "authenticity_importance": np.nan,
    "design_importance": np.nan,
    "practicality_importance": np.nan,
    "preorder_tolerance_days": np.nan,
    "price_too_cheap": np.nan,
    "price_good_value": np.nan,
    "price_expensive": np.nan,
    "price_too_expensive": np.nan,
    "concept_appeal": np.nan,
    "concept_uniqueness": np.nan,
    "product_improvement": "",
    "open_feedback": "",
}

SUMMARY_COLUMNS = [
    "operator",
    "category",
    "respondent_count",
    "purchase_intent_mean",
    "high_intent_share",
    "acceptable_price_median",
    "acceptable_price_p25",
    "acceptable_price_p75",
    "prior_buyer_share",
    "limited_preference_mean",
    "monthly_budget_median",
    "survey_evidence_grade",
    "research_note",
]

SEGMENT_SUMMARY_COLUMNS = [
    "user_segment",
    "respondent_count",
    "respondent_share",
    "prior_buyer_share",
    "purchase_intent_mean",
    "high_intent_share",
    "acceptable_price_median",
    "annual_merch_spend_median",
    "monthly_budget_median",
    "preorder_tolerance_days_median",
]

PRICE_SUMMARY_COLUMNS = [
    "operator",
    "category",
    "respondent_count",
    "acceptable_price_median",
    "acceptable_price_p25",
    "acceptable_price_p75",
    "good_value_price_median",
    "expensive_price_median",
    "too_expensive_price_median",
    "directional_price_floor",
    "directional_price_ceiling",
]


def validate_survey_responses(
    responses: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    missing = REQUIRED_COLUMNS.difference(responses.columns)
    if missing:
        raise ValueError(f"Missing survey columns: {sorted(missing)}")
    frame = responses.copy()
    if frame.empty:
        return frame, pd.DataFrame(columns=["response_id", "valid", "exclusion_reason"])
    numeric_columns = [
        "completion_seconds",
        "player_tenure_months",
        "monthly_merch_budget",
        "purchase_intent",
        "acceptable_price",
        "limited_preference",
    ]
    for column, default in OPTIONAL_COLUMNS_DEFAULTS.items():
        if column not in frame.columns:
            frame[column] = default
    numeric_columns.extend(
        [
            "activity_days_30d",
            "annual_merch_spend",
            "purchase_frequency_12m",
            "authenticity_importance",
            "design_importance",
            "practicality_importance",
            "preorder_tolerance_days",
            "price_too_cheap",
            "price_good_value",
            "price_expensive",
            "price_too_expensive",
            "concept_appeal",
            "concept_uniqueness",
        ]
    )
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["submitted_at"] = pd.to_datetime(frame["submitted_at"], errors="coerce", utc=True)
    frame["consent"] = frame["consent"].astype(str).str.lower().isin({"1", "true", "yes", "是"})
    frame["has_purchased_merch"] = (
        frame["has_purchased_merch"].astype(str).str.lower().isin({"1", "true", "yes", "是"})
    )
    reasons: list[list[str]] = [[] for _ in range(len(frame))]

    def flag(mask: pd.Series, reason: str) -> None:
        for position in np.flatnonzero(mask.fillna(False).to_numpy()):
            reasons[position].append(reason)

    flag(~frame["consent"], "no_consent")
    flag(frame["submitted_at"].isna(), "invalid_timestamp")
    flag(frame["completion_seconds"].lt(45) | frame["completion_seconds"].isna(), "too_fast")
    flag(~frame["purchase_intent"].between(1, 5), "invalid_purchase_intent")
    flag(~frame["acceptable_price"].between(1, 5000), "invalid_acceptable_price")
    flag(~frame["limited_preference"].between(1, 5), "invalid_limited_preference")
    flag(frame["player_tenure_months"].lt(0) | frame["player_tenure_months"].gt(120), "invalid_player_tenure")
    flag(frame["monthly_merch_budget"].lt(0) | frame["monthly_merch_budget"].gt(10000), "invalid_monthly_budget")
    flag(frame["activity_days_30d"].notna() & ~frame["activity_days_30d"].between(0, 30), "invalid_activity_days")
    flag(frame["annual_merch_spend"].notna() & ~frame["annual_merch_spend"].between(0, 100000), "invalid_annual_spend")
    flag(frame["purchase_frequency_12m"].notna() & ~frame["purchase_frequency_12m"].between(0, 100), "invalid_purchase_frequency")
    rating_columns = [
        "authenticity_importance",
        "design_importance",
        "practicality_importance",
        "concept_appeal",
        "concept_uniqueness",
    ]
    for column in rating_columns:
        flag(frame[column].notna() & ~frame[column].between(1, 5), f"invalid_{column}")
    price_ladder = frame[["price_too_cheap", "price_good_value", "price_expensive", "price_too_expensive"]]
    has_price_ladder = price_ladder.notna().all(axis=1)
    invalid_price_ladder = has_price_ladder & ~(
        price_ladder["price_too_cheap"].le(price_ladder["price_good_value"])
        & price_ladder["price_good_value"].le(price_ladder["price_expensive"])
        & price_ladder["price_expensive"].le(price_ladder["price_too_expensive"])
    )
    flag(invalid_price_ladder, "invalid_price_ladder")
    flag(frame["operator"].fillna("").astype(str).str.strip().eq(""), "missing_operator")
    flag(frame["category"].fillna("").astype(str).str.strip().eq(""), "missing_category")
    flag(
        frame["response_id"].fillna("").astype(str).str.contains("EXAMPLE|TEST", case=False),
        "non_real_identifier",
    )
    flag(frame["response_id"].duplicated(keep="first"), "duplicate_response")
    audit = pd.DataFrame(
        {
            "response_id": frame["response_id"].astype(str),
            "valid": [not row_reasons for row_reasons in reasons],
            "exclusion_reason": ["|".join(row_reasons) for row_reasons in reasons],
        }
    )
    valid = frame.loc[audit["valid"].to_numpy()].copy()
    valid["is_real_survey_response"] = True
    annual_spend = valid["annual_merch_spend"].fillna(valid["monthly_merch_budget"] * 12)
    purchase_frequency = valid["purchase_frequency_12m"].fillna(0)
    valid["user_segment"] = np.select(
        [
            valid["has_purchased_merch"] & (annual_spend.ge(500) | purchase_frequency.ge(4)),
            valid["has_purchased_merch"],
            ~valid["has_purchased_merch"] & valid["purchase_intent"].ge(4),
        ],
        ["core_buyer", "occasional_buyer", "potential_buyer"],
        default="observer",
    )
    return valid.reset_index(drop=True), audit


def build_survey_summary(valid_responses: pd.DataFrame) -> pd.DataFrame:
    if valid_responses.empty:
        return pd.DataFrame(columns=SUMMARY_COLUMNS)
    grouped = valid_responses.groupby(["operator", "category"], as_index=False).agg(
        respondent_count=("respondent_id", "nunique"),
        purchase_intent_mean=("purchase_intent", "mean"),
        high_intent_share=("purchase_intent", lambda values: (values >= 4).mean()),
        acceptable_price_median=("acceptable_price", "median"),
        acceptable_price_p25=("acceptable_price", lambda values: values.quantile(0.25)),
        acceptable_price_p75=("acceptable_price", lambda values: values.quantile(0.75)),
        prior_buyer_share=("has_purchased_merch", "mean"),
        limited_preference_mean=("limited_preference", "mean"),
        monthly_budget_median=("monthly_merch_budget", "median"),
    )
    grouped["survey_evidence_grade"] = pd.cut(
        grouped["respondent_count"],
        bins=[-np.inf, 9, 29, 99, np.inf],
        labels=["D", "C", "B", "A"],
    ).astype(str)
    grouped["research_note"] = np.select(
        [
            grouped["respondent_count"].ge(100),
            grouped["respondent_count"].ge(30),
            grouped["respondent_count"].ge(10),
        ],
        ["较稳定的方向性样本", "可用于方向判断", "仅作探索性观察"],
        default="样本不足，不进入决策",
    )
    return grouped.sort_values(
        ["survey_evidence_grade", "high_intent_share", "respondent_count"],
        ascending=[True, False, False],
    ).reset_index(drop=True)


def build_survey_segment_summary(valid_responses: pd.DataFrame) -> pd.DataFrame:
    if valid_responses.empty:
        return pd.DataFrame(columns=SEGMENT_SUMMARY_COLUMNS)
    frame = valid_responses.copy()
    if "user_segment" not in frame.columns:
        frame["user_segment"] = "unclassified"
    frame["annual_merch_spend"] = frame["annual_merch_spend"].fillna(
        frame["monthly_merch_budget"] * 12
    )
    grouped = frame.groupby("user_segment", as_index=False).agg(
        respondent_count=("respondent_id", "nunique"),
        prior_buyer_share=("has_purchased_merch", "mean"),
        purchase_intent_mean=("purchase_intent", "mean"),
        high_intent_share=("purchase_intent", lambda values: values.ge(4).mean()),
        acceptable_price_median=("acceptable_price", "median"),
        annual_merch_spend_median=("annual_merch_spend", "median"),
        monthly_budget_median=("monthly_merch_budget", "median"),
        preorder_tolerance_days_median=("preorder_tolerance_days", "median"),
    )
    total = grouped["respondent_count"].sum()
    grouped["respondent_share"] = grouped["respondent_count"] / max(total, 1)
    return grouped[SEGMENT_SUMMARY_COLUMNS].sort_values(
        ["respondent_count", "purchase_intent_mean"], ascending=[False, False]
    ).reset_index(drop=True)


def build_survey_barrier_summary(valid_responses: pd.DataFrame) -> pd.DataFrame:
    columns = ["purchase_barrier", "respondent_count", "respondent_share"]
    if valid_responses.empty or "purchase_barrier" not in valid_responses.columns:
        return pd.DataFrame(columns=columns)
    respondent_barriers: list[tuple[str, str]] = []
    for row in valid_responses[["respondent_id", "purchase_barrier"]].drop_duplicates().itertuples(index=False):
        barriers = [item.strip() for item in str(row.purchase_barrier).replace("；", "|").split("|")]
        for barrier in barriers:
            if barrier and barrier.lower() != "nan":
                respondent_barriers.append((str(row.respondent_id), barrier))
    if not respondent_barriers:
        return pd.DataFrame(columns=columns)
    exploded = pd.DataFrame(respondent_barriers, columns=["respondent_id", "purchase_barrier"])
    summary = exploded.groupby("purchase_barrier", as_index=False).agg(
        respondent_count=("respondent_id", "nunique")
    )
    denominator = valid_responses["respondent_id"].nunique()
    summary["respondent_share"] = summary["respondent_count"] / max(denominator, 1)
    return summary.sort_values("respondent_count", ascending=False).reset_index(drop=True)


def build_survey_price_summary(valid_responses: pd.DataFrame) -> pd.DataFrame:
    if valid_responses.empty:
        return pd.DataFrame(columns=PRICE_SUMMARY_COLUMNS)
    grouped = valid_responses.groupby(["operator", "category"], as_index=False).agg(
        respondent_count=("respondent_id", "nunique"),
        acceptable_price_median=("acceptable_price", "median"),
        acceptable_price_p25=("acceptable_price", lambda values: values.quantile(0.25)),
        acceptable_price_p75=("acceptable_price", lambda values: values.quantile(0.75)),
        good_value_price_median=("price_good_value", "median"),
        expensive_price_median=("price_expensive", "median"),
        too_expensive_price_median=("price_too_expensive", "median"),
    )
    grouped["directional_price_floor"] = grouped["good_value_price_median"].fillna(
        grouped["acceptable_price_p25"]
    )
    grouped["directional_price_ceiling"] = grouped["expensive_price_median"].fillna(
        grouped["acceptable_price_p75"]
    )
    return grouped[PRICE_SUMMARY_COLUMNS].sort_values(
        ["respondent_count", "acceptable_price_median"], ascending=[False, False]
    ).reset_index(drop=True)


def write_survey_report(
    valid_responses: pd.DataFrame,
    audit: pd.DataFrame,
    summary: pd.DataFrame,
    output_path: Path,
    segment_summary: pd.DataFrame | None = None,
    barrier_summary: pd.DataFrame | None = None,
    price_summary: pd.DataFrame | None = None,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    total = len(audit)
    valid_count = int(audit["valid"].sum()) if not audit.empty else 0
    lines = [
        "# 用户购买意愿调研报告",
        "",
        "> 本报告只统计明确同意、完成时间合理且字段逻辑有效的真实答卷；不保存姓名、手机号等个人身份信息。",
        "",
        "## 数据质量",
        "",
        f"- 原始记录：{total} 条。",
        f"- 有效记录：{valid_count} 条。",
        f"- 有效受访者：{valid_responses['respondent_id'].nunique() if not valid_responses.empty else 0} 人。",
        f"- 排除记录：{total - valid_count} 条。",
        "- 该调研为便利抽样，不代表全体玩家人口分布；样本量只决定证据等级，不消除选择偏差。",
        "",
        "## 角色 × 品类结果",
        "",
        summary.to_markdown(index=False, floatfmt=".2f") if not summary.empty else "尚未导入真实答卷，当前不生成购买意愿结论。",
    ]
    if segment_summary is not None:
        lines.extend(
            [
                "",
                "## 用户分群",
                "",
                segment_summary.to_markdown(index=False, floatfmt=".2f")
                if not segment_summary.empty
                else "尚无可分群的真实答卷。",
            ]
        )
    if barrier_summary is not None:
        lines.extend(
            [
                "",
                "## 购买阻力",
                "",
                barrier_summary.to_markdown(index=False, floatfmt=".2f")
                if not barrier_summary.empty
                else "尚无购买阻力数据。",
            ]
        )
    if price_summary is not None:
        lines.extend(
            [
                "",
                "## 方向性价格区间",
                "",
                "> 该区间来自匿名意愿问卷，不等于成交价格；样本不足30人时不得进入正式定价。",
                "",
                price_summary.to_markdown(index=False, floatfmt=".2f")
                if not price_summary.empty
                else "尚无价格区间数据。",
            ]
        )
    output_path.write_text("\n".join(lines), encoding="utf-8")
