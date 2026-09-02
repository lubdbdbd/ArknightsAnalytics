from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from arknights_merch_analytics.survey import validate_survey_responses


PII_COLUMNS = {"name", "real_name", "phone", "mobile", "email", "wechat", "qq", "ip", "address"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate and import anonymous real survey responses")
    parser.add_argument("input", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "manual" / "user_survey_responses.csv",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    frame = pd.read_csv(args.input)
    forbidden = PII_COLUMNS.intersection(column.lower() for column in frame.columns)
    if forbidden:
        raise SystemExit(f"Remove personal-identifying columns before import: {sorted(forbidden)}")
    valid, audit = validate_survey_responses(frame)
    audit_path = ROOT / "data" / "processed" / "survey_import_audit.csv"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(audit_path, index=False, encoding="utf-8-sig")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    valid.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(
        f"Imported {len(valid)} valid rows; excluded {len(frame) - len(valid)} rows. "
        f"Audit: {audit_path}"
    )


if __name__ == "__main__":
    main()
