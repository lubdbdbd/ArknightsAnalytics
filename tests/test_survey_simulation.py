from __future__ import annotations

from pathlib import Path

from arknights_merch_analytics.survey_simulation import (
    build_simulation_outputs,
    generate_simulated_survey_responses,
    validate_simulated_responses,
    write_simulated_survey_report,
)


ROOT = Path(__file__).resolve().parents[1]


def _generate():
    return generate_simulated_survey_responses(
        ROOT / "data" / "processed" / "operator_heat.csv",
        ROOT / "data" / "manual" / "product_categories.csv",
        size=200,
        seed=20260903,
    )


def test_simulation_is_deterministic_and_student_led() -> None:
    first = _generate()
    second = _generate()

    assert len(first) == 200
    assert first["response_id"].is_unique
    assert first["respondent_id"].is_unique
    assert first["age_band"].eq("18～22岁").sum() == 152
    assert first["is_simulated"].all()
    assert first["data_type"].eq("synthetic_persona").all()
    assert "丰川祥子" not in set(first["operator"])
    assert first.head(10).equals(second.head(10))


def test_simulation_passes_quality_gate_and_isolated_report(tmp_path: Path) -> None:
    responses = _generate()
    valid, audit = validate_simulated_responses(responses)
    outputs = build_simulation_outputs(valid)
    report_path = tmp_path / "simulated_report.md"
    write_simulated_survey_report(valid, audit, outputs, report_path)

    assert len(valid) == 200
    assert audit["valid"].all()
    assert not valid["is_real_survey_response"].any()
    assert valid["purchase_intent"].between(1, 5).all()
    assert valid["price_too_cheap"].le(valid["price_good_value"]).all()
    assert valid["price_good_value"].le(valid["price_expensive"]).all()
    assert valid["price_expensive"].le(valid["price_too_expensive"]).all()
    assert outputs["segment"]["respondent_count"].sum() == 200
    report = report_path.read_text(encoding="utf-8")
    assert "不是真实用户调研结果" in report
    assert "is_simulated=true" in report
