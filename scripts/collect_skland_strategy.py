from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from arknights_merch_analytics.skland import collect_skland_strategy_search, export_skland_snapshot


def main() -> None:
    heat = pd.read_csv(ROOT / "data" / "processed" / "character_heat_matrix.csv")
    survey = pd.read_csv(ROOT / "data" / "processed" / "survey_243_operator_summary.csv")
    operators = sorted(set(heat["operator"].dropna()) | set(survey["operator"].dropna()))
    snapshot = collect_skland_strategy_search(operators)
    export_skland_snapshot(
        snapshot,
        ROOT / "data" / "public" / "skland_strategy_operator_search_snapshot.csv",
        ROOT / "data" / "processed" / "skland_operator_summary.csv",
    )
    matched = int(snapshot["direct_name_match"].sum()) if not snapshot.empty else 0
    print(
        f"Collected {len(snapshot)} public Skland search rows for {len(operators)} operators; "
        f"direct-name matched rows={matched}."
    )


if __name__ == "__main__":
    main()
