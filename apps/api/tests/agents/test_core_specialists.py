from __future__ import annotations

import json
from pathlib import Path

import pytest
from agents import function_tool
from app.agents.director import DirectorTurnInput, DirectorTurnOutput, create_director_agent
from app.agents.rules import (
    ConstraintInterpretationInput,
    ConstraintInterpretationOutput,
    create_rules_agent,
    validate_constraint_interpretation,
)
from app.agents.schemas import AgentMode
from app.agents.strategy import (
    StrategyInput,
    StrategyOutput,
    create_strategy_agent,
    validate_strategy_output,
)

EVAL_ROOT = Path(__file__).resolve().parents[4] / "evals" / "cases" / "agents"


def _case(name: str) -> dict[str, object]:
    return json.loads((EVAL_ROOT / name).read_text(encoding="utf-8"))


def test_director_agent_owns_reply_and_uses_typed_evidence_output() -> None:
    case = _case("director-golden.json")
    turn_input = DirectorTurnInput.model_validate(case["input"])
    output = DirectorTurnOutput.model_validate(case["output"])
    agent = create_director_agent()

    assert turn_input.mode is AgentMode.GPT_5_6
    assert agent.name == "Tournament Director"
    assert agent.model == "gpt-5.6"
    assert agent.output_type is DirectorTurnOutput
    assert output.evidence_refs[0].consumed_fields == (
        "validation_status",
        "weather_risk",
    )
    assert output.ui_actions[0].action == "request_schedule_approval"


def test_rules_agent_requires_targeted_clarification_for_ambiguity() -> None:
    case = _case("rules-ambiguity.json")
    turn_input = ConstraintInterpretationInput.model_validate(case["input"])
    output = ConstraintInterpretationOutput.model_validate(case["output"])

    validate_constraint_interpretation(turn_input, output)
    assert create_rules_agent().output_type is ConstraintInterpretationOutput
    assert output.clarification_question is not None
    assert len(output.ambiguities) == 1


def test_rules_agent_rejects_ambiguity_without_clarification() -> None:
    case = _case("rules-ambiguity.json")
    turn_input = ConstraintInterpretationInput.model_validate(case["input"])
    output = ConstraintInterpretationOutput.model_validate(
        case["output"] | {"clarification_question": None}
    )

    with pytest.raises(ValueError, match="targeted clarification"):
        validate_constraint_interpretation(turn_input, output)


def test_strategy_recommendation_requires_validated_metrics_and_consumed_evidence() -> None:
    case = _case("strategy-no-metrics.json")
    turn_input = StrategyInput.model_validate(case["input"])
    output = StrategyOutput.model_validate(case["output"])

    with pytest.raises(ValueError, match="validated metrics"):
        validate_strategy_output(turn_input, output)
    assert create_strategy_agent().output_type is StrategyOutput


def test_strategy_golden_recommendation_consumes_validated_comparison() -> None:
    case = _case("strategy-golden.json")
    turn_input = StrategyInput.model_validate(case["input"])
    output = StrategyOutput.model_validate(case["output"])

    assert validate_strategy_output(turn_input, output) is output
    assert output.recommendation == "balanced"
    assert output.evidence_refs[0].consumed_fields == (
        "weather_risk",
        "group_rest_fairness",
        "preference_satisfaction",
    )


@function_tool
def forbidden_fixture_creator() -> str:
    """Create fixtures directly, which no specialist may do."""
    return "unsafe"


@pytest.mark.parametrize(
    "factory",
    (create_director_agent, create_rules_agent, create_strategy_agent),
)
def test_specialists_reject_tools_outside_their_narrow_allowlist(factory) -> None:
    with pytest.raises(ValueError, match="not allowed"):
        factory(tools=(forbidden_fixture_creator,))
