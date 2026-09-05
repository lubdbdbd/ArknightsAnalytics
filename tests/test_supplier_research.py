from __future__ import annotations

import pandas as pd

from arknights_merch_analytics.supplier_research import (
    build_supplier_public_leads,
    summarize_supplier_sourcing_gap,
)


def _shortlist() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "candidate_id": "CAND-002",
                "operator": "新约能天使",
                "category": "亚克力制品",
            },
            {
                "candidate_id": "CAND-006",
                "operator": "新约能天使",
                "category": "吧唧（徽章）",
            },
        ]
    )


def _decisions() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"candidate_id": "CAND-002", "decision": "approved"},
            {"candidate_id": "CAND-006", "decision": "approved"},
        ]
    )


def test_public_retail_evidence_is_not_treated_as_supplier_quote() -> None:
    snapshots = pd.DataFrame(
        [
            {
                "item_id": "1",
                "url": "https://item.taobao.com/item.htm?id=1",
                "operator_mentions": "新约能天使",
                "category": "毛绒玩偶",
                "rights_type": "官方/授权",
                "target_relevance": 1.0,
                "price": 104.0,
                "sales_proxy_min": 100,
                "snapshot_at": "2026-09-02T11:46:26+08:00",
                "raw_text": "官方正版 新约能天使 毛绒 梦谷小屋",
            }
        ]
    )
    leads = build_supplier_public_leads(snapshots, _shortlist(), _decisions())
    assert len(leads) == 2
    assert set(leads["quote_status"]) == {"not_a_quote"}
    assert set(leads["rights_verification_status"]) == {"requires_direct_verification"}
    assert set(leads["evidence_scope"]) == {"adjacent_role_category"}


def test_supplier_gap_counts_unique_rights_verified_suppliers_per_candidate() -> None:
    leads = pd.DataFrame(
        columns=["candidate_id", "evidence_scope"]
    )
    quotes = pd.DataFrame(
        [
            {
                "candidate_id": "CAND-002",
                "supplier_code": "SUP-001",
                "rights_verified": True,
            },
            {
                "candidate_id": "CAND-002",
                "supplier_code": "SUP-001",
                "rights_verified": True,
            },
            {
                "candidate_id": "CAND-006",
                "supplier_code": "SUP-002",
                "rights_verified": False,
            },
        ]
    )
    summary = summarize_supplier_sourcing_gap(_shortlist(), _decisions(), quotes, leads)
    acrylic = summary.loc[summary["candidate_id"].eq("CAND-002")].iloc[0]
    badge = summary.loc[summary["candidate_id"].eq("CAND-006")].iloc[0]
    assert acrylic["rights_verified_supplier_count"] == 1
    assert acrylic["supplier_quote_gap"] == 2
    assert badge["rights_verified_supplier_count"] == 0
    assert badge["supplier_quote_gap"] == 3
