from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from arknights_merch_analytics.pilot import (
    PILOT_TABLE_COLUMNS,
    build_pilot_candidate_shortlist,
    create_pilot_templates,
    export_pilot_workspace,
    load_pilot_tables,
    summarize_pilot_readiness,
    validate_pilot_tables,
)


def _empty_tables(tmp_path) -> dict[str, pd.DataFrame]:
    create_pilot_templates(tmp_path)
    return load_pilot_tables(tmp_path)


def _valid_tables(tmp_path) -> dict[str, pd.DataFrame]:
    tables = _empty_tables(tmp_path)
    tables["pilot_candidate_decisions"] = pd.DataFrame(
        [
            {
                "decision_id": "DEC-001",
                "candidate_id": "CAND-001",
                "decision": "approved",
                "rationale": "通过需求门禁",
                "decided_at": "2026-09-05",
                "evidence_ref": "reports/candidate.md",
                "is_simulated": False,
            }
        ]
    )
    tables["pilot_campaigns"] = pd.DataFrame(
        [
            {
                "campaign_id": "CAM-001",
                "candidate_id": "CAND-001",
                "channel": "Bilibili",
                "creative_variant": "A",
                "published_at": "2026-09-05",
                "impressions": 1000,
                "clicks": 120,
                "landing_uv": 100,
                "evidence_ref": "evidence/campaign-001.csv",
                "is_simulated": False,
            }
        ]
    )
    tables["pilot_intent_leads"] = pd.DataFrame(
        [
            {
                "lead_id": f"LEAD-HASH-{index:03d}",
                "campaign_id": "CAM-001",
                "candidate_id": "CAND-001",
                "submitted_at": "2026-09-06",
                "accepted_price": 79.0,
                "preorder_tolerance_days": 30,
                "purchase_intent": 5,
                "qualified_intent": True,
                "consent": True,
                "source_channel": "Bilibili",
                "is_simulated": False,
            }
            for index in range(1, 31)
        ]
    )
    tables["pilot_supplier_quotes"] = pd.DataFrame(
        [
            {
                "quote_id": f"QUOTE-{index:03d}",
                "candidate_id": "CAND-001",
                "supplier_code": f"SUP-{index:03d}",
                "quoted_at": "2026-09-06",
                "rights_verified": True,
                "rights_evidence_ref": f"evidence/rights-{index:03d}.md",
                "moq": 10,
                "unit_cost": 44.0 + index,
                "sample_cost": 60.0,
                "lead_time_days": 14,
                "defect_allowance_pct": 1.0,
                "payment_terms": "现款",
                "quote_status": "accepted" if index == 1 else "qualified",
                "is_simulated": False,
            }
            for index in range(1, 4)
        ]
    )
    tables["pilot_orders"] = pd.DataFrame(
        [
            {
                "order_id": "ORDER-001",
                "candidate_id": "CAND-001",
                "order_date": "2026-09-07",
                "channel": "pilot",
                "quantity": 1,
                "unit_price": 79.0,
                "discount_amount": 5.0,
                "shipping_fee": 6.0,
                "payment_status": "paid",
                "paid_amount": 80.0,
                "is_simulated": False,
            }
        ]
    )
    tables["pilot_fulfillment_events"] = pd.DataFrame(
        [
            {
                "event_id": "EVT-001",
                "order_id": "ORDER-001",
                "event_type": "delivered",
                "event_at": "2026-09-10",
                "quantity": 1,
                "evidence_ref": "evidence/fulfillment-001.csv",
                "is_simulated": False,
            }
        ]
    )
    tables["pilot_after_sales"] = pd.DataFrame(columns=PILOT_TABLE_COLUMNS["pilot_after_sales"])
    tables["pilot_reviews"] = pd.DataFrame(
        [
            {
                "review_id": "REV-001",
                "order_id": "ORDER-001",
                "submitted_at": "2026-09-11",
                "satisfaction_score": 5,
                "quality_score": 4,
                "delivery_score": 5,
                "repurchase_intent": 4,
                "feedback_summary": "包装完整",
                "is_simulated": False,
            }
        ]
    )
    return tables


def _candidate_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    content = pd.DataFrame(
        [
            {
                "operator": "新约能天使",
                "cross_platform_heat": 82.0,
                "commercial_heat_score": 60.0,
                "confidence_score": 85.0,
            },
            {
                "operator": "缄默德克萨斯",
                "cross_platform_heat": 70.0,
                "commercial_heat_score": 0.0,
                "confidence_score": 72.0,
            },
        ]
    )
    operators = pd.DataFrame(
        [
            {
                "operator": "德克萨斯",
                "weighted_preference_score": 97,
                "mention_share": 0.18,
                "operator_rank": 1,
            },
            {
                "operator": "能天使",
                "weighted_preference_score": 65,
                "mention_share": 0.14,
                "operator_rank": 5,
            },
        ]
    )
    categories = pd.DataFrame(
        [
            {
                "category": "毛绒玩偶",
                "respondent_count": 34,
                "buyer_share": 0.56,
                "purchase_intent_mean": 3.59,
                "high_intent_share": 0.56,
                "median_acceptable_price": 200.0,
                "median_preorder_days": 45.0,
                "selection_share": 0.14,
            },
            {
                "category": "亚克力制品",
                "respondent_count": 44,
                "buyer_share": 0.43,
                "purchase_intent_mean": 3.23,
                "high_intent_share": 0.41,
                "median_acceptable_price": 100.0,
                "median_preorder_days": 45.0,
                "selection_share": 0.18,
            },
        ]
    )
    return content, operators, categories


def test_creates_header_only_templates(tmp_path) -> None:
    create_pilot_templates(tmp_path)
    tables = load_pilot_tables(tmp_path)
    assert set(tables) == set(PILOT_TABLE_COLUMNS)
    assert all(frame.empty for frame in tables.values())


def test_template_creation_does_not_overwrite_existing_data(tmp_path) -> None:
    create_pilot_templates(tmp_path)
    path = tmp_path / "pilot_campaigns.csv"
    original = path.read_text(encoding="utf-8-sig") + "\n"
    path.write_text(original, encoding="utf-8-sig")
    create_pilot_templates(tmp_path)
    assert path.read_text(encoding="utf-8-sig") == original


def test_rejects_schema_drift(tmp_path) -> None:
    create_pilot_templates(tmp_path)
    path = tmp_path / "pilot_campaigns.csv"
    pd.DataFrame(columns=["unexpected"]).to_csv(path, index=False)
    with pytest.raises(ValueError, match="schema mismatch"):
        load_pilot_tables(tmp_path)


def test_accepts_empty_real_pilot_workspace(tmp_path) -> None:
    validate_pilot_tables(_empty_tables(tmp_path))


def test_accepts_valid_end_to_end_pilot_records(tmp_path) -> None:
    validate_pilot_tables(_valid_tables(tmp_path))


def test_rejects_simulated_rows_in_actual_pilot(tmp_path) -> None:
    tables = _valid_tables(tmp_path)
    tables["pilot_campaigns"].loc[0, "is_simulated"] = True
    with pytest.raises(ValueError, match="only accepts actual pilot rows"):
        validate_pilot_tables(tables)


def test_rejects_clicks_above_impressions(tmp_path) -> None:
    tables = _valid_tables(tmp_path)
    tables["pilot_campaigns"].loc[0, "clicks"] = 1001
    with pytest.raises(ValueError, match="invalid funnel metrics"):
        validate_pilot_tables(tables)


def test_rejects_intent_without_consent(tmp_path) -> None:
    tables = _valid_tables(tmp_path)
    tables["pilot_intent_leads"].loc[0, "consent"] = False
    with pytest.raises(ValueError, match="without consent"):
        validate_pilot_tables(tables)


def test_rejects_intent_candidate_mismatch(tmp_path) -> None:
    tables = _valid_tables(tmp_path)
    tables["pilot_intent_leads"].loc[0, "candidate_id"] = "CAND-OTHER"
    with pytest.raises(ValueError, match="does not match"):
        validate_pilot_tables(tables)


def test_rejects_accepted_quote_without_rights(tmp_path) -> None:
    tables = _valid_tables(tmp_path)
    tables["pilot_supplier_quotes"].loc[0, "rights_verified"] = False
    with pytest.raises(ValueError, match="verified rights"):
        validate_pilot_tables(tables)


def test_rejects_paid_order_without_approved_candidate(tmp_path) -> None:
    tables = _valid_tables(tmp_path)
    tables["pilot_candidate_decisions"].loc[0, "decision"] = "hold"
    with pytest.raises(ValueError, match="approved candidate"):
        validate_pilot_tables(tables)


def test_rejects_paid_order_without_eligible_supplier(tmp_path) -> None:
    tables = _valid_tables(tmp_path)
    tables["pilot_supplier_quotes"].loc[0, "quote_status"] = "qualified"
    with pytest.raises(ValueError, match="accepted rights-verified"):
        validate_pilot_tables(tables)


def test_rejects_paid_order_without_30_qualified_intents(tmp_path) -> None:
    tables = _valid_tables(tmp_path)
    tables["pilot_intent_leads"] = tables["pilot_intent_leads"].head(29)
    with pytest.raises(ValueError, match="30 qualified intents"):
        validate_pilot_tables(tables)


def test_rejects_paid_order_without_three_verified_suppliers(tmp_path) -> None:
    tables = _valid_tables(tmp_path)
    tables["pilot_supplier_quotes"] = tables["pilot_supplier_quotes"].head(2)
    with pytest.raises(ValueError, match="3 rights-verified suppliers"):
        validate_pilot_tables(tables)


def test_rejects_order_amount_mismatch(tmp_path) -> None:
    tables = _valid_tables(tmp_path)
    tables["pilot_orders"].loc[0, "paid_amount"] = 79.0
    with pytest.raises(ValueError, match="reconciliation"):
        validate_pilot_tables(tables)


def test_rejects_unknown_fulfillment_order(tmp_path) -> None:
    tables = _valid_tables(tmp_path)
    tables["pilot_fulfillment_events"].loc[0, "order_id"] = "UNKNOWN"
    with pytest.raises(ValueError, match="unknown order_id"):
        validate_pilot_tables(tables)


def test_rejects_review_score_outside_range(tmp_path) -> None:
    tables = _valid_tables(tmp_path)
    tables["pilot_reviews"].loc[0, "quality_score"] = 6
    with pytest.raises(ValueError, match="between 1 and 5"):
        validate_pilot_tables(tables)


def test_maps_alternate_operator_to_base_survey_role() -> None:
    content, operators, categories = _candidate_inputs()
    shortlist = build_pilot_candidate_shortlist(content, operators, categories)
    exusiai = shortlist.loc[shortlist["operator"].eq("新约能天使")]
    assert set(exusiai["base_operator"]) == {"能天使"}
    assert exusiai["survey_role_score"].gt(0).all()


def test_candidate_shortlist_has_no_simulated_results() -> None:
    content, operators, categories = _candidate_inputs()
    shortlist = build_pilot_candidate_shortlist(content, operators, categories)
    assert len(shortlist) == 4
    assert not shortlist["is_simulated"].any()
    assert set(shortlist["data_type"]) == {"decision_support_from_real_aggregate"}


def test_candidate_requires_targeted_role_category_sample() -> None:
    content, operators, categories = _candidate_inputs()
    targeted = pd.DataFrame(
        [
            {
                "operator": "能天使",
                "category": "毛绒玩偶",
                "respondent_count": 2,
                "purchase_intent_mean": 5.0,
                "high_intent_share": 1.0,
                "acceptable_price_median": 200.0,
            }
        ]
    )
    shortlist = build_pilot_candidate_shortlist(content, operators, categories, targeted)
    candidate = shortlist.loc[
        shortlist["operator"].eq("新约能天使") & shortlist["category"].eq("毛绒玩偶")
    ].iloc[0]
    assert candidate["targeted_respondent_count"] == 2
    assert candidate["evidence_status"] == "needs_targeted_research"


def test_readiness_blocks_unexecuted_commercial_stages(tmp_path) -> None:
    content, operators, categories = _candidate_inputs()
    shortlist = build_pilot_candidate_shortlist(content, operators, categories)
    readiness = summarize_pilot_readiness(shortlist, _empty_tables(tmp_path))
    assert readiness.loc[readiness["stage"].eq("candidate_approval"), "status"].item() == "blocked"
    assert readiness.loc[readiness["stage"].eq("paid_order_pilot"), "status"].item() == "blocked"


def test_readiness_accepts_two_products_under_one_operator(tmp_path) -> None:
    content, operators, categories = _candidate_inputs()
    shortlist = build_pilot_candidate_shortlist(content, operators, categories)
    tables = _empty_tables(tmp_path)
    operator_candidates = shortlist.loc[shortlist["operator"].eq("新约能天使")].head(2)
    tables["pilot_candidate_decisions"] = pd.DataFrame(
        [
            {
                "decision_id": f"DEC-{index:03d}",
                "candidate_id": candidate_id,
                "decision": "approved",
                "rationale": "批准进入专项验证",
                "decided_at": "2026-09-05",
                "evidence_ref": "docs/pilot.md",
                "is_simulated": False,
            }
            for index, candidate_id in enumerate(
                operator_candidates["candidate_id"], start=1
            )
        ]
    )
    readiness = summarize_pilot_readiness(shortlist, tables)
    approval = readiness.loc[readiness["stage"].eq("candidate_approval")]
    assert approval["status"].item() == "complete"
    assert approval["current_value"].item() == 2


def test_readiness_does_not_pool_orders_or_reviews_between_candidates(tmp_path) -> None:
    content, operators, categories = _candidate_inputs()
    shortlist = build_pilot_candidate_shortlist(content, operators, categories)
    tables = _empty_tables(tmp_path)
    operator_candidates = shortlist.loc[shortlist["operator"].eq("新约能天使")].head(2)
    approved_ids = operator_candidates["candidate_id"].tolist()
    tables["pilot_candidate_decisions"] = pd.DataFrame(
        [
            {
                "decision_id": f"DEC-{index:03d}",
                "candidate_id": candidate_id,
                "decision": "approved",
                "rationale": "批准进入专项验证",
                "decided_at": "2026-09-05",
                "evidence_ref": "docs/pilot.md",
                "is_simulated": False,
            }
            for index, candidate_id in enumerate(approved_ids, start=1)
        ]
    )
    tables["pilot_orders"] = pd.DataFrame(
        [
            {
                "order_id": f"ORDER-{index:03d}",
                "candidate_id": approved_ids[0],
                "order_date": "2026-09-07",
                "channel": "pilot",
                "quantity": 1,
                "unit_price": 39.0,
                "discount_amount": 0.0,
                "shipping_fee": 0.0,
                "payment_status": "paid",
                "paid_amount": 39.0,
                "is_simulated": False,
            }
            for index in range(1, 21)
        ]
    )
    tables["pilot_fulfillment_events"] = pd.DataFrame(
        [
            {
                "event_id": f"EVENT-{index:03d}",
                "order_id": f"ORDER-{index:03d}",
                "event_type": "delivered",
                "event_at": "2026-09-10",
                "quantity": 1,
                "evidence_ref": "evidence/fulfillment.csv",
                "is_simulated": False,
            }
            for index in range(1, 21)
        ]
    )
    tables["pilot_reviews"] = pd.DataFrame(
        [
            {
                "review_id": f"REVIEW-{index:03d}",
                "order_id": f"ORDER-{index:03d}",
                "submitted_at": "2026-09-11",
                "satisfaction_score": 5,
                "quality_score": 5,
                "delivery_score": 5,
                "repurchase_intent": 4,
                "feedback_summary": "匿名评价",
                "is_simulated": False,
            }
            for index in range(1, 21)
        ]
    )

    readiness = summarize_pilot_readiness(shortlist, tables)
    for stage in ["paid_order_pilot", "fulfillment", "post_purchase_review"]:
        row = readiness.loc[readiness["stage"].eq(stage)].iloc[0]
        assert row["status"] == "blocked"
        assert row["current_value"] == 0


def test_exports_sql_views_without_fabricated_orders(tmp_path) -> None:
    content, operators, categories = _candidate_inputs()
    shortlist = build_pilot_candidate_shortlist(content, operators, categories)
    tables = _empty_tables(tmp_path / "manual")
    readiness = summarize_pilot_readiness(shortlist, tables)
    database_path = tmp_path / "operations.db"
    views_path = tmp_path / "pilot_views.sql"
    source_views = Path(__file__).resolve().parents[1] / "sql" / "pilot_views.sql"
    views_path.write_text(source_views.read_text(encoding="utf-8"), encoding="utf-8")
    export_pilot_workspace(
        tables,
        shortlist,
        readiness,
        tmp_path / "processed",
        database_path,
        views_path,
    )
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM pilot_orders").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM vw_pilot_candidate_decision").fetchone()[0] == 4


def test_candidate_view_counts_distinct_verified_suppliers(tmp_path) -> None:
    content, operators, categories = _candidate_inputs()
    shortlist = build_pilot_candidate_shortlist(content, operators, categories)
    tables = _empty_tables(tmp_path / "manual")
    candidate_id = shortlist.iloc[0]["candidate_id"]
    tables["pilot_supplier_quotes"] = pd.DataFrame(
        [
            {
                "quote_id": f"QUOTE-{index:03d}",
                "candidate_id": candidate_id,
                "supplier_code": "SUP-SAME",
                "quoted_at": "2026-09-06",
                "rights_verified": True,
                "rights_evidence_ref": "evidence/rights.pdf",
                "moq": 50,
                "unit_cost": 10.0 + index,
                "sample_cost": 20.0,
                "lead_time_days": 20,
                "defect_allowance_pct": 1.0,
                "payment_terms": "现款",
                "quote_status": "qualified",
                "is_simulated": False,
            }
            for index in range(1, 3)
        ]
    )
    readiness = summarize_pilot_readiness(shortlist, tables)
    database_path = tmp_path / "operations.db"
    views_path = tmp_path / "pilot_views.sql"
    source_views = Path(__file__).resolve().parents[1] / "sql" / "pilot_views.sql"
    views_path.write_text(source_views.read_text(encoding="utf-8"), encoding="utf-8")
    export_pilot_workspace(
        tables,
        shortlist,
        readiness,
        tmp_path / "processed",
        database_path,
        views_path,
    )
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT candidate_approved, verified_quote_count "
            "FROM vw_pilot_candidate_decision WHERE candidate_id = ?",
            (candidate_id,),
        ).fetchone()
    assert row == (0, 1)
