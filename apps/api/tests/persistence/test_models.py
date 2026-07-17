from __future__ import annotations

from app.persistence.models import IMMUTABLE_TABLES, Base
from sqlalchemy import Index, UniqueConstraint

EXPECTED_TABLES = {
    "guest_workspaces",
    "workspace_snapshots",
    "tournaments",
    "tournament_groups",
    "teams",
    "venues",
    "venue_slots",
    "constraints",
    "tournament_revisions",
    "match_definitions",
    "schedule_runs",
    "schedule_drafts",
    "fixture_placements",
    "schedule_versions",
    "weather_snapshots",
    "disruptions",
    "schedule_diffs",
    "agent_runs",
    "agent_sessions",
    "audit_events",
    "workspace_feedback",
    "feedback_consents",
    "idempotency_keys",
    "jobs",
}


def test_metadata_contains_every_persistence_entity() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_workspace_owned_tables_have_workspace_foreign_key_and_index() -> None:
    for name, table in Base.metadata.tables.items():
        if name in {"guest_workspaces", "feedback_consents"}:
            continue
        assert "workspace_id" in table.c, name
        assert any(
            foreign_key.target_fullname == "guest_workspaces.id"
            for foreign_key in table.c.workspace_id.foreign_keys
        ), name
        assert table.c.workspace_id.index, name


def test_active_tournament_and_team_name_constraints_are_declared() -> None:
    tournaments = Base.metadata.tables["tournaments"]
    active_indexes = [
        item
        for item in tournaments.indexes
        if isinstance(item, Index) and item.name == "uq_tournaments_active_workspace"
    ]
    assert len(active_indexes) == 1
    assert active_indexes[0].unique
    assert active_indexes[0].dialect_options["postgresql"]["where"] is not None

    teams = Base.metadata.tables["teams"]
    assert any(
        isinstance(item, UniqueConstraint)
        and item.name == "uq_teams_tournament_normalized_name"
        for item in teams.constraints
    )


def test_revision_version_and_audit_rows_are_marked_immutable() -> None:
    assert IMMUTABLE_TABLES == {
        "tournament_revisions",
        "schedule_versions",
        "audit_events",
    }
    for table_name in IMMUTABLE_TABLES:
        assert Base.metadata.tables[table_name].info["immutable"] is True


def test_feedback_reason_and_consent_constraints_are_declared() -> None:
    feedback = Base.metadata.tables["workspace_feedback"]
    reason_constraint = next(
        constraint
        for constraint in feedback.constraints
        if constraint.name == "ck_workspace_feedback_reason_code"
    )
    sql = str(reason_constraint.sqltext)
    for reason in (
        "weather_preference",
        "unfair_rest_distribution",
        "venue_preference",
        "unsuitable_time_slot",
        "rivalry_requirement",
        "travel_concern",
        "other",
    ):
        assert reason in sql

    consents = Base.metadata.tables["feedback_consents"]
    assert "workspace_id" not in consents.c
    assert consents.c.revocation_token.unique
