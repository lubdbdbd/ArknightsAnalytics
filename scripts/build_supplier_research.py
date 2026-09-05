from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from arknights_merch_analytics.pilot import load_pilot_tables
from arknights_merch_analytics.supplier_research import (
    build_supplier_public_leads,
    export_supplier_research,
    summarize_supplier_sourcing_gap,
)


def main() -> None:
    shortlist = pd.read_csv(ROOT / "data" / "processed" / "pilot_candidate_shortlist.csv")
    snapshots = pd.read_csv(ROOT / "data" / "processed" / "taobao_public_snapshots.csv")
    tables = load_pilot_tables(ROOT / "data" / "manual" / "commercial_pilot")
    public_leads = build_supplier_public_leads(
        snapshots,
        shortlist,
        tables["pilot_candidate_decisions"],
    )
    sourcing_gap = summarize_supplier_sourcing_gap(
        shortlist,
        tables["pilot_candidate_decisions"],
        tables["pilot_supplier_quotes"],
        public_leads,
    )
    export_supplier_research(
        public_leads,
        sourcing_gap,
        ROOT / "data" / "processed",
        ROOT / "reports" / "generated" / "supplier_sourcing_gap_report.md",
    )
    print(
        f"Supplier research built: {len(public_leads)} public leads, "
        f"{int(sourcing_gap['supplier_quote_gap'].sum()) if not sourcing_gap.empty else 0} quote gaps"
    )


if __name__ == "__main__":
    main()
