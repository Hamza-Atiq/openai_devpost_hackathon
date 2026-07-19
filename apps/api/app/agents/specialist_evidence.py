from __future__ import annotations

from app.agents.director import SpecialistRequest
from app.agents.rules import ConstraintInterpretationInput
from app.agents.schemas import AgentRole
from app.agents.specialist_runtime import SpecialistRunRequest
from app.agents.strategy import StrategyInput
from app.api.workspace import GuestWorkspace
from app.domain.schedules import ScheduleProfile


def _current_constraints(workspace: GuestWorkspace) -> tuple[str, ...]:
    tournament = workspace.tournament
    if tournament is None:
        return ()
    return (
        f"match_format={tournament.match_format_preset.value}",
        f"allocation_minutes={tournament.allocation_minutes}",
        f"teams={len(tournament.teams)}",
        f"groups={len(tournament.groups)}",
        f"venues={len(tournament.venues)}",
        f"slots={len(tournament.slots)}",
        f"hard_constraints={len(tournament.constraints.hard)}",
        f"soft_constraints={len(tournament.constraints.soft)}",
    )


def _latest_validated_metrics(
    workspace: GuestWorkspace,
) -> dict[ScheduleProfile, dict[str, float]] | None:
    for run in reversed(tuple(workspace.schedule_runs.values())):
        if run.get("status") != "completed":
            continue
        metrics: dict[ScheduleProfile, dict[str, float]] = {}
        for option in run.get("options", ()):
            if not option.get("validation_valid"):
                continue
            profile = ScheduleProfile(str(option["profile"]))
            metrics[profile] = {
                str(name): float(value)
                for name, value in dict(option.get("metrics", {})).items()
                if isinstance(value, int | float) and not isinstance(value, bool)
            }
        if metrics:
            return metrics
    return None


def build_specialist_request(
    workspace: GuestWorkspace,
    specialist_request: SpecialistRequest,
    user_message: str,
) -> SpecialistRunRequest | None:
    tournament = workspace.tournament
    revision = tournament.revision if tournament is not None else 0
    constraints = _current_constraints(workspace)

    if specialist_request.role is AgentRole.RULES_CONSTRAINT:
        return SpecialistRunRequest(
            role=specialist_request.role,
            payload=ConstraintInterpretationInput(
                current_constraints=constraints,
                user_text=user_message,
                tournament_context={
                    "revision": revision,
                    "tournament_name": tournament.name if tournament is not None else None,
                    "status": tournament.status if tournament is not None else None,
                },
            ),
            invocation_reason=specialist_request.reason,
            tournament_revision=revision,
            consumed_fields=("current_constraints", "tournament_context"),
            tool_name="constraint_precheck",
            deterministic_authority=True,
        )

    if specialist_request.role is AgentRole.SCHEDULING_STRATEGY:
        validated_metrics = _latest_validated_metrics(workspace)
        profiles = (
            tuple(validated_metrics)
            if validated_metrics is not None
            else (
                ScheduleProfile.BALANCED,
                ScheduleProfile.WEATHER_FIRST,
                ScheduleProfile.FAIRNESS_FIRST,
            )
        )
        return SpecialistRunRequest(
            role=specialist_request.role,
            payload=StrategyInput(
                confirmed_constraints=constraints,
                priorities=(
                    tournament.priorities.model_dump(exclude={"schema_version"})
                    if tournament is not None
                    else {}
                ),
                available_profiles=profiles,
                validated_metrics=validated_metrics,
            ),
            invocation_reason=specialist_request.reason,
            tournament_revision=revision,
            consumed_fields=("validated_metrics", "confirmed_constraints"),
            tool_name="read_validated_comparison",
            deterministic_authority=True,
        )

    return None
