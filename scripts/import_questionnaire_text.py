from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from arknights_merch_analytics.survey_text_import import (
    build_questionnaire_summaries,
    parse_questionnaire_text,
    write_questionnaire_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import the anonymous 25-question text export into auditable CSV tables."
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("--batch-id", default="ARK-SURVEY-20260903")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    imported = parse_questionnaire_text(args.source, batch_id=args.batch_id)
    summaries = build_questionnaire_summaries(imported)
    simulated_dir = ROOT / "data" / "survey"
    processed_dir = ROOT / "data" / "processed"
    simulated_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    imported.responses.to_csv(
        simulated_dir / "anonymous_responses_243.csv", index=False, encoding="utf-8-sig"
    )
    imported.responses.to_csv(
        ROOT / "data" / "manual" / "user_survey_responses.csv",
        index=False,
        encoding="utf-8-sig",
    )
    imported.operator_rankings.to_csv(
        simulated_dir / "anonymous_operator_rankings_243.csv",
        index=False,
        encoding="utf-8-sig",
    )
    imported.category_prices.to_csv(
        simulated_dir / "anonymous_category_prices_243.csv",
        index=False,
        encoding="utf-8-sig",
    )
    imported.audit.to_csv(
        simulated_dir / "anonymous_response_audit_243.csv", index=False, encoding="utf-8-sig"
    )
    for name, frame in summaries.items():
        frame.to_csv(
            processed_dir / f"survey_243_{name}_summary.csv",
            index=False,
            encoding="utf-8-sig",
        )
    write_questionnaire_report(
        imported,
        summaries,
        ROOT / "reports" / "generated" / "user_research_report.md",
    )
    print(
        f"Imported {len(imported.responses)} valid responses from {len(imported.audit)} records; "
        f"generated {len(imported.operator_rankings)} operator rankings and "
        f"{len(imported.category_prices)} category price observations."
    )


if __name__ == "__main__":
    main()
