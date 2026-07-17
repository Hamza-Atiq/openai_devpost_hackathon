from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from agents import RunConfig, Runner  # noqa: E402
from app.agents.director import DirectorTurnOutput, create_director_agent  # noqa: E402
from app.agents.fairness import (  # noqa: E402
    FairnessAuditInput,
    FairnessAuditOutput,
    create_fairness_agent,
    validate_fairness_audit,
)
from app.agents.recovery import (  # noqa: E402
    RecoveryInput,
    RecoveryOptionEvidence,
    RecoveryOutput,
    create_recovery_agent,
    validate_recovery_output,
)
from app.agents.rules import (  # noqa: E402
    ConstraintInterpretationInput,
    ConstraintInterpretationOutput,
    create_rules_agent,
    validate_constraint_interpretation,
)
from app.agents.schemas import AgentMode  # noqa: E402
from app.agents.strategy import (  # noqa: E402
    StrategyInput,
    StrategyOutput,
    create_strategy_agent,
    validate_strategy_output,
)
from app.agents.weather import (  # noqa: E402
    FixtureRiskEvidence,
    VenueWeatherEvidence,
    WeatherAnalysisInput,
    WeatherAnalysisOutput,
    create_weather_agent,
    validate_weather_analysis,
)
from app.domain.schedules import ScheduleDiff, ScheduleProfile  # noqa: E402

MODEL = "gpt-5.6"
_SECRET = re.compile(r"\bsk-[A-Za-z0-9_-]+\b")
ROLE_ORDER = (
    "rules_constraint",
    "scheduling_strategy",
    "weather_intelligence",
    "fairness_logistics",
    "disruption_recovery",
    "tournament_director",
)


@dataclass(frozen=True)
class SmokeCall:
    role: str
    agent: Any
    prompt: str
    output_type: type[Any]
    validate: Callable[[Any], Any]


def _json_prompt(task: str, evidence: Any) -> str:
    return (
        f"{task}\nUse only the following deterministic evidence. Do not invent facts. "
        "Return the configured structured output schema.\nEVIDENCE:\n"
        f"{json.dumps(evidence, default=str, sort_keys=True)}"
    )


def _calls() -> tuple[SmokeCall, ...]:
    fetched_at = datetime(2026, 7, 16, 8, 0, tzinfo=UTC)
    rules_input = ConstraintInterpretationInput(
        current_constraints=("exactly 8 teams", "T20 allocation 240 minutes"),
        user_text="Prefer weekends for high-audience matches.",
        tournament_context={"format": "T20", "teams": 8, "venues": 2},
    )
    strategy_input = StrategyInput(
        confirmed_constraints=rules_input.current_constraints,
        priorities={"minimize_weather_risk": True, "maximize_fair_rest": True},
        available_profiles=(
            ScheduleProfile.BALANCED,
            ScheduleProfile.WEATHER_FIRST,
            ScheduleProfile.FAIRNESS_FIRST,
        ),
    )
    weather_input = WeatherAnalysisInput(
        venue_snapshots=(
            VenueWeatherEvidence(
                venue_id="venue-a", provider_state="fresh", fetched_at=fetched_at
            ),
        ),
        fixture_risks={
            "G07": FixtureRiskEvidence(risk=78, covered=True, quality="complete")
        },
        weather_coverage=100,
        mode=AgentMode.GPT_5_6,
    )
    fairness_input = FairnessAuditInput(
        schedule_id="balanced-draft",
        validation_valid=True,
        metric_version="schedule-metrics/v1",
        metrics={"group_rest_fairness": 92.0, "venue_balance": 94.0},
        team_breakdown={"team-a": {"minimum_rest_hours": 24.0}},
    )

    official_id = "0190f2f0-0000-7000-8000-000000000001"
    draft_id = "0190f2f0-0000-7000-8000-000000000002"
    affected_id = "0190f2f0-0000-7000-8000-000000000003"
    preserved_id = "0190f2f0-0000-7000-8000-000000000004"
    diff = ScheduleDiff(
        baseline_version_id=official_id,
        draft_id=draft_id,
        unchanged=(preserved_id,),
        moved=(affected_id,),
        metric_deltas={"weather_risk": -12.0, "group_rest_fairness": -1.0},
    )
    recovery_input = RecoveryInput(
        official_version_id=official_id,
        disruption_kind="rain",
        unavailable_slot_ids=("0190f2f0-0000-7000-8000-000000000005",),
        affected_fixture_ids=(affected_id,),
        validated_repairs=(
            RecoveryOptionEvidence(draft_id=draft_id, validation_valid=True, diff=diff),
        ),
    )

    evidence_ref = {
        "evidence_id": "smoke-evidence-v1",
        "evidence_kind": "deterministic_input",
        "revision": 1,
        "consumed_fields": ["format", "teams", "venues"],
    }
    calls = (
        SmokeCall(
            "rules_constraint",
            create_rules_agent(model=MODEL),
            _json_prompt(
                "Interpret the preference as one preferred addition, with no ambiguity "
                "or contradiction.",
                {"input": rules_input.model_dump(mode="json"), "evidence_ref": evidence_ref},
            ),
            ConstraintInterpretationOutput,
            lambda output: validate_constraint_interpretation(rules_input, output),
        ),
        SmokeCall(
            "scheduling_strategy",
            create_strategy_agent(model=MODEL),
            _json_prompt(
                "Request all three available profiles. Do not recommend or compare "
                "because validated metrics are absent.",
                {"input": strategy_input.model_dump(mode="json"), "evidence_ref": evidence_ref},
            ),
            StrategyOutput,
            lambda output: validate_strategy_output(strategy_input, output),
        ),
        SmokeCall(
            "weather_intelligence",
            create_weather_agent(model=MODEL),
            _json_prompt(
                "Identify G07 as high risk, preserve the required disclaimer, and make "
                "no unsupported claim.",
                {"input": weather_input.model_dump(mode="json"), "evidence_ref": evidence_ref},
            ),
            WeatherAnalysisOutput,
            lambda output: validate_weather_analysis(weather_input, output),
        ),
        SmokeCall(
            "fairness_logistics",
            create_fairness_agent(model=MODEL),
            _json_prompt(
                "Audit only the supplied valid metrics. Include group and potential-knockout "
                "rest summaries and the required fairness boundary.",
                {"input": fairness_input.model_dump(mode="json"), "evidence_ref": evidence_ref},
            ),
            FairnessAuditOutput,
            lambda output: validate_fairness_audit(fairness_input, output),
        ),
        SmokeCall(
            "disruption_recovery",
            create_recovery_agent(model=MODEL),
            _json_prompt(
                "Explain the validated repair exactly: one preserved, one moved, zero "
                "added/removed. Recommend its draft and cite evidence_kind "
                "validated_schedule_diff.",
                {
                    "input": recovery_input.model_dump(mode="json"),
                    "diff": diff.model_dump(mode="json"),
                },
            ),
            RecoveryOutput,
            lambda output: validate_recovery_output(recovery_input, output),
        ),
        SmokeCall(
            "tournament_director",
            create_director_agent(model=MODEL),
            _json_prompt(
                "Give a concise organizer-facing recovery summary and expose review_repair "
                "as an explicit UI action. Do not claim external publication.",
                {
                    "official_version": 1,
                    "repair_draft": draft_id,
                    "moved": 1,
                    "preserved": 1,
                    "evidence_ref": {
                        **evidence_ref,
                        "evidence_kind": "validated_schedule_diff",
                        "consumed_fields": ["moved", "unchanged", "metric_deltas"],
                    },
                },
            ),
            DirectorTurnOutput,
            lambda output: output,
        ),
    )
    return calls


async def _run_live(timeout_seconds: float) -> dict[str, Any]:
    started = perf_counter()
    validated_roles: list[str] = []
    run_config = RunConfig(trace_include_sensitive_data=False)
    for call in _calls():
        try:
            result = await asyncio.wait_for(
                Runner.run(call.agent, call.prompt, max_turns=2, run_config=run_config),
                timeout=timeout_seconds,
            )
            output = result.final_output_as(
                call.output_type, raise_if_incorrect_type=True
            )
            call.validate(output)
        except Exception as exc:
            return _failed_report(
                exc,
                validated_roles=validated_roles,
                failing_role=call.role,
            )
        validated_roles.append(call.role)
    return {
        "schema_version": "gpt-smoke/v1",
        "status": "passed",
        "model": MODEL,
        "genuine_model_calls": len(validated_roles),
        "validated_roles": validated_roles,
        "fabricated_response": False,
        "duration_seconds": round(perf_counter() - started, 3),
        "validation": "shared Pydantic schemas plus deterministic role validators",
    }


def _safe_error_details(exc: Exception) -> dict[str, Any]:
    message = str(getattr(exc, "message", None) or exc)[:500]
    details: dict[str, Any] = {
        "error_type": type(exc).__name__,
        "error_message": _SECRET.sub("[REDACTED]", message),
    }
    for source, target in (
        ("status_code", "error_status"),
        ("code", "error_code"),
        ("param", "error_param"),
    ):
        value = getattr(exc, source, None)
        if value is not None:
            details[target] = value
    return {
        key: details[key]
        for key in (
            "error_type",
            "error_status",
            "error_code",
            "error_param",
            "error_message",
        )
        if key in details
    }


def _failed_report(
    exc: Exception,
    *,
    validated_roles: list[str],
    failing_role: str,
) -> dict[str, Any]:
    return {
        "schema_version": "gpt-smoke/v1",
        "status": "failed",
        "model": MODEL,
        "genuine_model_calls": len(validated_roles),
        "validated_roles": list(validated_roles),
        "failing_role": failing_role,
        "fabricated_response": False,
        **_safe_error_details(exc),
    }


def run_gpt_smoke(*, timeout_seconds: float = 45.0) -> dict[str, Any]:
    if not os.environ.get("OPENAI_API_KEY"):
        return {
            "schema_version": "gpt-smoke/v1",
            "status": "missing_api_key",
            "model": MODEL,
            "genuine_model_calls": 0,
            "validated_roles": [],
            "fabricated_response": False,
        }
    try:
        return asyncio.run(_run_live(timeout_seconds))
    except Exception as exc:  # safe evidence; prompts and secrets are deliberately excluded
        return _failed_report(exc, validated_roles=[], failing_role="setup")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the genuine GPT-5.6 six-role smoke gate")
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run_gpt_smoke(timeout_seconds=args.timeout)
    rendered = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
