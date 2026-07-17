from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.agents.provider import AgentProviderRouter  # noqa: E402
from app.agents.resilience import AgentResilienceManager, TransientProviderError  # noqa: E402
from app.domain.matches import MatchStage  # noqa: E402
from app.domain.samples import load_sample  # noqa: E402
from app.domain.schedules import FixturePlacement  # noqa: E402
from app.domain.tournament import TournamentConfig  # noqa: E402
from app.domain.venues import SlotAvailability  # noqa: E402
from app.main import create_app  # noqa: E402
from app.observability.dependency_health import DependencyHealthRegistry  # noqa: E402
from app.scheduling.model import solve_hard_feasible_schedule  # noqa: E402
from app.scheduling.pairings import generate_match_graph  # noqa: E402
from app.scheduling.solver_result import (  # noqa: E402
    FeasibleSolverResult,
    InfeasibleSolverResult,
)
from app.validation.validator import validate_schedule  # noqa: E402
from app.validation.violations import ViolationCode  # noqa: E402
from app.weather.demo import load_demo_scenario, run_demo_scenario  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

CASE_DIRECTORY = ROOT / "evals" / "cases" / "v1"
EXPECTED_DIRECTORY = ROOT / "evals" / "expected" / "v1"
GENERATED_AT = datetime(2026, 7, 16, 12, tzinfo=UTC)


class EvaluationContext:
    def __init__(self) -> None:
        self.app = create_app()
        self.client = TestClient(self.app, base_url="https://testserver")
        self._hero: dict[str, Any] | None = None
        self._approved = False

    def hero(self) -> dict[str, Any]:
        if self._hero is not None:
            return self._hero
        created = self.client.post(
            "/api/v1/workspaces",
            json={"sample_id": "global-community-cup"},
        )
        revision = created.json()["tournament"]["revision"]
        confirmed = self.client.post(
            "/api/v1/constraints/confirm",
            json={
                "confirmation": True,
                "expected_revision": revision,
                "selection": {"match_format_preset": "T20", "allocation_minutes": 240},
            },
        )
        generated = self.client.post(
            "/api/v1/schedule-runs",
            headers={"Idempotency-Key": "eval-generation-v1"},
            json={"profiles": ["balanced", "weather_first", "fairness_first"]},
        )
        run = self.client.get(f"/api/v1/schedule-runs/{generated.json()['run_id']}").json()
        drafts = [
            self.client.get(f"/api/v1/schedule-drafts/{draft_id}").json()
            for draft_id in run["draft_ids"]
        ]
        self._hero = {
            "created": created,
            "confirmed": confirmed,
            "generated": generated,
            "run": run,
            "drafts": drafts,
        }
        return self._hero

    def approve_baseline(self) -> dict[str, object]:
        hero = self.hero()
        if not self._approved:
            response = self.client.post(
                f"/api/v1/schedule-drafts/{hero['run']['draft_ids'][0]}/approve",
                headers={"Idempotency-Key": "eval-approval-v1"},
                json={"confirmation": True},
            )
            response.raise_for_status()
            self._approved = True
        return self.client.get("/api/v1/schedule-versions").json()["items"][0]


def _format_case(_context: EvaluationContext) -> dict[str, object]:
    t20 = load_sample("global-community-cup")
    t10_payload = t20.model_dump(mode="python")
    t10_payload.update({"match_format_preset": "T10", "allocation_minutes": 120})
    t10 = TournamentConfig.model_validate(t10_payload)
    matches = generate_match_graph(t20)
    stages = Counter(match.stage for match in matches)
    preset_validity: dict[str, bool] = {}
    for tournament in (t10, t20):
        preset_matches = generate_match_graph(tournament)
        eligible = {
            match.id: frozenset(slot.id for slot in tournament.slots) for match in preset_matches
        }
        solved = solve_hard_feasible_schedule(
            tournament,
            preset_matches,
            eligible,
            max_time_seconds=5,
        )
        if not isinstance(solved, FeasibleSolverResult):
            preset_validity[tournament.match_format_preset.value] = False
            continue
        slots = {slot.id: slot for slot in tournament.slots}
        placements = tuple(
            FixturePlacement(
                match_id=placement.match_id,
                slot_id=placement.slot_id,
                venue_id=slots[placement.slot_id].venue_id,
                starts_at_utc=slots[placement.slot_id].starts_at_utc,
                ends_at_utc=slots[placement.slot_id].starts_at_utc
                + timedelta(minutes=tournament.allocation_minutes),
            )
            for placement in solved.placements
        )
        report = validate_schedule(
            tournament,
            preset_matches,
            placements,
            generated_at=GENERATED_AT,
        )
        preset_validity[tournament.match_format_preset.value] = report.valid
    return {
        "match_count": len(matches),
        "group_count": stages[MatchStage.GROUP],
        "semifinal_count": stages[MatchStage.SEMIFINAL],
        "final_count": stages[MatchStage.FINAL],
        "unique_match_count": len({match.id for match in matches}),
        "knockout_placeholders_valid": {
            (match.participant_a, match.participant_b)
            for match in matches
            if match.stage is MatchStage.SEMIFINAL
        }
        == {("A1", "B2"), ("B1", "A2")},
        "shared_timezone": len({venue.iana_time_zone for venue in t20.venues}) == 1,
        "preset_allocations": {"T10": 120, "T20": 240},
        "preset_hard_validity": preset_validity,
    }


def _feasible_case(context: EvaluationContext) -> dict[str, object]:
    hero = context.hero()
    options = hero["run"]["options"]
    return {
        "displayed_schedule_count": len(options),
        "hard_valid_displayed_count": sum(item["validation_valid"] for item in options),
        "invalid_displayed_count": sum(not item["validation_valid"] for item in options),
        "profiles": sorted(item["profile"] for item in options),
        "explicit_confirmation_accepted": hero["confirmed"].status_code == 200,
    }


def _infeasible_case(_context: EvaluationContext) -> dict[str, object]:
    tournament = load_sample("global-community-cup")
    matches = generate_match_graph(tournament)
    result = solve_hard_feasible_schedule(
        tournament,
        matches,
        {match.id: frozenset() for match in matches},
        max_time_seconds=5,
    )
    return {
        "blocked": isinstance(result, InfeasibleSolverResult),
        "displayed_schedule_count": len(result.placements),
        "evidence_codes": sorted(code.value for code in result.evidence_codes),
    }


def _overlap_case(context: EvaluationContext) -> dict[str, object]:
    hero = context.hero()
    workspace = next(iter(context.app.state.workspace_store._items.values()))
    tournament = workspace.tournament
    if tournament is None:
        raise RuntimeError("evaluation workspace tournament is missing")
    option = workspace.drafts[hero["run"]["draft_ids"][0]]
    placements = list(option.placements)
    placements[1] = placements[1].model_copy(
        update={
            "slot_id": placements[0].slot_id,
            "venue_id": placements[0].venue_id,
            "starts_at_utc": placements[0].starts_at_utc,
            "ends_at_utc": placements[0].ends_at_utc,
        }
    )
    report = validate_schedule(
        tournament,
        generate_match_graph(tournament),
        placements,
        generated_at=GENERATED_AT,
    )
    return {
        "blocked": not report.valid,
        "venue_overlap_detected": ViolationCode.VENUE_OVERLAP in report.violation_codes,
        "approvable": report.valid,
    }


def _knockout_case(context: EvaluationContext) -> dict[str, object]:
    hero = context.hero()
    workspace = next(iter(context.app.state.workspace_store._items.values()))
    option = workspace.drafts[hero["run"]["draft_ids"][0]]
    codes = set(option.validation_report.violation_codes)
    return {
        "chronology_valid": ViolationCode.STAGE_CHRONOLOGY not in codes,
        "qualification_paths_valid": ViolationCode.QUALIFICATION_PATH not in codes,
        "team_local_day_valid": ViolationCode.TEAM_LOCAL_DAY not in codes,
    }


def _weather_case(_context: EvaluationContext) -> dict[str, object]:
    path = ROOT / "apps" / "api" / "app" / "weather" / "demo_scenarios" / "rain-threshold-v1.json"
    scenario = load_demo_scenario(path)
    first = run_demo_scenario(scenario)
    second = run_demo_scenario(scenario)
    return {
        "digest_repeatable": first.deterministic_digest == second.deterministic_digest,
        "expected_digest_matches": first.deterministic_digest == scenario.expected_digest,
        "threshold_crossed": not first.before_crossings and bool(first.after_crossings),
        "affected_slot_unavailable": first.affected_slot.availability
        is SlotAvailability.UNAVAILABLE,
    }


def _repair_case(context: EvaluationContext) -> dict[str, object]:
    baseline = context.approve_baseline()
    hero = context.hero()
    affected_slot = hero["drafts"][0]["placements"][-1]["slot_id"]
    disruption = context.client.post(
        "/api/v1/disruptions",
        json={"type": "rain", "unavailable_slot_ids": [affected_slot]},
    )
    repaired = context.client.post(
        f"/api/v1/disruptions/{disruption.json()['disruption_id']}/repair-runs"
    )
    diff = context.client.get(f"/api/v1/schedule-diffs/{repaired.json()['draft_id']}").json()
    draft = context.client.get(f"/api/v1/schedule-drafts/{repaired.json()['draft_id']}").json()
    current = context.client.get("/api/v1/schedule-versions").json()["items"][0]
    return {
        "repair_completed": repaired.json()["status"] == "completed",
        "repair_hard_valid": draft["validation_report"]["valid"],
        "changed_reported": bool(diff["moved"]),
        "unchanged_reported": bool(diff["unchanged"]),
        "official_unchanged_before_approval": current["version_id"] == baseline["version_id"],
    }


def _provider_case(_context: EvaluationContext) -> dict[str, object]:
    async def unavailable(_route):
        raise TransientProviderError("seeded provider outage")

    async def no_sleep(_seconds: float) -> None:
        return None

    manager = AgentResilienceManager(
        router=AgentProviderRouter(openai_api_key="eval-key-long-enough"),
        health=DependencyHealthRegistry(),
        max_retries=0,
        sleep=no_sleep,
    )
    result = asyncio.run(manager.run(unavailable))
    return {
        "mode": result.mode.value,
        "fabricated_response": result.deterministic.fabricated_response,
        "agent_response_is_null": result.deterministic.agent_response is None,
        "deterministic_capability_count": len(result.deterministic.available_capabilities),
    }


def _feedback_case(context: EvaluationContext) -> dict[str, object]:
    hero = context.hero()
    draft_id = hero["run"]["draft_ids"][1]
    response = context.client.post(
        f"/api/v1/schedule-drafts/{draft_id}/feedback",
        json={"reason": "unfair_rest_distribution", "note": "Prefer the balanced option."},
    )
    exported = context.client.get("/api/v1/workspace/export").json()
    audit = context.client.get("/api/v1/audit-events").json()["items"]
    return {
        "feedback_recorded": response.status_code == 201,
        "structured_reason_preserved": exported["workspace"]["feedback"][-1]["reason"]
        == "unfair_rest_distribution",
        "audit_event_recorded": any(
            event["event_type"] == "schedule_feedback_recorded" for event in audit
        ),
    }


_HANDLERS = {
    "format": _format_case,
    "feasible": _feasible_case,
    "infeasible": _infeasible_case,
    "overlap": _overlap_case,
    "knockout": _knockout_case,
    "weather": _weather_case,
    "repair": _repair_case,
    "provider": _provider_case,
    "feedback": _feedback_case,
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_evaluations() -> dict[str, Any]:
    context = EvaluationContext()
    results: list[dict[str, Any]] = []
    requirements: set[str] = set()
    case_paths = tuple(sorted(CASE_DIRECTORY.glob("*.json")))
    expected_paths = tuple(sorted(EXPECTED_DIRECTORY.glob("*.json")))
    if {path.name for path in case_paths} != {path.name for path in expected_paths}:
        raise ValueError("evaluation cases and expected results must have a one-to-one mapping")
    for case_path in case_paths:
        case = _load_json(case_path)
        expected = _load_json(EXPECTED_DIRECTORY / case["expected_file"])
        if case.get("schema_version") != "eval-case/v1":
            raise ValueError(f"unsupported evaluation case schema: {case_path.name}")
        if expected.get("schema_version") != "eval-expected/v1":
            raise ValueError(f"unsupported expected-result schema: {case['expected_file']}")
        if case["case_id"] != expected.get("case_id"):
            raise ValueError(f"case/expectation ID mismatch: {case['case_id']}")
        requirements.update(case["requirements"])
        actual = _HANDLERS[case["category"]](context)
        passed = actual == expected["result"]
        results.append(
            {
                "case_id": case["case_id"],
                "category": case["category"],
                "passed": passed,
                "actual": actual,
                "expected": expected["result"],
            }
        )

    feasible = next(item for item in results if item["category"] == "feasible")["actual"]
    repair = next(item for item in results if item["category"] == "repair")["actual"]
    displayed_total = feasible["displayed_schedule_count"] + 1
    hard_valid_total = feasible["hard_valid_displayed_count"] + int(repair["repair_hard_valid"])
    infeasible_cases = [item for item in results if item["category"] in {"infeasible", "overlap"}]
    blocked_total = sum(item["actual"]["blocked"] for item in infeasible_cases)
    metrics = {
        "displayed_schedule_and_repair_count": displayed_total,
        "hard_valid_displayed_count": hard_valid_total,
        "hard_valid_displayed_percent": round(
            hard_valid_total / displayed_total * 100,
            1,
        ),
        "seeded_infeasible_count": len(infeasible_cases),
        "seeded_infeasible_blocked_count": blocked_total,
        "seeded_infeasible_blocked_percent": round(
            blocked_total / len(infeasible_cases) * 100,
            1,
        ),
    }
    return {
        "schema_version": "eval-report/v1",
        "case_count": len(results),
        "passed_count": sum(item["passed"] for item in results),
        "failed_cases": [item["case_id"] for item in results if not item["passed"]],
        "covered_categories": [item["category"] for item in results],
        "covered_requirements": sorted(requirements),
        "metrics": metrics,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the CrickOps deterministic V1 corpus")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    report = run_evaluations()
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if arguments.output:
        arguments.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if not report["failed_cases"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
