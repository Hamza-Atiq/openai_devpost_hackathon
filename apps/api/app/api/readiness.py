from __future__ import annotations

from app.api.workspace import GuestWorkspace
from app.scheduling.pairings import generate_match_graph
from app.scheduling.precheck import PrecheckResult, run_pre_solver_checks


def minimum_rest_minutes(workspace: GuestWorkspace) -> int:
    return workspace.setup_draft.minimum_rest_minutes if workspace.setup_draft else 0


def run_workspace_precheck(workspace: GuestWorkspace) -> PrecheckResult:
    if workspace.tournament is None:
        raise ValueError("tournament is required for readiness checks")
    matches = generate_match_graph(workspace.tournament)
    raw_slot_ids = frozenset(slot.id for slot in workspace.tournament.slots)
    eligibility = {match.id: raw_slot_ids for match in matches}
    return run_pre_solver_checks(
        workspace.tournament,
        matches,
        eligibility,
        minimum_rest_minutes=minimum_rest_minutes(workspace),
    )
