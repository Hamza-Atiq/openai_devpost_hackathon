from __future__ import annotations

import pytest
from app.agents.instructions import (
    ROLE_CONTRACTS,
    SOURCE_HIERARCHY,
    AgentEvidence,
    AgentOutputClaims,
    OutputViolationCode,
    build_agent_instructions,
    evaluate_output_claims,
)
from app.agents.schemas import AgentRole


def test_all_role_turn_and_output_budgets_match_spec() -> None:
    expected = {
        AgentRole.TOURNAMENT_DIRECTOR: (8, 900),
        AgentRole.RULES_CONSTRAINT: (4, 600),
        AgentRole.SCHEDULING_STRATEGY: (4, 600),
        AgentRole.WEATHER_INTELLIGENCE: (4, 600),
        AgentRole.FAIRNESS_LOGISTICS: (3, 500),
        AgentRole.DISRUPTION_RECOVERY: (5, 700),
    }

    assert {
        role: (contract.max_turns, contract.output_token_budget)
        for role, contract in ROLE_CONTRACTS.items()
    } == expected


@pytest.mark.parametrize("role", tuple(AgentRole))
def test_every_role_receives_shared_hierarchy_and_safety_language(role: AgentRole) -> None:
    instructions = build_agent_instructions(role)

    hierarchy_positions = tuple(instructions.index(source) for source in SOURCE_HIERARCHY)
    assert hierarchy_positions == tuple(sorted(hierarchy_positions))
    assert "I do not have enough validated evidence to determine that" in instructions
    assert "Do not request or expose hidden reasoning" in instructions
    assert "Deterministic tool failures remain typed failures" in instructions
    assert "explicit organizer approval" in instructions


def test_weather_contract_requires_forecast_uncertainty_and_forbids_nowcasting_claims() -> None:
    instructions = build_agent_instructions(AgentRole.WEATHER_INTELLIGENCE)

    assert "forecast-based risk" in instructions
    assert "coverage and issue time" in instructions
    assert "radar nowcasting" in instructions
    assert "official safety decision" in instructions


@pytest.mark.parametrize(
    ("claims", "expected_code"),
    [
        (
            AgentOutputClaims(text="Move fixture S99.", fixture_ids=("S99",)),
            OutputViolationCode.INVENTED_FIXTURE,
        ),
        (
            AgentOutputClaims(text="Weather risk is 22.", metric_claims={"weather_risk": 22}),
            OutputViolationCode.INVENTED_METRIC,
        ),
        (
            AgentOutputClaims(text="Here is my chain of thought and hidden reasoning."),
            OutputViolationCode.HIDDEN_REASONING,
        ),
        (
            AgentOutputClaims(
                text="I silently reduced minimum rest.", claims_hard_constraint_change=True
            ),
            OutputViolationCode.UNCONFIRMED_HARD_CONSTRAINT_CHANGE,
        ),
        (
            AgentOutputClaims(text="Radar guarantees this match will not be washed out."),
            OutputViolationCode.UNSUPPORTED_WEATHER_CLAIM,
        ),
        (
            AgentOutputClaims(text="I approved and published the schedule for you."),
            OutputViolationCode.UNAUTHORIZED_APPROVAL,
        ),
    ],
)
def test_adversarial_claims_are_rejected(
    claims: AgentOutputClaims, expected_code: OutputViolationCode
) -> None:
    report = evaluate_output_claims(
        claims,
        AgentEvidence(
            fixture_ids=("S14",),
            metrics={"weather_risk": 31.2},
            confirmed_hard_constraint_change=False,
        ),
    )

    assert report.valid is False
    assert expected_code in report.violations


def test_grounded_output_passes_contract() -> None:
    report = evaluate_output_claims(
        AgentOutputClaims(
            text=(
                "Fixture S14 has forecast-based risk 31.2 at the recorded issue time; "
                "select Approve schedule if you want to make the draft official."
            ),
            fixture_ids=("S14",),
            metric_claims={"weather_risk": 31.2},
        ),
        AgentEvidence(
            fixture_ids=("S14",),
            metrics={"weather_risk": 31.2},
            confirmed_hard_constraint_change=False,
        ),
    )

    assert report.valid is True
    assert report.violations == ()
