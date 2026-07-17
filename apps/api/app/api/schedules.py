from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, Query, Response, status
from pydantic import Field, model_validator

from app.api.operations import OperationsState
from app.api.problems import APIProblem
from app.api.routes import require_workspace
from app.api.workspace import GuestWorkspace
from app.domain.common import DomainModel
from app.domain.matches import MatchDefinition, MatchStage
from app.domain.schedules import ScheduleMetrics, ScheduleProfile
from app.domain.venues import SlotAvailability
from app.fairness.evaluator import evaluate_schedule_metrics
from app.optimization.config import load_optimization_config
from app.scheduling.comparison import compare_profile_options
from app.scheduling.diff import build_schedule_diff
from app.scheduling.pairings import generate_match_graph
from app.scheduling.profiles import ComponentPenalties, generate_profile_options
from app.scheduling.repair import RepairStatus, repair_schedule


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
        slot.id
        for slot in tournament.slots
        if slot.availability is SlotAvailability.AVAILABLE
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


def build_schedule_router(operations: OperationsState | None = None) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.post("/schedule-runs", status_code=status.HTTP_202_ACCEPTED)
    def start_schedule_run(
        body: ScheduleRunInput,
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
        matches, eligibility = _eligibility(workspace)
        batch = generate_profile_options(
            workspace.tournament,
            matches,
            eligibility,
            generated_at=datetime.now(UTC),
            metric_evaluator=_metric_evaluator(workspace, matches),
            component_penalties=_component_penalties(workspace, matches, eligibility),
            custom_priorities=(
                body.custom_priorities.model_dump(exclude={"schema_version"})
                if body.custom_priorities is not None
                else None
            ),
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
        }
        workspace.schedule_runs[run_id] = run
        accepted = {"run_id": run_id, "status": "accepted"}
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

    @router.post("/schedule-drafts/{draft_id}/feedback", status_code=201)
    def record_feedback(
        draft_id: str,
        body: dict[str, Any],
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ):
        if draft_id not in workspace.drafts:
            raise APIProblem(
                status=404,
                code="schedule_draft_not_found",
                title="Schedule draft not found",
                detail="The draft does not belong to this workspace.",
            )
        return {"draft_id": draft_id, "feedback": body}

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
        if operations is not None:
            operations.audit_events.setdefault(workspace.workspace_id, []).append(
                {
                    "id": str(_uuid7()),
                    "actor_type": "organizer",
                    "event_type": "schedule_approved",
                    "summary": f"Schedule Version {version['version_number']} approved.",
                    "structured_payload": {
                        "version_id": version["version_id"],
                        "version_number": version["version_number"],
                        "draft_id": draft_id,
                    },
                    "occurred_at": version["approved_at"],
                    "agent_provenance": None,
                }
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
        workspace.idempotency[f"restore:{idempotency_key}"] = restored
        return restored

    @router.get("/schedule-versions")
    def list_schedule_versions(
        workspace: Annotated[GuestWorkspace, Depends(require_workspace)],
    ):
        return {"items": tuple(reversed(workspace.official_versions))}

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
        disruption_id = str(uuid4())
        disruption = {
            "disruption_id": disruption_id,
            "status": "active",
            **body.model_dump(mode="json"),
        }
        workspace.disruptions[disruption_id] = disruption
        return disruption

    @router.post("/disruptions/{disruption_id}/repair-runs", status_code=202)
    def start_repair(
        disruption_id: str,
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
        result = repair_schedule(
            repaired_tournament,
            matches,
            baseline.placements,
            eligible,
            generated_at=datetime.now(UTC),
        )
        if result.status is RepairStatus.INFEASIBLE or result.validation_report is None:
            raise APIProblem(
                status=422,
                code="repair_infeasible",
                title="No valid repair exists",
                detail="The official schedule is preserved; edit and reconfirm constraints.",
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
        return {
            "run_id": str(uuid4()),
            "status": "completed",
            "draft_id": draft_id,
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
        return diff

    return router
