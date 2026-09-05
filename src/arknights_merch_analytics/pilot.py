from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd


VARIANT_TO_BASE_OPERATOR = {
    "新约能天使": "能天使",
    "缄默德克萨斯": "德克萨斯",
    "荒芜拉普兰德": "拉普兰德",
    "归溟幽灵鲨": "幽灵鲨",
    "纯烬艾雅法拉": "艾雅法拉",
    "赤刃明霄陈": "陈",
    "凛御银灰": "银灰",
    "凯尔希·思衡托": "凯尔希",
    "予愿安洁莉娜": "安洁莉娜",
    "斩业星熊": "星熊",
    "怒潮凛冬": "凛冬",
}

PILOT_TABLE_COLUMNS = {
    "pilot_candidate_decisions": [
        "decision_id",
        "candidate_id",
        "decision",
        "rationale",
        "decided_at",
        "evidence_ref",
        "is_simulated",
    ],
    "pilot_campaigns": [
        "campaign_id",
        "candidate_id",
        "channel",
        "creative_variant",
        "published_at",
        "impressions",
        "clicks",
        "landing_uv",
        "evidence_ref",
        "is_simulated",
    ],
    "pilot_intent_leads": [
        "lead_id",
        "campaign_id",
        "candidate_id",
        "submitted_at",
        "accepted_price",
        "preorder_tolerance_days",
        "purchase_intent",
        "qualified_intent",
        "consent",
        "source_channel",
        "is_simulated",
    ],
    "pilot_supplier_quotes": [
        "quote_id",
        "candidate_id",
        "supplier_code",
        "quoted_at",
        "rights_verified",
        "rights_evidence_ref",
        "moq",
        "unit_cost",
        "sample_cost",
        "lead_time_days",
        "defect_allowance_pct",
        "payment_terms",
        "quote_status",
        "is_simulated",
    ],
    "pilot_orders": [
        "order_id",
        "candidate_id",
        "order_date",
        "channel",
        "quantity",
        "unit_price",
        "discount_amount",
        "shipping_fee",
        "payment_status",
        "paid_amount",
        "is_simulated",
    ],
    "pilot_fulfillment_events": [
        "event_id",
        "order_id",
        "event_type",
        "event_at",
        "quantity",
        "evidence_ref",
        "is_simulated",
    ],
    "pilot_after_sales": [
        "case_id",
        "order_id",
        "case_type",
        "reason",
        "requested_at",
        "resolved_at",
        "refund_amount",
        "case_status",
        "is_simulated",
    ],
    "pilot_reviews": [
        "review_id",
        "order_id",
        "submitted_at",
        "satisfaction_score",
        "quality_score",
        "delivery_score",
        "repurchase_intent",
        "feedback_summary",
        "is_simulated",
    ],
}

PRIMARY_KEYS = {
    "pilot_candidate_decisions": "decision_id",
    "pilot_campaigns": "campaign_id",
    "pilot_intent_leads": "lead_id",
    "pilot_supplier_quotes": "quote_id",
    "pilot_orders": "order_id",
    "pilot_fulfillment_events": "event_id",
    "pilot_after_sales": "case_id",
    "pilot_reviews": "review_id",
}

NUMERIC_COLUMNS = {
    "pilot_campaigns": ["impressions", "clicks", "landing_uv"],
    "pilot_intent_leads": [
        "accepted_price",
        "preorder_tolerance_days",
        "purchase_intent",
    ],
    "pilot_supplier_quotes": [
        "moq",
        "unit_cost",
        "sample_cost",
        "lead_time_days",
        "defect_allowance_pct",
    ],
    "pilot_orders": [
        "quantity",
        "unit_price",
        "discount_amount",
        "shipping_fee",
        "paid_amount",
    ],
    "pilot_fulfillment_events": ["quantity"],
    "pilot_after_sales": ["refund_amount"],
    "pilot_reviews": [
        "satisfaction_score",
        "quality_score",
        "delivery_score",
        "repurchase_intent",
    ],
}

BOOLEAN_COLUMNS = {
    "pilot_candidate_decisions": ["is_simulated"],
    "pilot_campaigns": ["is_simulated"],
    "pilot_intent_leads": ["qualified_intent", "consent", "is_simulated"],
    "pilot_supplier_quotes": ["rights_verified", "is_simulated"],
    "pilot_orders": ["is_simulated"],
    "pilot_fulfillment_events": ["is_simulated"],
    "pilot_after_sales": ["is_simulated"],
    "pilot_reviews": ["is_simulated"],
}

DATE_COLUMNS = {
    "pilot_candidate_decisions": ["decided_at"],
    "pilot_campaigns": ["published_at"],
    "pilot_intent_leads": ["submitted_at"],
    "pilot_supplier_quotes": ["quoted_at"],
    "pilot_orders": ["order_date"],
    "pilot_fulfillment_events": ["event_at"],
    "pilot_after_sales": ["requested_at", "resolved_at"],
    "pilot_reviews": ["submitted_at"],
}

REQUIRED_COLUMNS = {
    "pilot_candidate_decisions": [
        "decision_id",
        "candidate_id",
        "decision",
        "decided_at",
        "is_simulated",
    ],
    "pilot_campaigns": [
        "campaign_id",
        "candidate_id",
        "channel",
        "creative_variant",
        "published_at",
        "impressions",
        "clicks",
        "landing_uv",
        "evidence_ref",
        "is_simulated",
    ],
    "pilot_intent_leads": [
        "lead_id",
        "campaign_id",
        "candidate_id",
        "submitted_at",
        "purchase_intent",
        "qualified_intent",
        "consent",
        "source_channel",
        "is_simulated",
    ],
    "pilot_supplier_quotes": [
        "quote_id",
        "candidate_id",
        "supplier_code",
        "quoted_at",
        "rights_verified",
        "rights_evidence_ref",
        "moq",
        "unit_cost",
        "lead_time_days",
        "quote_status",
        "is_simulated",
    ],
    "pilot_orders": [
        "order_id",
        "candidate_id",
        "order_date",
        "channel",
        "quantity",
        "unit_price",
        "payment_status",
        "paid_amount",
        "is_simulated",
    ],
    "pilot_fulfillment_events": [
        "event_id",
        "order_id",
        "event_type",
        "event_at",
        "quantity",
        "evidence_ref",
        "is_simulated",
    ],
    "pilot_after_sales": [
        "case_id",
        "order_id",
        "case_type",
        "requested_at",
        "refund_amount",
        "case_status",
        "is_simulated",
    ],
    "pilot_reviews": [
        "review_id",
        "order_id",
        "submitted_at",
        "satisfaction_score",
        "quality_score",
        "delivery_score",
        "repurchase_intent",
        "is_simulated",
    ],
}


def _empty_table(table_name: str) -> pd.DataFrame:
    frame = pd.DataFrame(columns=PILOT_TABLE_COLUMNS[table_name])
    for column in NUMERIC_COLUMNS.get(table_name, []):
        frame[column] = pd.Series(dtype="float64")
    for column in BOOLEAN_COLUMNS.get(table_name, []):
        frame[column] = pd.Series(dtype="boolean")
    return frame


def create_pilot_templates(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for table_name in PILOT_TABLE_COLUMNS:
        path = output_dir / f"{table_name}.csv"
        if not path.exists():
            _empty_table(table_name).to_csv(path, index=False, encoding="utf-8-sig")


def _parse_boolean(value: object) -> object:
    if pd.isna(value) or str(value).strip() == "":
        return pd.NA
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes", "y"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False
    return pd.NA


def load_pilot_tables(input_dir: Path) -> dict[str, pd.DataFrame]:
    tables: dict[str, pd.DataFrame] = {}
    for table_name, expected_columns in PILOT_TABLE_COLUMNS.items():
        path = input_dir / f"{table_name}.csv"
        if not path.exists():
            tables[table_name] = _empty_table(table_name)
            continue
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
        missing = set(expected_columns).difference(frame.columns)
        unexpected = set(frame.columns).difference(expected_columns)
        if missing or unexpected:
            raise ValueError(
                f"{table_name} schema mismatch: missing={sorted(missing)}, "
                f"unexpected={sorted(unexpected)}"
            )
        frame = frame.reindex(columns=expected_columns)
        for column in NUMERIC_COLUMNS.get(table_name, []):
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        for column in BOOLEAN_COLUMNS.get(table_name, []):
            frame[column] = frame[column].map(_parse_boolean).astype("boolean")
        tables[table_name] = frame
    return tables


def _require_nonblank(
    table_name: str,
    frame: pd.DataFrame,
    column: str,
    errors: list[str],
) -> None:
    if frame.empty:
        return
    missing = frame[column].isna() | frame[column].astype(str).str.strip().eq("")
    if missing.any():
        errors.append(f"{table_name}.{column} contains {int(missing.sum())} blank values")


def validate_pilot_tables(tables: dict[str, pd.DataFrame]) -> None:
    errors: list[str] = []
    for table_name, expected_columns in PILOT_TABLE_COLUMNS.items():
        if table_name not in tables:
            errors.append(f"missing table: {table_name}")
            continue
        frame = tables[table_name]
        missing = set(expected_columns).difference(frame.columns)
        if missing:
            errors.append(f"{table_name} missing columns: {sorted(missing)}")
            continue
        primary_key = PRIMARY_KEYS[table_name]
        _require_nonblank(table_name, frame, primary_key, errors)
        if frame[primary_key].duplicated().any():
            errors.append(f"{table_name}.{primary_key} contains duplicate values")
        for column in REQUIRED_COLUMNS[table_name]:
            _require_nonblank(table_name, frame, column, errors)
        if not frame.empty and frame["is_simulated"].fillna(True).astype(bool).any():
            errors.append(f"{table_name} only accepts actual pilot rows with is_simulated=false")

    if errors:
        raise ValueError("; ".join(errors))

    campaigns = tables["pilot_campaigns"]
    leads = tables["pilot_intent_leads"]
    decisions = tables["pilot_candidate_decisions"]
    quotes = tables["pilot_supplier_quotes"]
    orders = tables["pilot_orders"]
    events = tables["pilot_fulfillment_events"]
    after_sales = tables["pilot_after_sales"]
    reviews = tables["pilot_reviews"]

    errors = []
    if not campaigns.empty:
        invalid_metrics = (
            campaigns[["impressions", "clicks", "landing_uv"]].lt(0).any(axis=1)
            | campaigns["clicks"].gt(campaigns["impressions"])
        )
        if invalid_metrics.any():
            errors.append("pilot_campaigns contains invalid funnel metrics")
    if not leads.empty:
        if not leads["campaign_id"].isin(campaigns["campaign_id"]).all():
            errors.append("pilot_intent_leads references unknown campaign_id")
        campaign_candidates = campaigns.set_index("campaign_id")["candidate_id"].to_dict()
        mismatched = leads.apply(
            lambda row: campaign_candidates.get(row["campaign_id"]) != row["candidate_id"],
            axis=1,
        )
        if mismatched.any():
            errors.append("pilot_intent_leads candidate_id does not match its campaign")
        if not leads["consent"].fillna(False).astype(bool).all():
            errors.append("pilot_intent_leads contains rows without consent")
        if leads["purchase_intent"].notna().any() and not leads[
            "purchase_intent"
        ].dropna().between(1, 5).all():
            errors.append("pilot_intent_leads.purchase_intent must be between 1 and 5")
    if not quotes.empty:
        invalid_quote = (
            quotes["moq"].le(0)
            | quotes["unit_cost"].le(0)
            | quotes["lead_time_days"].le(0)
            | quotes["defect_allowance_pct"].lt(0)
        )
        if invalid_quote.any():
            errors.append("pilot_supplier_quotes contains non-positive commercial terms")
        accepted_without_rights = quotes["quote_status"].eq("accepted") & ~quotes[
            "rights_verified"
        ].fillna(False)
        if accepted_without_rights.any():
            errors.append("accepted supplier quote must have verified rights evidence")
    if not orders.empty:
        approved_candidates = set(
            decisions.loc[decisions["decision"].eq("approved"), "candidate_id"]
        )
        eligible_candidates = set(
            quotes.loc[
                quotes["rights_verified"].fillna(False)
                & quotes["quote_status"].eq("accepted"),
                "candidate_id",
            ]
        )
        paid_orders = orders["payment_status"].eq("paid")
        paid_candidate_ids = set(orders.loc[paid_orders, "candidate_id"])
        qualified_lead_counts = (
            leads.loc[leads["qualified_intent"].fillna(False)]
            .groupby("candidate_id")
            .size()
            .to_dict()
        )
        insufficient_intent = sorted(
            candidate_id
            for candidate_id in paid_candidate_ids
            if qualified_lead_counts.get(candidate_id, 0) < 30
        )
        if insufficient_intent:
            errors.append(
                "paid order requires at least 30 qualified intents per candidate"
            )
        verified_supplier_counts = (
            quotes.loc[quotes["rights_verified"].fillna(False)]
            .groupby("candidate_id")["supplier_code"]
            .nunique()
            .to_dict()
        )
        insufficient_suppliers = sorted(
            candidate_id
            for candidate_id in paid_candidate_ids
            if verified_supplier_counts.get(candidate_id, 0) < 3
        )
        if insufficient_suppliers:
            errors.append(
                "paid order requires at least 3 rights-verified suppliers per candidate"
            )
        if not orders.loc[paid_orders, "candidate_id"].isin(approved_candidates).all():
            errors.append("paid order requires an approved candidate decision")
        if not orders.loc[paid_orders, "candidate_id"].isin(eligible_candidates).all():
            errors.append("paid order requires an accepted rights-verified supplier quote")
        expected_paid = (
            orders["quantity"] * orders["unit_price"]
            - orders["discount_amount"].fillna(0)
            + orders["shipping_fee"].fillna(0)
        ).round(2)
        mismatch = paid_orders & orders["paid_amount"].round(2).ne(expected_paid)
        if mismatch.any():
            errors.append("pilot_orders contains paid amount reconciliation errors")
        cancelled_with_payment = orders["payment_status"].eq("cancelled") & orders[
            "paid_amount"
        ].fillna(0).ne(0)
        if cancelled_with_payment.any():
            errors.append("cancelled order must have paid_amount=0")
    if not events.empty and not events["order_id"].isin(orders["order_id"]).all():
        errors.append("pilot_fulfillment_events references unknown order_id")
    if not after_sales.empty:
        if not after_sales["order_id"].isin(orders["order_id"]).all():
            errors.append("pilot_after_sales references unknown order_id")
        paid_lookup = orders.set_index("order_id")["paid_amount"].to_dict()
        excess_refund = after_sales.apply(
            lambda row: float(row["refund_amount"] or 0)
            > float(paid_lookup.get(row["order_id"], 0)),
            axis=1,
        )
        if excess_refund.any():
            errors.append("pilot_after_sales refund exceeds order paid amount")
    if not reviews.empty:
        if not reviews["order_id"].isin(orders["order_id"]).all():
            errors.append("pilot_reviews references unknown order_id")
        score_columns = [
            "satisfaction_score",
            "quality_score",
            "delivery_score",
            "repurchase_intent",
        ]
        if not reviews[score_columns].apply(lambda column: column.between(1, 5)).all().all():
            errors.append("pilot_reviews scores must be between 1 and 5")
    if errors:
        raise ValueError("; ".join(errors))


def _percentile_score(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    return numeric.rank(pct=True, ascending=higher_is_better).fillna(0.0) * 100


def build_pilot_candidate_shortlist(
    content_commerce: pd.DataFrame,
    survey_operator_summary: pd.DataFrame,
    survey_category_summary: pd.DataFrame,
    survey_operator_category_summary: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if content_commerce.empty or survey_operator_summary.empty or survey_category_summary.empty:
        return pd.DataFrame()
    roles = content_commerce.copy()
    roles["base_operator"] = roles["operator"].map(VARIANT_TO_BASE_OPERATOR).fillna(
        roles["operator"]
    )
    survey_roles = survey_operator_summary.copy()
    survey_roles["survey_role_score"] = _percentile_score(
        survey_roles["weighted_preference_score"]
    )
    roles = roles.merge(
        survey_roles[
            [
                "operator",
                "weighted_preference_score",
                "mention_share",
                "operator_rank",
                "survey_role_score",
            ]
        ].rename(columns={"operator": "base_operator"}),
        on="base_operator",
        how="left",
    )
    roles["survey_role_score"] = roles["survey_role_score"].fillna(0.0)
    roles["commercial_heat_score"] = pd.to_numeric(
        roles.get("commercial_heat_score", 0), errors="coerce"
    ).fillna(0.0)
    roles["confidence_score"] = pd.to_numeric(
        roles.get("confidence_score", 0), errors="coerce"
    ).fillna(0.0)
    roles["cross_platform_heat"] = pd.to_numeric(
        roles["cross_platform_heat"], errors="coerce"
    ).fillna(0.0)

    categories = survey_category_summary.copy()
    categories["category_intent_score"] = (
        0.50 * pd.to_numeric(categories["high_intent_share"], errors="coerce").fillna(0)
        + 0.30 * pd.to_numeric(categories["buyer_share"], errors="coerce").fillna(0)
        + 0.20 * _percentile_score(categories["selection_share"]) / 100
    ) * 100

    roles["_join_key"] = 1
    categories["_join_key"] = 1
    candidates = roles.merge(categories, on="_join_key", how="inner").drop(columns="_join_key")
    if survey_operator_category_summary is None or survey_operator_category_summary.empty:
        candidates["targeted_respondent_count"] = 0
        candidates["targeted_purchase_intent_mean"] = np.nan
        candidates["targeted_high_intent_share"] = np.nan
        candidates["targeted_acceptable_price_median"] = np.nan
    else:
        targeted = survey_operator_category_summary[
            [
                "operator",
                "category",
                "respondent_count",
                "purchase_intent_mean",
                "high_intent_share",
                "acceptable_price_median",
            ]
        ].rename(
            columns={
                "operator": "base_operator",
                "respondent_count": "targeted_respondent_count",
                "purchase_intent_mean": "targeted_purchase_intent_mean",
                "high_intent_share": "targeted_high_intent_share",
                "acceptable_price_median": "targeted_acceptable_price_median",
            }
        )
        candidates = candidates.merge(
            targeted,
            on=["base_operator", "category"],
            how="left",
        )
        candidates["targeted_respondent_count"] = candidates[
            "targeted_respondent_count"
        ].fillna(0).astype(int)
    candidates["pilot_score"] = (
        0.35 * candidates["cross_platform_heat"]
        + 0.25 * candidates["survey_role_score"]
        + 0.20 * candidates["category_intent_score"]
        + 0.10 * candidates["commercial_heat_score"]
        + 0.10 * candidates["confidence_score"]
    )
    candidates = candidates.sort_values(
        ["pilot_score", "cross_platform_heat", "category_intent_score"],
        ascending=False,
    ).reset_index(drop=True)
    candidates.insert(0, "candidate_id", [f"CAND-{index:03d}" for index in range(1, len(candidates) + 1)])
    candidates.insert(1, "candidate_rank", np.arange(1, len(candidates) + 1))
    candidates["operator_category_rank"] = (
        candidates.groupby("operator")["pilot_score"]
        .rank(method="first", ascending=False)
        .astype(int)
    )
    candidates["evidence_status"] = np.select(
        [
            candidates["targeted_respondent_count"].ge(30)
            & candidates["survey_role_score"].gt(0)
            & candidates["commercial_heat_score"].gt(0),
            candidates["targeted_respondent_count"].ge(30)
            & candidates["survey_role_score"].gt(0),
        ],
        ["supplier_validation_ready", "concept_test_ready"],
        default="needs_targeted_research",
    )
    candidates["decision_note"] = np.select(
        [
            candidates["evidence_status"].eq("supplier_validation_ready"),
            candidates["evidence_status"].eq("concept_test_ready"),
        ],
        [
            "已有内容、问卷与商业代理信号，可进入供应商比价和概念页验证",
            "已有内容与问卷信号，需补充正版商品和固定SKU证据",
        ],
        default="需先补充角色×品类专项样本",
    )
    candidates["data_type"] = "decision_support_from_real_aggregate"
    candidates["is_simulated"] = False
    output_columns = [
        "candidate_id",
        "candidate_rank",
        "operator_category_rank",
        "operator",
        "base_operator",
        "category",
        "pilot_score",
        "cross_platform_heat",
        "commercial_heat_score",
        "confidence_score",
        "weighted_preference_score",
        "mention_share",
        "operator_rank",
        "survey_role_score",
        "respondent_count",
        "buyer_share",
        "purchase_intent_mean",
        "high_intent_share",
        "median_acceptable_price",
        "median_preorder_days",
        "category_intent_score",
        "targeted_respondent_count",
        "targeted_purchase_intent_mean",
        "targeted_high_intent_share",
        "targeted_acceptable_price_median",
        "evidence_status",
        "decision_note",
        "data_type",
        "is_simulated",
    ]
    return candidates.reindex(columns=output_columns)


def summarize_pilot_readiness(
    shortlist: pd.DataFrame,
    tables: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    decisions = tables["pilot_candidate_decisions"]
    campaigns = tables["pilot_campaigns"]
    leads = tables["pilot_intent_leads"]
    quotes = tables["pilot_supplier_quotes"]
    orders = tables["pilot_orders"]
    events = tables["pilot_fulfillment_events"]
    reviews = tables["pilot_reviews"]
    approved_ids = set(
        decisions.loc[decisions["decision"].eq("approved"), "candidate_id"]
    ) if not decisions.empty else set()
    approved_candidates = shortlist.loc[shortlist["candidate_id"].isin(approved_ids)]
    approved_candidate_count = len(approved_candidates)
    approved_operator_count = approved_candidates["operator"].nunique()
    approval_complete = approved_candidate_count == 2 and approved_operator_count == 1
    qualified_by_candidate = (
        leads.loc[leads["qualified_intent"].fillna(False)]
        .groupby("candidate_id")
        .size()
        .to_dict()
        if not leads.empty
        else {}
    )
    verified_suppliers_by_candidate = (
        quotes.loc[quotes["rights_verified"].fillna(False)]
        .groupby("candidate_id")["supplier_code"]
        .nunique()
        .to_dict()
        if not quotes.empty
        else {}
    )
    qualified_leads = min(
        (qualified_by_candidate.get(candidate_id, 0) for candidate_id in approved_ids),
        default=0,
    )
    verified_quotes = min(
        (
            verified_suppliers_by_candidate.get(candidate_id, 0)
            for candidate_id in approved_ids
        ),
        default=0,
    )
    paid_orders = orders.loc[orders["payment_status"].eq("paid")] if not orders.empty else orders
    paid_by_candidate = (
        paid_orders.groupby("candidate_id")["order_id"].nunique().to_dict()
        if not paid_orders.empty
        else {}
    )
    paid_order_count = min(
        (paid_by_candidate.get(candidate_id, 0) for candidate_id in approved_ids),
        default=0,
    )
    delivered_order_ids = (
        set(events.loc[events["event_type"].eq("delivered"), "order_id"])
        if not events.empty
        else set()
    )
    delivery_rates = []
    review_counts = []
    for candidate_id in approved_ids:
        candidate_orders = paid_orders.loc[paid_orders["candidate_id"].eq(candidate_id)]
        candidate_order_ids = set(candidate_orders["order_id"])
        delivered_count = len(candidate_order_ids & delivered_order_ids)
        delivery_rates.append(
            delivered_count / len(candidate_order_ids) if candidate_order_ids else 0.0
        )
        review_counts.append(
            reviews.loc[reviews["order_id"].isin(candidate_order_ids), "review_id"].nunique()
            if not reviews.empty
            else 0
        )
    delivery_rate = min(delivery_rates, default=0.0)
    review_count = min(review_counts, default=0)
    stages = [
        {
            "stage": "candidate_approval",
            "current_value": approved_candidate_count,
            "gate": "2 approved candidates / 1 operator",
            "status": "complete" if approval_complete else "blocked",
            "next_action": (
                "围绕已批候选开展A/B内容预热"
                if approval_complete
                else "从候选池审批同一角色方向下的2个商品方案"
            ),
        },
        {
            "stage": "content_preheat",
            "current_value": int(campaigns["impressions"].fillna(0).sum()) if not campaigns.empty else 0,
            "gate": ">0 tracked impressions",
            "status": "complete" if not campaigns.empty and campaigns["impressions"].fillna(0).sum() > 0 else "blocked",
            "next_action": "发布A/B概念内容并记录曝光、点击和落地页UV",
        },
        {
            "stage": "qualified_intent_pool",
            "current_value": qualified_leads,
            "gate": ">=30 per approved candidate",
            "status": "complete" if qualified_leads >= 30 else "blocked",
            "next_action": "获取至少30条知情同意的匿名有效意向",
        },
        {
            "stage": "supplier_validation",
            "current_value": verified_quotes,
            "gate": ">=3 suppliers per approved candidate",
            "status": "complete" if verified_quotes >= 3 else "blocked",
            "next_action": "完成授权证据、MOQ、成本、样品和交期比价",
        },
        {
            "stage": "paid_order_pilot",
            "current_value": paid_order_count,
            "gate": ">=10 per approved candidate",
            "status": "complete" if paid_order_count >= 10 else "blocked",
            "next_action": "仅在候选与供应商通过门禁后，每个方案开展10至20单试点",
        },
        {
            "stage": "fulfillment",
            "current_value": round(delivery_rate * 100, 2),
            "gate": ">=90% delivered per approved candidate",
            "status": "complete" if delivery_rate >= 0.90 and paid_order_count else "blocked",
            "next_action": "记录打包、发货、签收、取消和退货事件",
        },
        {
            "stage": "post_purchase_review",
            "current_value": review_count,
            "gate": ">=5 per approved candidate",
            "status": "complete" if review_count >= 5 else "blocked",
            "next_action": "回收满意度、质量、交付和复购意愿",
        },
    ]
    return pd.DataFrame(stages)


def export_pilot_workspace(
    tables: dict[str, pd.DataFrame],
    shortlist: pd.DataFrame,
    readiness: pd.DataFrame,
    output_dir: Path,
    database_path: Path,
    views_path: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    shortlist.to_csv(output_dir / "pilot_candidate_shortlist.csv", index=False, encoding="utf-8-sig")
    readiness.to_csv(output_dir / "pilot_readiness.csv", index=False, encoding="utf-8-sig")
    for name, frame in tables.items():
        frame.to_csv(output_dir / f"{name}.csv", index=False, encoding="utf-8-sig")
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as connection:
        shortlist.to_sql("pilot_candidate_shortlist", connection, if_exists="replace", index=False)
        readiness.to_sql("pilot_readiness", connection, if_exists="replace", index=False)
        for name, frame in tables.items():
            frame.to_sql(name, connection, if_exists="replace", index=False)
        connection.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_pilot_campaign_candidate_channel
                ON pilot_campaigns(candidate_id, channel, published_at);
            CREATE INDEX IF NOT EXISTS idx_pilot_lead_candidate_campaign
                ON pilot_intent_leads(candidate_id, campaign_id, qualified_intent);
            CREATE INDEX IF NOT EXISTS idx_pilot_quote_candidate_status
                ON pilot_supplier_quotes(candidate_id, rights_verified, quote_status);
            CREATE INDEX IF NOT EXISTS idx_pilot_order_candidate_status
                ON pilot_orders(candidate_id, payment_status, order_date);
            CREATE INDEX IF NOT EXISTS idx_pilot_event_order_type
                ON pilot_fulfillment_events(order_id, event_type, event_at);
            CREATE INDEX IF NOT EXISTS idx_pilot_after_sales_order_status
                ON pilot_after_sales(order_id, case_status, requested_at);
            CREATE INDEX IF NOT EXISTS idx_pilot_review_order
                ON pilot_reviews(order_id, submitted_at);
            """
        )
        connection.executescript(views_path.read_text(encoding="utf-8"))


def write_pilot_report(
    shortlist: pd.DataFrame,
    readiness: pd.DataFrame,
    decisions: pd.DataFrame,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    top_candidates = shortlist.loc[shortlist["operator_category_rank"].le(2)].head(10).copy()
    if not top_candidates.empty:
        numeric_columns = [
            "pilot_score",
            "cross_platform_heat",
            "survey_role_score",
            "category_intent_score",
            "median_acceptable_price",
        ]
        top_candidates[numeric_columns] = top_candidates[numeric_columns].round(2)
        top_candidates = top_candidates[
            [
                "candidate_id",
                "operator",
                "base_operator",
                "category",
                "pilot_score",
                "median_acceptable_price",
                "evidence_status",
                "decision_note",
            ]
        ]
    approved_candidates = pd.DataFrame()
    if not decisions.empty:
        approved_candidates = decisions.loc[decisions["decision"].eq("approved")].merge(
            shortlist[
                [
                    "candidate_id",
                    "operator",
                    "category",
                    "pilot_score",
                    "targeted_respondent_count",
                    "evidence_status",
                ]
            ],
            on="candidate_id",
            how="left",
        )
        approved_candidates["pilot_score"] = approved_candidates["pilot_score"].round(2)
        approved_candidates = approved_candidates[
            [
                "candidate_id",
                "operator",
                "category",
                "pilot_score",
                "targeted_respondent_count",
                "evidence_status",
                "rationale",
                "decided_at",
            ]
        ]
    lines = [
        "# Arknights Analytics 商业试点准备度报告",
        "",
        "> 本报告只使用公开聚合数据与真实匿名问卷生成候选方向。供应商、曝光、意向、订单、履约、售后和评价必须由实际执行记录导入，系统不会生成模拟试点成果。",
        "",
        "## 项目定位",
        "",
        "《明日方舟》IP周边选品与商品运营分析平台，以用户洞察和内容热度形成候选池，再通过正版商品供应验证、内容预热、意向登记、小批量订单、履约和售后复盘建立可审计的0到1验证链路。",
        "",
        "## 当前阶段门禁",
        "",
        readiness.to_markdown(index=False),
        "",
        "## 已审批验证方案",
        "",
        (
            approved_candidates.to_markdown(index=False)
            if not approved_candidates.empty
            else "尚未审批商品方案。"
        ),
        "",
        "## 数据驱动候选方向",
        "",
        top_candidates.to_markdown(index=False) if not top_candidates.empty else "暂无可用候选。",
        "",
        "## 使用规则",
        "",
        "1. 候选评分只用于确定概念测试顺序，不等同于销量预测。",
        "2. 只有通过授权证据校验的现有正版或授权商品才能进入付费试点。",
        "3. 未达到30条专项有效意向前，不进入订单测试。",
        "4. 所有订单必须通过金额对账、状态流转、库存和退款校验。",
        "5. 达成门禁后再报告实际CTR、意向转化率、成交转化率、取消率、履约及时率、退货率、毛利率和满意度。",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")
