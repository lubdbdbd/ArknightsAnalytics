from __future__ import annotations

from pathlib import Path

import pandas as pd


SUPPLIER_GATE = 3


def _mentions_operator(value: object, operator: str) -> bool:
    mentions = {item.strip() for item in str(value or "").split("|") if item.strip()}
    return operator in mentions


def _seller_hint(raw_text: object) -> str:
    parts = str(raw_text or "").strip().split()
    return parts[-1] if parts else ""


def build_supplier_public_leads(
    snapshots: pd.DataFrame,
    shortlist: pd.DataFrame,
    decisions: pd.DataFrame,
) -> pd.DataFrame:
    columns = [
        "lead_id",
        "candidate_id",
        "operator",
        "candidate_category",
        "observed_category",
        "evidence_scope",
        "seller_hint",
        "item_id",
        "item_url",
        "observed_price",
        "sales_proxy_min",
        "snapshot_at",
        "public_rights_signal",
        "contact_status",
        "quote_status",
        "rights_verification_status",
        "data_type",
        "is_simulated",
    ]
    if decisions.empty or snapshots.empty:
        return pd.DataFrame(columns=columns)

    approved_ids = set(
        decisions.loc[decisions["decision"].eq("approved"), "candidate_id"]
    )
    approved = shortlist.loc[shortlist["candidate_id"].isin(approved_ids)]
    eligible_snapshots = snapshots.loc[
        snapshots["rights_type"].eq("官方/授权")
        & snapshots["target_relevance"].fillna(0).ge(0.8)
    ].copy()
    records: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for candidate in approved.itertuples(index=False):
        operator_rows = eligible_snapshots.loc[
            eligible_snapshots["operator_mentions"].map(
                lambda value: _mentions_operator(value, candidate.operator)
            )
        ]
        for snapshot in operator_rows.itertuples(index=False):
            identity = (candidate.candidate_id, str(snapshot.item_id))
            if identity in seen:
                continue
            seen.add(identity)
            evidence_scope = (
                "direct_candidate_category"
                if snapshot.category == candidate.category
                else "adjacent_role_category"
            )
            records.append(
                {
                    "lead_id": f"PUBLIC-{len(records) + 1:03d}",
                    "candidate_id": candidate.candidate_id,
                    "operator": candidate.operator,
                    "candidate_category": candidate.category,
                    "observed_category": snapshot.category,
                    "evidence_scope": evidence_scope,
                    "seller_hint": _seller_hint(snapshot.raw_text),
                    "item_id": str(snapshot.item_id),
                    "item_url": snapshot.url,
                    "observed_price": snapshot.price,
                    "sales_proxy_min": snapshot.sales_proxy_min,
                    "snapshot_at": snapshot.snapshot_at,
                    "public_rights_signal": snapshot.rights_type,
                    "contact_status": "not_contacted",
                    "quote_status": "not_a_quote",
                    "rights_verification_status": "requires_direct_verification",
                    "data_type": "public_retail_lead",
                    "is_simulated": False,
                }
            )
    return pd.DataFrame(records, columns=columns)


def summarize_supplier_sourcing_gap(
    shortlist: pd.DataFrame,
    decisions: pd.DataFrame,
    quotes: pd.DataFrame,
    public_leads: pd.DataFrame,
) -> pd.DataFrame:
    columns = [
        "candidate_id",
        "operator",
        "category",
        "direct_public_lead_count",
        "adjacent_role_evidence_count",
        "rights_verified_supplier_count",
        "supplier_quote_gap",
        "status",
        "next_action",
    ]
    approved_ids = set(
        decisions.loc[decisions["decision"].eq("approved"), "candidate_id"]
    ) if not decisions.empty else set()
    approved = shortlist.loc[shortlist["candidate_id"].isin(approved_ids)]
    records = []
    for candidate in approved.itertuples(index=False):
        candidate_leads = public_leads.loc[
            public_leads["candidate_id"].eq(candidate.candidate_id)
        ] if not public_leads.empty else public_leads
        candidate_quotes = quotes.loc[
            quotes["candidate_id"].eq(candidate.candidate_id)
            & quotes["rights_verified"].fillna(False)
        ] if not quotes.empty else quotes
        verified_count = (
            candidate_quotes["supplier_code"].nunique() if not candidate_quotes.empty else 0
        )
        quote_gap = max(SUPPLIER_GATE - verified_count, 0)
        records.append(
            {
                "candidate_id": candidate.candidate_id,
                "operator": candidate.operator,
                "category": candidate.category,
                "direct_public_lead_count": int(
                    candidate_leads["evidence_scope"].eq("direct_candidate_category").sum()
                ) if not candidate_leads.empty else 0,
                "adjacent_role_evidence_count": int(
                    candidate_leads["evidence_scope"].eq("adjacent_role_category").sum()
                ) if not candidate_leads.empty else 0,
                "rights_verified_supplier_count": verified_count,
                "supplier_quote_gap": quote_gap,
                "status": "complete" if quote_gap == 0 else "blocked",
                "next_action": (
                    "进入样品与交期比价"
                    if quote_gap == 0
                    else f"仍需取得{quote_gap}家独立供应商的授权证据与有效报价"
                ),
            }
        )
    return pd.DataFrame(records, columns=columns)


def export_supplier_research(
    public_leads: pd.DataFrame,
    sourcing_gap: pd.DataFrame,
    processed_dir: Path,
    report_path: Path,
) -> None:
    processed_dir.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    public_leads.to_csv(
        processed_dir / "pilot_supplier_public_leads.csv",
        index=False,
        encoding="utf-8-sig",
    )
    sourcing_gap.to_csv(
        processed_dir / "pilot_supplier_sourcing_gap.csv",
        index=False,
        encoding="utf-8-sig",
    )
    lines = [
        "# 供应商寻源缺口报告",
        "",
        "> 本报告只整理公开零售商品线索，不代表已联系供应商、取得报价或完成授权核验。",
        "",
        f"- 公开线索关联记录：{len(public_leads)} 条",
        f"- 去重公开商品：{public_leads['item_id'].nunique() if not public_leads.empty else 0} 个",
        f"- 已批准商品方案：{len(sourcing_gap)} 个",
        f"- 已完成供应商门禁：{int(sourcing_gap['status'].eq('complete').sum()) if not sourcing_gap.empty else 0} 个",
        "",
    ]
    if not sourcing_gap.empty:
        lines.extend(["## 分方案缺口", "", sourcing_gap.to_markdown(index=False), ""])
    if not public_leads.empty:
        lines.extend(["## 公开线索", "", public_leads.to_markdown(index=False), ""])
    report_path.write_text("\n".join(lines), encoding="utf-8")
