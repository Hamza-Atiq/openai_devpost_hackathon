from __future__ import annotations

import json
from pathlib import Path

import pytest
from app.agents.fairness import (
    FairnessAuditInput,
    FairnessAuditOutput,
    create_fairness_agent,
    validate_fairness_audit,
)
from app.agents.weather import (
    WeatherAnalysisInput,
    WeatherAnalysisOutput,
    create_weather_agent,
    validate_weather_analysis,
)

EVAL_ROOT = Path(__file__).resolve().parents[4] / "evals" / "cases" / "agents"


def _case(name: str) -> dict[str, object]:
    return json.loads((EVAL_ROOT / name).read_text(encoding="utf-8"))


def test_weather_golden_explains_partial_coverage_and_guidance_boundary() -> None:
    case = _case("weather-golden.json")
    turn_input = WeatherAnalysisInput.model_validate(case["input"])
    output = WeatherAnalysisOutput.model_validate(case["output"])

    assert validate_weather_analysis(turn_input, output) is output
    assert create_weather_agent().output_type is WeatherAnalysisOutput
    assert "forecast-based" in output.guidance_disclaimer.lower()
    assert "official safety" in output.guidance_disclaimer
    assert output.uncertainty_notes


def test_weather_rejects_radar_guarantee() -> None:
    case = _case("weather-golden.json")
    turn_input = WeatherAnalysisInput.model_validate(case["input"])
    output = WeatherAnalysisOutput.model_validate(
        case["output"]
        | {"alternatives": ["Radar guarantees that fixture S14 will avoid a washout."]}
    )

    with pytest.raises(ValueError, match="unsupported weather claim"):
        validate_weather_analysis(turn_input, output)


def test_fairness_golden_separates_group_and_knockout_rest() -> None:
    case = _case("fairness-golden.json")
    turn_input = FairnessAuditInput.model_validate(case["input"])
    output = FairnessAuditOutput.model_validate(case["output"])

    assert validate_fairness_audit(turn_input, output) is output
    assert create_fairness_agent().output_type is FairnessAuditOutput
    assert output.group_rest_summary
    assert output.potential_knockout_rest_summary
    assert "not a universal definition" in output.fairness_boundary


def test_fairness_rejects_fabricated_metric_and_placeholder_overcount() -> None:
    case = _case("fairness-golden.json")
    turn_input = FairnessAuditInput.model_validate(case["input"])
    fabricated = FairnessAuditOutput.model_validate(
        case["output"]
        | {
            "metric_claims": {"group_rest_fairness": 99.9},
            "potential_knockout_rest_summary": (
                "Every qualification placeholder is an actual appearance for every team."
            ),
        }
    )

    with pytest.raises(ValueError, match="fabricated fairness metric"):
        validate_fairness_audit(turn_input, fabricated)

    placeholder_overcount = FairnessAuditOutput.model_validate(
        case["output"]
        | {
            "potential_knockout_rest_summary": (
                "Every qualification placeholder is an actual appearance for every team."
            )
        }
    )
    with pytest.raises(ValueError, match="placeholders"):
        validate_fairness_audit(turn_input, placeholder_overcount)


def test_fairness_rejects_invalid_schedule_before_explanation() -> None:
    case = _case("fairness-golden.json")
    turn_input = FairnessAuditInput.model_validate(case["input"] | {"validation_valid": False})
    output = FairnessAuditOutput.model_validate(case["output"])

    with pytest.raises(ValueError, match="independently validated"):
        validate_fairness_audit(turn_input, output)
