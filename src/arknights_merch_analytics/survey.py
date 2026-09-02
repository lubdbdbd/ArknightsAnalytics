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
    "attention_check",
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
    flag(frame["attention_check"].astype(str).ne("通过"), "attention_check_failed")
    flag(~frame["purchase_intent"].between(1, 5), "invalid_purchase_intent")
    flag(~frame["acceptable_price"].between(1, 5000), "invalid_acceptable_price")
    flag(~frame["limited_preference"].between(1, 5), "invalid_limited_preference")
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


def write_survey_report(
    valid_responses: pd.DataFrame,
    audit: pd.DataFrame,
    summary: pd.DataFrame,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    total = len(audit)
    valid_count = int(audit["valid"].sum()) if not audit.empty else 0
    lines = [
        "# 用户购买意愿调研报告",
        "",
        "> 本报告只统计明确同意、通过注意力检查且完成时间合理的真实答卷；不保存姓名、手机号等个人身份信息。",
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
    output_path.write_text("\n".join(lines), encoding="utf-8")
