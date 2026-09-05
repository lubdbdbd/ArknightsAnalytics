from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from arknights_merch_analytics.survey_simulation import (  # noqa: E402
    SIMULATION_SEED,
    build_simulation_outputs,
    generate_simulated_survey_responses,
    validate_simulated_responses,
    write_simulated_survey_report,
)


def main() -> None:
    simulated = generate_simulated_survey_responses(
        ROOT / "data" / "processed" / "operator_heat.csv",
        ROOT / "data" / "manual" / "product_categories.csv",
        size=200,
        seed=SIMULATION_SEED,
    )
    valid, audit = validate_simulated_responses(simulated)
    if len(valid) != 200 or not audit["valid"].all():
        failures = audit.loc[~audit["valid"]]
        raise RuntimeError(f"Simulated survey failed validation:\n{failures.to_string(index=False)}")

    output_dir = ROOT / "data" / "simulated"
    processed_dir = ROOT / "data" / "processed"
    report_path = ROOT / "reports" / "generated" / "simulated_user_research_report.md"
    output_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    valid.to_csv(output_dir / "survey_responses_200.csv", index=False, encoding="utf-8-sig")
    audit.to_csv(output_dir / "survey_response_audit_200.csv", index=False, encoding="utf-8-sig")
    outputs = build_simulation_outputs(valid)
    for name, frame in outputs.items():
        frame.to_csv(
            processed_dir / f"simulated_survey_{name}_summary.csv",
            index=False,
            encoding="utf-8-sig",
        )
    write_simulated_survey_report(valid, audit, outputs, report_path)
    print(f"Generated {len(valid)} simulated survey responses with seed {SIMULATION_SEED}")
    print(f"Dataset: {output_dir / 'survey_responses_200.csv'}")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
