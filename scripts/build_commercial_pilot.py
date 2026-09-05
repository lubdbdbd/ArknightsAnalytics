from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from arknights_merch_analytics.pilot import (
    build_pilot_candidate_shortlist,
    create_pilot_templates,
    export_pilot_workspace,
    load_pilot_tables,
    summarize_pilot_readiness,
    validate_pilot_tables,
    write_pilot_report,
)
from arknights_merch_analytics.supplier_research import (
    build_supplier_public_leads,
    export_supplier_research,
    summarize_supplier_sourcing_gap,
)


def main() -> None:
    manual_dir = ROOT / "data" / "manual" / "commercial_pilot"
    create_pilot_templates(manual_dir)
    tables = load_pilot_tables(manual_dir)
    validate_pilot_tables(tables)
    shortlist = build_pilot_candidate_shortlist(
        pd.read_csv(ROOT / "data" / "processed" / "content_commerce_matrix.csv"),
        pd.read_csv(ROOT / "data" / "processed" / "survey_243_operator_summary.csv"),
        pd.read_csv(ROOT / "data" / "processed" / "survey_243_category_summary.csv"),
        pd.read_csv(ROOT / "data" / "processed" / "survey_operator_category_summary.csv"),
    )
    readiness = summarize_pilot_readiness(shortlist, tables)
    export_pilot_workspace(
        tables,
        shortlist,
        readiness,
        ROOT / "data" / "processed",
        ROOT / "reports" / "generated" / "operations.db",
        ROOT / "sql" / "pilot_views.sql",
    )
    write_pilot_report(
        shortlist,
        readiness,
        tables["pilot_candidate_decisions"],
        ROOT / "reports" / "generated" / "commercial_pilot_report.md",
    )
    public_leads = build_supplier_public_leads(
        pd.read_csv(ROOT / "data" / "processed" / "taobao_public_snapshots.csv"),
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
        f"Commercial pilot workspace built: {len(shortlist)} candidates, "
        f"{sum(len(frame) for frame in tables.values())} actual pilot rows"
    )


if __name__ == "__main__":
    main()
