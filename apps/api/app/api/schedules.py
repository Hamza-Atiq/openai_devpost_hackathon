from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from time import perf_counter
from typing import Annotated, Any, Literal, Protocol
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from pydantic import Field, model_validator

from app.api.audit import append_audit_event
from app.api.operations import OperationsState
from app.api.problems import APIProblem
from app.api.readiness import minimum_rest_minutes, run_workspace_precheck
from app.api.routes import require_workspace
from app.api.workspace import GuestWorkspace
from app.domain.common import DomainModel
from app.domain.matches import MatchDefinition, MatchStage
from app.domain.schedules import ScheduleMetrics, ScheduleProfile
from app.domain.venues import SlotAvailability
from app.fairness.evaluator import evaluate_schedule_metrics
from app.limits.public_demo import PublicDemoProtection, UsageAction
from app.observability.recorder import observe
from app.optimization.config import load_optimization_config
from app.scheduling.comparison import compare_profile_options
from app.scheduling.diff import build_schedule_diff
from app.scheduling.pairings import generate_match_graph
from app.scheduling.precheck import RemedyCode, run_pre_solver_checks
from app.scheduling.profiles import ComponentPenalties, generate_profile_options
from app.scheduling.repair import RepairStatus, repair_schedule


class WorkflowOrchestratorProtocol(Protocol):
    async def after_generation(
        self, *, workspace: GuestWorkspace, run: Mapping[str, object]
    ) -> tuple[Mapping[str, object], ...]: ...


def _specialist_status(evidence: tuple[Mapping[str, object], ...]) -> str:
    available = sum(bool(item.get("available")) for item in evidence)
    if available == len(evidence) and evidence:
        return "complete"
    if available:
        return "partial"
    return "unavailable"

    async def after_repair(
        self,
        *,
        workspace: GuestWorkspace,
        draft_id: str,
        disruption: Mapping[str, object],
        diff: Mapping[str, object],
    ) -> tuple[Mapping[str, object], ...]: ...


class CustomPrioritiesInput(DomainModel):
    weather_coverage: int = Field(ge=0, le=100)
    rest: int = Field(ge=0, le=100)
    venue_balance: int = Field(ge=0, le=100)
    slot_balance: int = Field(ge=0, le=100)
    organizer_preferences: int = Field(ge=0, le=100)
    audience_timing: int = Field(ge=0, le=100)

    @model_validator(mode="after")
    def reject_all_zero(self) -> CustomPrioritiesInput:
        values = self.model_dump(exclude={"schema_version"}).values()
        if sum(values) == 0:
            raise ValueError("custom priorities cannot all be zero")
        return self


class ScheduleRunInput(DomainModel):
    profiles: tuple[str, ...] = Field(min_length=1, max_length=4)
    expected_revision: int | None = Field(default=None, ge=0)
    custom_priorities: CustomPrioritiesInput | None = None


class ApprovalInput(DomainModel):
    confirmation: bool


class ScheduleFeedbackInput(DomainModel):
    reason: (
        Literal[
            "weather_preference",
            "unfair_rest_distribution",
            "venue_preference",
            "unsuitable_time_slot",
            "rivalry_requirement",
            "travel_concern",
            "other",
        ]
        | None
    ) = None
    note: str | None = Field(default=None, max_length=500)


class DisruptionInput(DomainModel):
    type: str = Field(pattern=r"^(rain|venue_unavailability)$")
    unavailable_slot_ids: tuple[str, ...] = Field(min_length=1)


def _uuid7() -> UUID:
    raw = bytearray(uuid4().bytes)
    raw[6] = (raw[6] & 0x0F) | 0x70
    raw[8] = (raw[8] & 0x3F) | 0x80
    return UUID(bytes=bytes(raw))


def _weather_risk_by_slot(workspace: GuestWorkspace) -> dict[UUID, Decimal | None]:
    raw = workspace.weather.get("slot_risks", {})
    if not isinstance(raw, dict):
        return {}
    result: dict[UUID, Decimal | None] = {}
    for slot_id, risk in raw.items():
        try:
            identifier = UUID(str(slot_id))
        except ValueError:
            continue
        result[identifier] = None if risk is None else Decimal(str(risk))
    return result


def _metric_evaluator(workspace: GuestWorkspace, matches):
    if workspace.tournament is None:
        raise ValueError("tournament is required for metric evaluation")
    config = load_optimization_config()
    risks = _weather_risk_by_slot(workspace)

    def evaluate(profile: ScheduleProfile, placements) -> ScheduleMetrics:
        profile_name = "balanced" if profile is ScheduleProfile.CUSTOM else profile.value
        return evaluate_schedule_metrics(
            workspace.tournament,
            matches,
            placements,
            slot_weather_risk=risks,
            missing_coverage_penalty=Decimal(
                config.profiles[profile_name].missing_coverage_penalty
            ),
        )

    return evaluate


def _eligibility(workspace: GuestWorkspace):
    tournament = workspace.tournament
    if tournament is None:
        return (), {}
    matches = generate_match_graph(tournament)
    available_slot_ids = frozenset(
        slot.id for slot in tournament.slots if slot.availability is SlotAvailability.AVAILABLE
    )
    if len(available_slot_ids) < 15:
        return matches, {match.id: frozenset() for match in matches}
    return matches, {match.id: available_slot_ids for match in matches}


def _slot_category(local_hour: int) -> str:
    if 6 <= local_hour <= 11:
        return "morning"
    if 12 <= local_hour <= 16:
        return "day"
    if 17 <= local_hour <= 22:
        return "evening"
    return "off_hours"


def _component_penalties(
    workspace: GuestWorkspace,
    matches: tuple[MatchDefinition, ...],
    eligibility: dict[UUID, frozenset[UUID]],
) -> ComponentPenalties:
    """Translate confirmed workspace state into bounded placement costs.

    Exact comparable metrics are still calculated after solving. These costs
    provide CP-SAT with real choices instead of preselecting one slot per match.
    """
    tournament = workspace.tournament
    if tournament is None:
        raise ValueError("tournament is required for objective construction")
    config = load_optimization_config()
    risks = _weather_risk_by_slot(workspace)
    missing_risk = config.profiles["balanced"].missing_coverage_penalty
    ordered_slots = tuple(
        sorted(tournament.slots, key=lambda slot: (slot.starts_at_utc, str(slot.id)))
    )
    slot_by_id = {slot.id: slot for slot in ordered_slots}
    venue_by_id = {venue.id: venue for venue in tournament.venues}
    venue_index = {venue.id: index for index, venue in enumerate(tournament.venues)}
    distinct_starts = tuple(sorted({slot.starts_at_utc for slot in ordered_slots}))
    start_rank = {starts_at: index for index, starts_at in enumerate(distinct_starts)}
    last_rank = max(len(distinct_starts) - 1, 1)
    categories = tuple(
        dict.fromkeys(
            _slot_category(
                slot.starts_at_utc.astimezone(
                    ZoneInfo(venue_by_id[slot.venue_id].iana_time_zone)
                ).hour
            )
            for slot in ordered_slots
        )
    ) or ("off_hours",)
    penalties: dict[str, dict[tuple[UUID, UUID], int]] = {
        name: {}
        for name in (
            "weather_coverage",
            "rest",
            "venue_balance",
            "slot_balance",
            "organizer_preferences",
            "audience_timing",
        )
    }
    for match in matches:
        target_venue = (match.sequence - 1) % len(tournament.venues)
        target_category = categories[(match.sequence - 1) % len(categories)]
        for slot_id in eligibility[match.id]:
            slot = slot_by_id[slot_id]
            venue = venue_by_id[slot.venue_id]
            local = slot.starts_at_utc.astimezone(ZoneInfo(venue.iana_time_zone))
            category = _slot_category(local.hour)
            key = (match.id, slot_id)
            risk = risks.get(slot_id)
            weather_penalty = Decimal(missing_risk) if risk is None else risk
            penalties["weather_coverage"][key] = int(
                min(Decimal(100), max(Decimal(0), weather_penalty))
            )
            rank = start_rank[slot.starts_at_utc]
            rest_rank = rank if match.stage is MatchStage.GROUP else last_rank - rank
            penalties["rest"][key] = round(rest_rank * 100 / last_rank)
            penalties["venue_balance"][key] = (
                0 if venue_index[slot.venue_id] == target_venue else 100
            )
            penalties["slot_balance"][key] = 0 if category == target_category else 100
            penalties["organizer_preferences"][key] = 0
            if match.stage is MatchStage.GROUP:
                penalties["audience_timing"][key] = 0
            elif category == "evening":
                penalties["audience_timing"][key] = 0
            elif local.weekday() >= 5:
                penalties["audience_timing"][key] = 30
            elif category == "off_hours":
                penalties["audience_timing"][key] = 100
            else:
                penalties["audience_timing"][key] = 60
    return penalties


def _schedule_version_view(
    workspace: GuestWorkspace, version: Mapping[str, object]
) -> dict[str, object]:
    tournament = workspace.tournament
    option = workspace.drafts.get(str(version["approved_draft_id"]))
    if tournament is None or option is None or not option.validation_report.valid:
        raise APIProblem(
            status=409,
            code="official_schedule_unavailable",
            title="Official schedule is unavailable",
            detail="The approved schedule could not be verified from workspace state.",
        )
    matches = generate_match_graph(tournament)
    placement_by_match = {placement.match_id: placement for placement in option.placements}
    team_name = {str(team.id): team.display_name for team in tournament.teams}
    venue_by_id = {venue.id: venue for venue in tournament.venues}

    def participant_label(value: str) -> str:
        return {
            "A1": "Group A Winner",
            "A2": "Group A Runner-up",
            "B1": "Group B Winner",
            "B2": "Group B Runner-up",
            "SF1 Winner": "Semifinal 1 Winner",
            "SF2 Winner": "Semifinal 2 Winner",
        }.get(value, team_name.get(value, value))

    fixtures: list[dict[str, object]] = []
    for match in matches:
        placement = placement_by_match[match.id]
        venue = venue_by_id[placement.venue_id]
        time_zone = ZoneInfo(venue.iana_time_zone)
        code = (
            f"G{match.sequence:02d}"
            if match.stage is MatchStage.GROUP
            else "SF1"
            if match.sequence == 13
            else "SF2"
            if match.sequence == 14
            else "F1"
        )
        fixtures.append(
            {
                "id": str(match.id),
                "slot_id": str(placement.slot_id),
                "code": code,
                "stage": match.stage,
                "home": participant_label(match.participant_a),
                "away": participant_label(match.participant_b),
                "venue": venue.display_name,
                "starts_at": placement.starts_at_utc.astimezone(time_zone).isoformat(),
                "ends_at": placement.ends_at_utc.astimezone(time_zone).isoformat(),
                "timezone": venue.iana_time_zone,
                "validation": "valid",
            }
        )
    return {
        **version,
        "current_official": bool(
            workspace.official_versions
            and str(workspace.official_versions[-1]["version_id"])
            == str(version["version_id"])
        ),
        "validation_valid": True,
        "fixtures": fixtures,
    }


def build_schedule_router(
    operations: OperationsState | None = None,
    demo_protection: PublicDemoProtection | None = None,
    workflow_orchestrator: WorkflowOrchestratorProtocol | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.post("/schedule-runs", status_code=status.HTTP_202_ACCEPTED)
    async def start_schedule_run(
        body: ScheduleRunInput,
        request: Request,
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    ) -> dict[str, object]:
        replay = workspace.idempotency.get(f"generation:{idempotency_key}")
        if replay is not None:
            return replay
        if workspace.tournament is None:
            raise APIProblem(
                status=409,
                code="tournament_not_ready",
                title="Tournament is not ready",
                detail="Complete tournament setup before generation.",
            )
        if (
            body.expected_revision is not None
            and body.expected_revision != workspace.tournament.revision
        ):
            raise APIProblem(
                status=409,
                code="stale_tournament_revision",
                title="Tournament revision is stale",
                detail="Refresh the workspace before starting another schedule run.",
                retryable=True,
            )
        from app.domain.tournament import TournamentStatus

        confirmed_revision = (
            workspace.constraint_confirmation.get("confirmed_revision")
            if workspace.constraint_confirmation
            else None
        )
        if (
            workspace.tournament.status is not TournamentStatus.READY_TO_SCHEDULE
            or confirmed_revision != workspace.tournament.revision
        ):
            raise APIProblem(
                status=409,
                code="constraints_not_confirmed",
                title="Hard constraints are not confirmed",
                detail="Review and confirm the latest saved setup before generation.",
            )
        precheck = run_workspace_precheck(workspace)
        if not precheck.can_solve:
            evidence = " ".join(item.message for item in precheck.evidence)
            raise APIProblem(
                status=422,
                code="schedule_precheck_failed",
                title="Tournament setup is infeasible",
                detail=(
                    "Available capacity or chronology cannot satisfy the tournament. "
                    f"{evidence}"
                ),
            )
        requested = {value.replace("_", "-") for value in body.profiles}
        required = {"balanced", "weather-first", "fairness-first"}
        if not required.issubset(requested):
            raise APIProblem(
                status=422,
                code="profiles_required",
                title="Three profiles required",
                detail="Balanced, Weather-first, and Fairness-first must be requested together.",
            )
        custom_requested = "custom" in requested
        if custom_requested and body.custom_priorities is None:
            raise APIProblem(
                status=422,
                code="custom_priorities_required",
                title="Custom priorities required",
                detail="Set Custom priority weights before generating a custom schedule.",
            )
        if body.custom_priorities is not None and not custom_requested:
            raise APIProblem(
                status=422,
                code="custom_profile_required",
                title="Custom profile required",
                detail="Request the Custom profile when custom priorities are supplied.",
            )
        if demo_protection is not None:
            decision = demo_protection.consume(
                UsageAction.GENERATION,
                workspace_id=workspace.workspace_id,
                ip_address=request.client.host if request.client else None,
            )
            if not decision.allowed:
                reset = decision.reset_at.isoformat() if decision.reset_at else "capacity clears"
                raise APIProblem(
                    status=429,
                    code="public_demo_limit_exceeded",
                    title="Public demo limit reached",
                    detail=f"Schedule generation is temporarily limited; retry after {reset}.",
                    retryable=True,
                )
            job = demo_protection.acquire_job(workspace.workspace_id)
            if not job.allowed:
                raise APIProblem(
                    status=429,
                    code="public_demo_capacity_reached",
                    title="Scheduling capacity reached",
                    detail="Another scheduling job is active; retry when it completes.",
                    retryable=True,
                )
        matches, eligibility = _eligibility(workspace)
        observe(
            component="weather",
            event="risk_snapshot_read",
            outcome=str(workspace.weather.get("quality", "unknown")),
            metadata={
                "mode": workspace.weather.get("mode", "deterministic"),
                "scenario_id": workspace.weather.get("scenario_id"),
            },
        )
        solver_started = perf_counter()
        try:
            batch = generate_profile_options(
                workspace.tournament,
                matches,
                eligibility,
                generated_at=datetime.now(UTC),
                metric_evaluator=_metric_evaluator(workspace, matches),
                component_penalties=_component_penalties(workspace, matches, eligibility),
                minimum_rest_minutes=minimum_rest_minutes(workspace),
                custom_priorities=(
                    body.custom_priorities.model_dump(exclude={"schema_version"})
                    if body.custom_priorities is not None
                    else None
                ),
            )
        finally:
            if demo_protection is not None:
                demo_protection.release_job(workspace.workspace_id)
        solver_duration_ms = round((perf_counter() - solver_started) * 1000, 3)
        observe(
            component="solver",
            event="profile_generation",
            outcome="infeasible" if batch.failures else "success",
            metadata={
                "profile_count": len(batch.options),
                "failure_count": len(batch.failures),
                "duration_ms": solver_duration_ms,
            },
        )
        observe(
            component="validator",
            event="profile_batch",
            outcome=(
                "valid"
                if batch.options and all(option.validation_report.valid for option in batch.options)
                else "invalid"
            ),
            metadata={
                "validated_count": len(batch.options),
                "invalid_count": sum(
                    not option.validation_report.valid for option in batch.options
                ),
            },
        )
        if batch.failures:
            raise APIProblem(
                status=422,
                code="schedule_infeasible",
                title="No valid schedule exists",
                detail="Confirmed constraints and available slots are infeasible.",
            )
        run_id = str(uuid4())
        options: list[dict[str, object]] = []
        for option in batch.options:
            draft_id = str(_uuid7())
            workspace.drafts[draft_id] = option
            workspace.draft_revisions[draft_id] = workspace.tournament.revision
            options.append(
                {
                    "draft_id": draft_id,
                    "profile": option.profile,
                    "validation_valid": option.validation_report.valid,
                    "metrics": option.metrics.model_dump(mode="json"),
                }
            )
        run = {
            "run_id": run_id,
            "status": "completed",
            "draft_ids": [item["draft_id"] for item in options],
            "options": options,
            "specialist_evidence": [],
            "agent_status": "not_configured",
        }
        workspace.schedule_runs[run_id] = run
        if workflow_orchestrator is not None:
            try:
                specialist_evidence = await workflow_orchestrator.after_generation(
                    workspace=workspace, run=run
                )
                run["specialist_evidence"] = list(specialist_evidence)
                run["agent_status"] = _specialist_status(specialist_evidence)
            except Exception as exc:
                run["agent_status"] = "unavailable"
                observe(
                    component="agent",
                    event="generation_specialists",
                    outcome="unavailable",
                    metadata={"error_type": type(exc).__name__},
                )
        observe(
            component="database",
            event="schedule_run_saved",
            outcome="success",
            metadata={"run_id": run_id, "draft_count": len(options)},
        )
        if operations is not None:
            append_audit_event(
                operations,
                workspace.workspace_id,
                event_type="schedule_options_generated",
                summary=f"Generated and validated {len(options)} schedule options.",
                structured_payload={
                    "run_id": run_id,
                    "profiles": [str(item["profile"]) for item in options],
                    "agent_status": run["agent_status"],
                    "specialist_evidence": run["specialist_evidence"],
                },
                actor_type="system",
            )
        accepted = {
            "run_id": run_id,
            "status": "accepted",
            "agent_status": run["agent_status"],
        }
        workspace.idempotency[f"generation:{idempotency_key}"] = accepted
        return accepted

    @router.get("/schedule-runs/{run_id}")
    def read_schedule_run(
        run_id: str,
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ):
        run = workspace.schedule_runs.get(run_id)
        if run is None:
            raise APIProblem(
                status=404,
                code="schedule_run_not_found",
                title="Schedule run not found",
                detail="The run does not belong to this workspace.",
            )
        return run

    @router.delete("/schedule-runs/{run_id}")
    def cancel_schedule_run(
        run_id: str,
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ):
        run = workspace.schedule_runs.get(run_id)
        if run is None:
            raise APIProblem(
                status=404,
                code="schedule_run_not_found",
                title="Schedule run not found",
                detail="The run does not belong to this workspace.",
            )
        run["status"] = "cancelled"
        return run

    @router.get("/schedule-runs/{run_id}/events")
    def schedule_run_events(
        run_id: str,
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ) -> Response:
        if run_id not in workspace.schedule_runs:
            raise APIProblem(
                status=404,
                code="schedule_run_not_found",
                title="Schedule run not found",
                detail="The run does not belong to this workspace.",
            )
        return Response("event: completed\ndata: {}\n\n", media_type="text/event-stream")

    @router.get("/schedule-drafts/{draft_id}")
    def read_draft(
        draft_id: str,
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ):
        option = workspace.drafts.get(draft_id)
        if option is None:
            raise APIProblem(
                status=404,
                code="schedule_draft_not_found",
                title="Schedule draft not found",
                detail="The draft does not belong to this workspace.",
            )
        return {"draft_id": draft_id, **option.model_dump(mode="json")}

    @router.get("/schedule-comparisons")
    def read_comparison(
        run_id: Annotated[str, Query()],
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ) -> dict[str, object]:
        run = workspace.schedule_runs.get(run_id)
        if run is None:
            raise APIProblem(
                status=404,
                code="schedule_run_not_found",
                title="Schedule run not found",
                detail="The run does not belong to this workspace.",
            )
        options = [workspace.drafts[str(draft_id)] for draft_id in run["draft_ids"]]
        comparison = compare_profile_options(options)
        return {
            "run_id": run_id,
            "metric_version": comparison.metric_version,
            "options": run["options"],
            "identical_solution_groups": comparison.identical_solution_groups,
        }

    @router.get("/weather/schedule")
    def read_schedule_weather(
        draft_id: Annotated[str, Query(min_length=1)],
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ) -> dict[str, object]:
        tournament = workspace.tournament
        draft = workspace.drafts.get(draft_id)
        if tournament is None or draft is None:
            raise APIProblem(
                status=404,
                code="schedule_draft_not_found",
                title="Schedule draft not found",
                detail="The draft does not belong to this workspace.",
            )
        matches = generate_match_graph(tournament)
        placement_by_match = {placement.match_id: placement for placement in draft.placements}
        venues = {venue.id: venue for venue in tournament.venues}
        team_names = {str(team.id): team.display_name for team in tournament.teams}
        slot_risks = workspace.weather.get("slot_risks", {})
        slot_details = workspace.weather.get("slot_details", {})
        if not isinstance(slot_risks, dict):
            slot_risks = {}
        if not isinstance(slot_details, dict):
            slot_details = {}

        def participant_label(value: str) -> str:
            return {
                "A1": "Group A Winner",
                "A2": "Group A Runner-up",
                "B1": "Group B Winner",
                "B2": "Group B Runner-up",
                "SF1 Winner": "Semifinal 1 Winner",
                "SF2 Winner": "Semifinal 2 Winner",
            }.get(value, team_names.get(value, value))

        fixtures = []
        for match in matches:
            placement = placement_by_match[match.id]
            venue = venues[placement.venue_id]
            zone = ZoneInfo(venue.iana_time_zone)
            slot_id = str(placement.slot_id)
            raw_detail = slot_details.get(slot_id, {})
            detail = raw_detail if isinstance(raw_detail, dict) else {}
            raw_risk = slot_risks.get(slot_id)
            code = (
                f"G{match.sequence:02d}"
                if match.stage is MatchStage.GROUP
                else "SF1"
                if match.sequence == 13
                else "SF2"
                if match.sequence == 14
                else "F1"
            )
            fixtures.append(
                {
                    "id": code,
                    "label": (
                        f"{participant_label(match.participant_a)} vs "
                        f"{participant_label(match.participant_b)}"
                    ),
                    "venue": venue.display_name,
                    "starts_at": placement.starts_at_utc.astimezone(zone).isoformat(),
                    "timezone": venue.iana_time_zone,
                    "risk": raw_risk,
                    "components": detail.get("components", {}),
                    "quality": detail.get(
                        "quality",
                        "complete" if raw_risk is not None else "forecast_not_yet_available",
                    ),
                }
            )
        covered = sum(item["risk"] is not None for item in fixtures)
        coverage = round(covered / len(fixtures) * 100, 1) if fixtures else 0.0
        return {
            "draft_id": draft_id,
            "mode": workspace.weather.get("mode", "live"),
            "provider": workspace.weather.get("provider"),
            "issued_at": workspace.weather.get("issued_at"),
            "fetched_at": workspace.weather.get("fetched_at"),
            "quality": workspace.weather.get("quality", "unavailable"),
            "coverage": coverage,
            "allocation_minutes": tournament.allocation_minutes,
            "attribution": workspace.weather.get("attribution"),
            "fixtures": fixtures,
        }

    @router.post("/schedule-drafts/{draft_id}/feedback", status_code=201)
    def record_feedback(
        draft_id: str,
        body: ScheduleFeedbackInput,
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ):
        if draft_id not in workspace.drafts:
            raise APIProblem(
                status=404,
                code="schedule_draft_not_found",
                title="Schedule draft not found",
                detail="The draft does not belong to this workspace.",
            )
        payload = body.model_dump(mode="json", exclude={"schema_version"})
        feedback = {"draft_id": draft_id, **payload, "recorded_at": datetime.now(UTC).isoformat()}
        workspace.feedback.append(feedback)
        if operations is not None:
            append_audit_event(
                operations,
                workspace.workspace_id,
                event_type="schedule_feedback_recorded",
                summary="Organizer recorded structured schedule feedback.",
                structured_payload={"draft_id": draft_id, "reason": body.reason},
            )
        return feedback

    @router.post("/schedule-drafts/{draft_id}/approve", status_code=201)
    def approve_draft(
        draft_id: str,
        body: ApprovalInput,
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    ):
        replay = workspace.idempotency.get(f"approval:{idempotency_key}")
        if replay is not None:
            return replay
        option = workspace.drafts.get(draft_id)
        if (
            option is None
            or draft_id in workspace.rejected_drafts
            or not option.validation_report.valid
            or not body.confirmation
        ):
            raise APIProblem(
                status=409,
                code="draft_not_approvable",
                title="Draft cannot be approved",
                detail="Only an owned, valid draft with explicit confirmation may be approved.",
            )
        draft_revision = workspace.draft_revisions.get(draft_id)
        tournament_revision = workspace.tournament.revision if workspace.tournament else None
        if draft_revision != tournament_revision:
            raise APIProblem(
                status=409,
                code="stale_schedule_draft",
                title="Schedule draft is stale",
                detail="Regenerate this option from the latest confirmed tournament revision.",
            )
        repair_diff = workspace.schedule_diffs.get(draft_id)
        if repair_diff is not None:
            latest_version_id = (
                str(workspace.official_versions[-1]["version_id"])
                if workspace.official_versions
                else None
            )
            if str(repair_diff["baseline_version_id"]) != latest_version_id:
                raise APIProblem(
                    status=409,
                    code="stale_official_baseline",
                    title="Official schedule changed",
                    detail="Generate a new repair from the latest official schedule version.",
                )
        version = {
            "version_id": str(_uuid7()),
            "version_number": len(workspace.official_versions) + 1,
            "approved_draft_id": draft_id,
            "approved_at": datetime.now(UTC).isoformat(),
        }
        workspace.official_versions.append(version)
        observe(
            component="approval",
            event="schedule_approved",
            outcome="success",
            metadata={"draft_id": draft_id, "version_number": version["version_number"]},
        )
        observe(
            component="database",
            event="schedule_version_saved",
            outcome="success",
            metadata={"version_id": version["version_id"]},
        )
        if repair_diff is not None:
            observe(
                component="hero",
                event="repaired_schedule_approved",
                outcome="success",
                metadata={"version_number": version["version_number"]},
            )
        if operations is not None:
            append_audit_event(
                operations,
                workspace.workspace_id,
                event_type="schedule_approved",
                summary=f"Schedule Version {version['version_number']} approved.",
                structured_payload={
                    "version_id": version["version_id"],
                    "version_number": version["version_number"],
                    "draft_id": draft_id,
                },
            )
        workspace.idempotency[f"approval:{idempotency_key}"] = version
        return version

    @router.post("/schedule-drafts/{draft_id}/reject", status_code=204)
    def reject_draft(
        draft_id: str,
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ) -> Response:
        if draft_id not in workspace.drafts:
            raise APIProblem(
                status=404,
                code="schedule_draft_not_found",
                title="Schedule draft not found",
                detail="The draft does not belong to this workspace.",
            )
        workspace.rejected_drafts.add(draft_id)
        if operations is not None:
            append_audit_event(
                operations,
                workspace.workspace_id,
                event_type="schedule_rejected",
                summary="Organizer rejected a schedule draft.",
                structured_payload={"draft_id": draft_id},
            )
        return Response(status_code=204)

    @router.post("/schedule-versions/{version_id}/restore", status_code=201)
    def restore_schedule_version(
        version_id: str,
        body: ApprovalInput,
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    ):
        replay = workspace.idempotency.get(f"restore:{idempotency_key}")
        if replay is not None:
            return replay
        source = next(
            (
                version
                for version in workspace.official_versions
                if str(version["version_id"]) == version_id
            ),
            None,
        )
        if source is None:
            raise APIProblem(
                status=404,
                code="schedule_version_not_found",
                title="Schedule version not found",
                detail="The requested official version does not belong to this workspace.",
            )
        if not body.confirmation:
            raise APIProblem(
                status=422,
                code="confirmation_required",
                title="Confirmation required",
                detail="Explicitly confirm restoration of the earlier official schedule.",
            )
        restored = {
            "version_id": str(_uuid7()),
            "version_number": len(workspace.official_versions) + 1,
            "approved_draft_id": source["approved_draft_id"],
            "approved_at": datetime.now(UTC).isoformat(),
            "restored_from_version_id": version_id,
        }
        workspace.official_versions.append(restored)
        if operations is not None:
            append_audit_event(
                operations,
                workspace.workspace_id,
                event_type="schedule_restored",
                summary=(
                    f"Version {source['version_number']} restored as new official "
                    f"Version {restored['version_number']}."
                ),
                structured_payload={
                    "restored_from_version_id": version_id,
                    "version_id": restored["version_id"],
                },
            )
        workspace.idempotency[f"restore:{idempotency_key}"] = restored
        return restored

    @router.get("/schedule-versions")
    def list_schedule_versions(
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ):
        return {"items": tuple(reversed(workspace.official_versions))}

    @router.get("/schedule-versions/{version_id}")
    def read_schedule_version(
        version_id: str,
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ):
        version = next(
            (
                item
                for item in workspace.official_versions
                if str(item["version_id"]) == version_id
            ),
            None,
        )
        if version is None:
            raise APIProblem(
                status=404,
                code="schedule_version_not_found",
                title="Schedule version not found",
                detail="The requested official version does not belong to this workspace.",
            )
        return _schedule_version_view(workspace, version)

    @router.get("/official-schedule")
    def read_official_schedule(
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ):
        if not workspace.official_versions:
            return {"official": None}
        version = workspace.official_versions[-1]
        return {"official": _schedule_version_view(workspace, version)}

    @router.post("/schedule-edits", status_code=201)
    def create_edit(
        body: dict[str, Any],
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ):
        edit_id = str(uuid4())
        workspace.edits[edit_id] = {"edit_id": edit_id, "status": "proposed", **body}
        return workspace.edits[edit_id]

    @router.post("/schedule-edits/{edit_id}/confirm")
    def confirm_edit(
        edit_id: str,
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ):
        edit = workspace.edits.get(edit_id)
        if edit is None:
            raise APIProblem(
                status=404,
                code="schedule_edit_not_found",
                title="Schedule edit not found",
                detail="The edit does not belong to this workspace.",
            )
        edit["status"] = "confirmed"
        return edit

    @router.delete("/schedule-edits/{edit_id}", status_code=204)
    def cancel_edit(
        edit_id: str,
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ) -> Response:
        workspace.edits.pop(edit_id, None)
        return Response(status_code=204)

    @router.post("/disruptions", status_code=201)
    def create_disruption(
        body: DisruptionInput,
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ):
        if not workspace.official_versions:
            raise APIProblem(
                status=409,
                code="official_schedule_required",
                title="Official schedule required",
                detail="Recovery must start from the latest approved schedule.",
            )
        tournament = workspace.tournament
        if tournament is None:
            raise APIProblem(
                status=409,
                code="tournament_not_ready",
                title="Tournament is not ready",
                detail="The active tournament configuration is unavailable.",
            )
        tournament_slot_ids = {str(slot.id) for slot in tournament.slots}
        supplied_slot_ids = set(body.unavailable_slot_ids)
        if not supplied_slot_ids.issubset(tournament_slot_ids):
            raise APIProblem(
                status=422,
                code="invalid_disruption_slots",
                title="Invalid disruption slots",
                detail=(
                    "One or more selected venue-time slots do not belong to this "
                    "workspace tournament."
                ),
            )
        latest = workspace.official_versions[-1]
        baseline = workspace.drafts.get(str(latest["approved_draft_id"]))
        occupied_slot_ids = (
            {str(placement.slot_id) for placement in baseline.placements}
            if baseline is not None
            else set()
        )
        if supplied_slot_ids.isdisjoint(occupied_slot_ids):
            raise APIProblem(
                status=422,
                code="disruption_does_not_affect_official_schedule",
                title="No official fixture is affected",
                detail=(
                    "Select at least one venue-time slot used by the latest official "
                    "schedule."
                ),
            )
        disruption_id = str(uuid4())
        disruption = {
            "disruption_id": disruption_id,
            "status": "active",
            **body.model_dump(mode="json"),
        }
        workspace.disruptions[disruption_id] = disruption
        if operations is not None:
            append_audit_event(
                operations,
                workspace.workspace_id,
                event_type="disruption_declared",
                summary=f"Organizer declared {body.type.replace('_', ' ')}.",
                structured_payload={
                    "disruption_id": disruption_id,
                    "type": body.type,
                    "unavailable_slot_count": len(body.unavailable_slot_ids),
                },
            )
        return disruption

    @router.post("/disruptions/{disruption_id}/repair-runs", status_code=202)
    async def start_repair(
        disruption_id: str,
        request: Request,
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ):
        disruption = workspace.disruptions.get(disruption_id)
        if disruption is None:
            raise APIProblem(
                status=404,
                code="disruption_not_found",
                title="Disruption not found",
                detail="The disruption does not belong to this workspace.",
            )
        official = workspace.official_versions[-1]
        baseline_id = str(official["approved_draft_id"])
        baseline = workspace.drafts[baseline_id]
        unavailable = set(disruption["unavailable_slot_ids"])
        tournament = workspace.tournament
        if tournament is None:
            raise APIProblem(
                status=409,
                code="tournament_not_ready",
                title="Tournament is not ready",
                detail="The active tournament configuration is unavailable.",
            )
        if demo_protection is not None:
            decision = demo_protection.consume(
                UsageAction.REPAIR,
                workspace_id=workspace.workspace_id,
                ip_address=request.client.host if request.client else None,
            )
            if not decision.allowed:
                reset = decision.reset_at.isoformat() if decision.reset_at else "capacity clears"
                raise APIProblem(
                    status=429,
                    code="public_demo_limit_exceeded",
                    title="Public demo limit reached",
                    detail=f"Schedule repair is temporarily limited; retry after {reset}.",
                    retryable=True,
                )
            job = demo_protection.acquire_job(workspace.workspace_id)
            if not job.allowed:
                raise APIProblem(
                    status=429,
                    code="public_demo_capacity_reached",
                    title="Scheduling capacity reached",
                    detail="Another scheduling job is active; retry when it completes.",
                    retryable=True,
                )
        repaired_tournament = tournament.model_copy(
            update={
                "slots": tuple(
                    slot.model_copy(update={"availability": SlotAvailability.UNAVAILABLE})
                    if str(slot.id) in unavailable
                    else slot
                    for slot in tournament.slots
                )
            }
        )
        matches = generate_match_graph(repaired_tournament)
        eligible = {
            match.id: frozenset(
                slot.id
                for slot in repaired_tournament.slots
                if slot.availability is SlotAvailability.AVAILABLE
            )
            for match in matches
        }

        def reject_infeasible(
            evidence: tuple[dict[str, object], ...],
            remedies: tuple[dict[str, object], ...],
        ) -> None:
            if operations is not None:
                append_audit_event(
                    operations,
                    workspace.workspace_id,
                    event_type="repair_infeasible",
                    summary=(
                        "No valid repair satisfied the confirmed constraints; the "
                        "official schedule was preserved."
                    ),
                    structured_payload={
                        "disruption_id": disruption_id,
                        "official_schedule_preserved": True,
                        "evidence_codes": [item["code"] for item in evidence],
                        "remedy_codes": [item["code"] for item in remedies],
                    },
                    actor_type="system",
                )
            raise APIProblem(
                status=422,
                code="repair_infeasible",
                title="No valid repair exists",
                detail=(
                    "The selected disruption leaves no placement that satisfies capacity, "
                    "chronology, rest, and blackout rules. The official schedule is unchanged."
                ),
                evidence=evidence,
                remedies=remedies,
            )

        precheck = run_pre_solver_checks(
            repaired_tournament,
            matches,
            eligible,
            minimum_rest_minutes=minimum_rest_minutes(workspace),
        )
        if not precheck.can_solve:
            evidence = tuple(item.model_dump(mode="json") for item in precheck.evidence)
            remedies_by_code = {
                item.code.value: item.model_dump(mode="json") for item in precheck.remedies
            }
            remedies_by_code.setdefault(
                RemedyCode.ADD_VENUE_SLOTS.value,
                {
                    "code": RemedyCode.ADD_VENUE_SLOTS.value,
                    "description": "Add an eligible start time at either venue.",
                },
            )
            remedies_by_code.setdefault(
                RemedyCode.EXTEND_TOURNAMENT_WINDOW.value,
                {
                    "code": RemedyCode.EXTEND_TOURNAMENT_WINDOW.value,
                    "description": (
                        "Extend the tournament window and add venue slots before "
                        "reconfirming constraints."
                    ),
                },
            )
            reject_infeasible(evidence, tuple(remedies_by_code.values()))
        solver_started = perf_counter()
        try:
            result = repair_schedule(
                repaired_tournament,
                matches,
                baseline.placements,
                eligible,
                generated_at=datetime.now(UTC),
            )
        finally:
            if demo_protection is not None:
                demo_protection.release_job(workspace.workspace_id)
        observe(
            component="solver",
            event="minimum_change_repair",
            outcome=result.status,
            metadata={
                "duration_ms": round((perf_counter() - solver_started) * 1000, 3),
                "unavailable_slot_count": len(unavailable),
                "changed_count": len(result.changed_match_ids),
            },
        )
        observe(
            component="validator",
            event="repair",
            outcome=(
                "valid"
                if result.validation_report is not None and result.validation_report.valid
                else "invalid"
            ),
            metadata={
                "violation_count": (
                    len(result.validation_report.violations)
                    if result.validation_report is not None
                    else None
                )
            },
        )
        if result.status is RepairStatus.INFEASIBLE or result.validation_report is None:
            reject_infeasible(
                (
                    {
                        "code": "chronology_or_rest_conflict",
                        "message": (
                            "Remaining slots cannot preserve every confirmed chronology "
                            "and rest path."
                        ),
                    },
                ),
                (
                    {
                        "code": RemedyCode.ADD_VENUE_SLOTS.value,
                        "description": "Add an eligible start time at either venue.",
                    },
                    {
                        "code": RemedyCode.EXTEND_TOURNAMENT_WINDOW.value,
                        "description": (
                            "Extend the tournament window and add venue slots before "
                            "reconfirming constraints."
                        ),
                    },
                ),
            )
        draft_id = str(_uuid7())
        repaired = baseline.model_copy(
            update={
                "placements": result.placements,
                "metrics": _metric_evaluator(workspace, matches)(
                    baseline.profile, result.placements
                ),
                "validation_report": result.validation_report,
            }
        )
        workspace.drafts[draft_id] = repaired
        workspace.draft_revisions[draft_id] = workspace.tournament.revision
        diff = build_schedule_diff(
            baseline_version_id=UUID(str(official["version_id"])),
            draft_id=UUID(draft_id),
            baseline=baseline.placements,
            draft=result.placements,
            baseline_metrics=baseline.metrics,
            draft_metrics=repaired.metrics,
        )
        workspace.schedule_diffs[draft_id] = diff.model_dump(mode="json")
        specialist_evidence: tuple[Mapping[str, object], ...] = ()
        agent_status = "not_configured"
        if workflow_orchestrator is not None:
            try:
                specialist_evidence = await workflow_orchestrator.after_repair(
                    workspace=workspace,
                    draft_id=draft_id,
                    disruption=disruption,
                    diff=workspace.schedule_diffs[draft_id],
                )
                agent_status = _specialist_status(specialist_evidence)
            except Exception as exc:
                agent_status = "unavailable"
                observe(
                    component="agent",
                    event="repair_specialists",
                    outcome="unavailable",
                    metadata={"error_type": type(exc).__name__},
                )
        disruption["specialist_evidence"] = list(specialist_evidence)
        disruption["agent_status"] = agent_status
        observe(
            component="database",
            event="repair_draft_saved",
            outcome="success",
            metadata={"draft_id": draft_id, "moved_count": len(diff.moved)},
        )
        if operations is not None:
            append_audit_event(
                operations,
                workspace.workspace_id,
                event_type="repair_generated",
                summary="Generated and validated a minimum-change repair draft.",
                structured_payload={
                    "draft_id": draft_id,
                    "disruption_id": disruption_id,
                    "moved_count": len(diff.moved),
                    "agent_status": agent_status,
                    "specialist_evidence": specialist_evidence,
                },
            )
        return {
            "run_id": str(uuid4()),
            "status": "completed",
            "draft_id": draft_id,
            "agent_status": agent_status,
            "specialist_evidence": specialist_evidence,
        }

    @router.get("/schedule-diffs/{draft_id}")
    def read_schedule_diff(
        draft_id: str,
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ):
        diff = workspace.schedule_diffs.get(draft_id)
        if diff is None:
            raise APIProblem(
                status=409,
                code="schedule_diff_not_ready",
                title="Schedule diff is not ready",
                detail="A validated repair diff is not available for this draft.",
                retryable=True,
            )
        tournament = workspace.tournament
        draft = workspace.drafts.get(draft_id)
        if tournament is None or draft is None or not workspace.official_versions:
            raise APIProblem(
                status=409,
                code="schedule_diff_not_ready",
                title="Schedule diff is not ready",
                detail="The repair comparison cannot be verified from workspace state.",
                retryable=True,
            )
        baseline_version_id = str(diff["baseline_version_id"])
        baseline_version = next(
            (
                version
                for version in workspace.official_versions
                if str(version["version_id"]) == baseline_version_id
            ),
            None,
        )
        if baseline_version is None:
            raise APIProblem(
                status=409,
                code="schedule_diff_not_ready",
                title="Schedule diff is not ready",
                detail="The immutable official baseline is unavailable.",
                retryable=True,
            )
        baseline = workspace.drafts.get(str(baseline_version["approved_draft_id"]))
        if baseline is None:
            raise APIProblem(
                status=409,
                code="schedule_diff_not_ready",
                title="Schedule diff is not ready",
                detail="The immutable official baseline placements are unavailable.",
                retryable=True,
            )
        baseline_by_match = {str(item.match_id): item for item in baseline.placements}
        draft_by_match = {str(item.match_id): item for item in draft.placements}
        venue_by_id = {venue.id: venue for venue in tournament.venues}
        team_names = {str(team.id): team.display_name for team in tournament.teams}
        matches = generate_match_graph(tournament)

        def participant_label(value: str) -> str:
            return {
                "A1": "Group A Winner",
                "A2": "Group A Runner-up",
                "B1": "Group B Winner",
                "B2": "Group B Runner-up",
                "SF1 Winner": "Semifinal 1 Winner",
                "SF2 Winner": "Semifinal 2 Winner",
            }.get(value, team_names.get(value, value))

        def placement_view(placement) -> dict[str, object] | None:
            if placement is None:
                return None
            venue = venue_by_id[placement.venue_id]
            zone = ZoneInfo(venue.iana_time_zone)
            return {
                "slot_id": str(placement.slot_id),
                "venue": venue.display_name,
                "starts_at": placement.starts_at_utc.astimezone(zone).isoformat(),
                "ends_at": placement.ends_at_utc.astimezone(zone).isoformat(),
                "timezone": venue.iana_time_zone,
            }

        changed = {
            change: {str(item) for item in diff.get(change, ())}
            for change in ("unchanged", "moved", "added", "removed")
        }
        fixture_views = []
        for match in matches:
            match_id = str(match.id)
            change = next(
                (name for name, identifiers in changed.items() if match_id in identifiers),
                "unchanged",
            )
            code = (
                f"G{match.sequence:02d}"
                if match.stage is MatchStage.GROUP
                else "SF1"
                if match.sequence == 13
                else "SF2"
                if match.sequence == 14
                else "F1"
            )
            fixture_views.append(
                {
                    "id": match_id,
                    "code": code,
                    "fixture": (
                        f"{participant_label(match.participant_a)} vs "
                        f"{participant_label(match.participant_b)}"
                    ),
                    "change": change,
                    "before": placement_view(baseline_by_match.get(match_id)),
                    "after": placement_view(draft_by_match.get(match_id)),
                }
            )
        return {
            **diff,
            "validation_valid": draft.validation_report.valid,
            "fixture_views": fixture_views,
        }

    return router
