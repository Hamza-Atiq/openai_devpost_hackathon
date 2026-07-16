from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

IMMUTABLE_TABLES = {
    "tournament_revisions",
    "schedule_versions",
    "audit_events",
}


class Base(DeclarativeBase):
    pass


class IdMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True)


class WorkspaceOwned:
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("guest_workspaces.id", ondelete="CASCADE"), index=True
    )


class GuestWorkspace(IdMixin, Base):
    __tablename__ = "guest_workspaces"

    identity_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    mode: Mapped[str] = mapped_column(String(24))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Tournament(IdMixin, WorkspaceOwned, Base):
    __tablename__ = "tournaments"
    __table_args__ = (
        Index(
            "uq_tournaments_active_workspace",
            "workspace_id",
            unique=True,
            postgresql_where=text("active = true AND deleted_at IS NULL"),
            sqlite_where=text("active = 1 AND deleted_at IS NULL"),
        ),
    )

    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(48), default="draft_setup")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    current_revision: Mapped[int] = mapped_column(Integer, default=0)
    current_official_version_id: Mapped[str | None] = mapped_column(String(36))
    match_format_preset: Mapped[str | None] = mapped_column(String(8))
    allocation_minutes: Mapped[int | None] = mapped_column(Integer)
    start_date: Mapped[Any | None] = mapped_column(Date)
    end_date: Mapped[Any | None] = mapped_column(Date)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TournamentGroup(IdMixin, WorkspaceOwned, Base):
    __tablename__ = "tournament_groups"
    __table_args__ = (UniqueConstraint("tournament_id", "code", name="uq_group_code"),)

    tournament_id: Mapped[str] = mapped_column(
        ForeignKey("tournaments.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(32))
    display_name: Mapped[str] = mapped_column(String(100))


class Team(IdMixin, WorkspaceOwned, Base):
    __tablename__ = "teams"
    __table_args__ = (
        UniqueConstraint(
            "tournament_id", "normalized_name", name="uq_teams_tournament_normalized_name"
        ),
    )

    tournament_id: Mapped[str] = mapped_column(
        ForeignKey("tournaments.id", ondelete="CASCADE"), index=True
    )
    group_id: Mapped[str] = mapped_column(
        ForeignKey("tournament_groups.id", ondelete="RESTRICT"), index=True
    )
    display_name: Mapped[str] = mapped_column(String(100))
    normalized_name: Mapped[str] = mapped_column(String(100))


class Venue(IdMixin, WorkspaceOwned, Base):
    __tablename__ = "venues"

    tournament_id: Mapped[str] = mapped_column(
        ForeignKey("tournaments.id", ondelete="CASCADE"), index=True
    )
    display_name: Mapped[str] = mapped_column(String(160))
    city: Mapped[str] = mapped_column(String(120))
    country_code: Mapped[str] = mapped_column(String(2))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    iana_time_zone: Mapped[str] = mapped_column(String(64))
    geocoding_provider: Mapped[str | None] = mapped_column(String(80))
    geocoding_reference: Mapped[str | None] = mapped_column(String(200))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class VenueSlot(IdMixin, WorkspaceOwned, Base):
    __tablename__ = "venue_slots"
    __table_args__ = (
        CheckConstraint("ends_at_utc > starts_at_utc", name="ck_venue_slot_positive_interval"),
    )

    tournament_id: Mapped[str] = mapped_column(
        ForeignKey("tournaments.id", ondelete="CASCADE"), index=True
    )
    venue_id: Mapped[str] = mapped_column(
        ForeignKey("venues.id", ondelete="CASCADE"), index=True
    )
    starts_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    local_date: Mapped[Any] = mapped_column(Date)
    availability: Mapped[str] = mapped_column(String(24))
    source: Mapped[str] = mapped_column(String(48))


class ConstraintRecord(IdMixin, WorkspaceOwned, Base):
    __tablename__ = "constraints"
    __table_args__ = (
        CheckConstraint("classification IN ('hard', 'soft')", name="ck_constraint_classification"),
        CheckConstraint(
            "priority IS NULL OR (priority >= 0 AND priority <= 100)",
            name="ck_constraint_priority",
        ),
        UniqueConstraint("tournament_id", "revision", "id", name="uq_constraint_revision"),
    )

    tournament_id: Mapped[str] = mapped_column(
        ForeignKey("tournaments.id", ondelete="CASCADE"), index=True
    )
    revision: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(64))
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON)
    classification: Mapped[str] = mapped_column(String(8))
    priority: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(48))
    status: Mapped[str] = mapped_column(String(32))
    explanation: Mapped[str] = mapped_column(Text)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TournamentRevision(IdMixin, WorkspaceOwned, Base):
    __tablename__ = "tournament_revisions"
    __table_args__ = (
        UniqueConstraint("tournament_id", "revision", name="uq_tournament_revision"),
        {"info": {"immutable": True}},
    )

    tournament_id: Mapped[str] = mapped_column(
        ForeignKey("tournaments.id", ondelete="CASCADE"), index=True
    )
    revision: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    input_digest: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MatchDefinition(IdMixin, WorkspaceOwned, Base):
    __tablename__ = "match_definitions"
    __table_args__ = (UniqueConstraint("tournament_id", "sequence", name="uq_match_sequence"),)

    tournament_id: Mapped[str] = mapped_column(
        ForeignKey("tournaments.id", ondelete="CASCADE"), index=True
    )
    tournament_revision_id: Mapped[str] = mapped_column(
        ForeignKey("tournament_revisions.id", ondelete="RESTRICT"), index=True
    )
    stage: Mapped[str] = mapped_column(String(32))
    sequence: Mapped[int] = mapped_column(Integer)
    participant_a: Mapped[dict[str, Any]] = mapped_column(JSON)
    participant_b: Mapped[dict[str, Any]] = mapped_column(JSON)
    dependency_ids: Mapped[list[str]] = mapped_column(JSON)


class ScheduleRun(IdMixin, WorkspaceOwned, Base):
    __tablename__ = "schedule_runs"

    tournament_id: Mapped[str] = mapped_column(
        ForeignKey("tournaments.id", ondelete="CASCADE"), index=True
    )
    tournament_revision_id: Mapped[str] = mapped_column(
        ForeignKey("tournament_revisions.id", ondelete="RESTRICT"), index=True
    )
    request_type: Mapped[str] = mapped_column(String(32))
    profile: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    solver_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class ScheduleDraft(IdMixin, WorkspaceOwned, Base):
    __tablename__ = "schedule_drafts"

    tournament_id: Mapped[str] = mapped_column(
        ForeignKey("tournaments.id", ondelete="CASCADE"), index=True
    )
    tournament_revision_id: Mapped[str] = mapped_column(
        ForeignKey("tournament_revisions.id", ondelete="RESTRICT"), index=True
    )
    schedule_run_id: Mapped[str] = mapped_column(
        ForeignKey("schedule_runs.id", ondelete="RESTRICT"), index=True
    )
    baseline_version_id: Mapped[str | None] = mapped_column(String(36), index=True)
    profile: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), index=True)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON)
    validation_report: Mapped[dict[str, Any]] = mapped_column(JSON)
    validation_digest: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class FixturePlacement(IdMixin, WorkspaceOwned, Base):
    __tablename__ = "fixture_placements"
    __table_args__ = (
        UniqueConstraint("draft_id", "match_id", name="uq_draft_match_placement"),
        UniqueConstraint("draft_id", "venue_slot_id", name="uq_draft_slot_placement"),
        CheckConstraint("ends_at_utc > starts_at_utc", name="ck_placement_positive_interval"),
    )

    tournament_id: Mapped[str] = mapped_column(
        ForeignKey("tournaments.id", ondelete="CASCADE"), index=True
    )
    draft_id: Mapped[str] = mapped_column(
        ForeignKey("schedule_drafts.id", ondelete="CASCADE"), index=True
    )
    match_id: Mapped[str] = mapped_column(
        ForeignKey("match_definitions.id", ondelete="RESTRICT"), index=True
    )
    venue_slot_id: Mapped[str] = mapped_column(
        ForeignKey("venue_slots.id", ondelete="RESTRICT"), index=True
    )
    starts_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ScheduleVersion(IdMixin, WorkspaceOwned, Base):
    __tablename__ = "schedule_versions"
    __table_args__ = (
        UniqueConstraint("tournament_id", "version_number", name="uq_schedule_version_number"),
        UniqueConstraint("approved_draft_id", name="uq_schedule_version_draft"),
        {"info": {"immutable": True}},
    )

    tournament_id: Mapped[str] = mapped_column(
        ForeignKey("tournaments.id", ondelete="CASCADE"), index=True
    )
    tournament_revision_id: Mapped[str] = mapped_column(
        ForeignKey("tournament_revisions.id", ondelete="RESTRICT"), index=True
    )
    version_number: Mapped[int] = mapped_column(Integer)
    approved_draft_id: Mapped[str] = mapped_column(
        ForeignKey("schedule_drafts.id", ondelete="RESTRICT"), index=True
    )
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    supersedes_id: Mapped[str | None] = mapped_column(
        ForeignKey("schedule_versions.id", ondelete="RESTRICT"), index=True
    )


class WeatherSnapshot(IdMixin, WorkspaceOwned, Base):
    __tablename__ = "weather_snapshots"

    tournament_id: Mapped[str] = mapped_column(
        ForeignKey("tournaments.id", ondelete="CASCADE"), index=True
    )
    venue_id: Mapped[str] = mapped_column(
        ForeignKey("venues.id", ondelete="CASCADE"), index=True
    )
    mode: Mapped[str] = mapped_column(String(16))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    valid_hours: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    quality: Mapped[str] = mapped_column(String(24))
    provider_metadata: Mapped[dict[str, Any]] = mapped_column(JSON)


class Disruption(IdMixin, WorkspaceOwned, Base):
    __tablename__ = "disruptions"

    tournament_id: Mapped[str] = mapped_column(
        ForeignKey("tournaments.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(48))
    unavailable_slot_ids: Mapped[list[str]] = mapped_column(JSON)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ScheduleDiff(IdMixin, WorkspaceOwned, Base):
    __tablename__ = "schedule_diffs"
    __table_args__ = (UniqueConstraint("baseline_version_id", "draft_id", name="uq_schedule_diff"),)

    tournament_id: Mapped[str] = mapped_column(
        ForeignKey("tournaments.id", ondelete="CASCADE"), index=True
    )
    baseline_version_id: Mapped[str] = mapped_column(
        ForeignKey("schedule_versions.id", ondelete="CASCADE"), index=True
    )
    draft_id: Mapped[str] = mapped_column(
        ForeignKey("schedule_drafts.id", ondelete="CASCADE"), index=True
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AgentRun(IdMixin, WorkspaceOwned, Base):
    __tablename__ = "agent_runs"

    tournament_id: Mapped[str | None] = mapped_column(
        ForeignKey("tournaments.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(48))
    provider: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(120))
    input_revision: Mapped[int | None] = mapped_column(Integer)
    output_schema_version: Mapped[str] = mapped_column(String(32))
    tool_evidence_ids: Mapped[list[str]] = mapped_column(JSON)
    validation_status: Mapped[str] = mapped_column(String(32))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentSession(IdMixin, WorkspaceOwned, Base):
    __tablename__ = "agent_sessions"
    __table_args__ = (
        UniqueConstraint("workspace_id", "conversation_id", name="uq_agent_conversation"),
    )

    conversation_id: Mapped[str] = mapped_column(String(128))
    session_data: Mapped[dict[str, Any]] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuditEvent(IdMixin, WorkspaceOwned, Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_workspace_occurred", "workspace_id", "occurred_at"),
        {"info": {"immutable": True}},
    )

    tournament_id: Mapped[str | None] = mapped_column(
        ForeignKey("tournaments.id", ondelete="CASCADE"), index=True
    )
    actor_type: Mapped[str] = mapped_column(String(32))
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    summary: Mapped[str] = mapped_column(Text)
    structured_payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


FEEDBACK_REASONS = (
    "weather_preference",
    "unfair_rest_distribution",
    "venue_preference",
    "unsuitable_time_slot",
    "rivalry_requirement",
    "travel_concern",
    "other",
)


class WorkspaceFeedback(IdMixin, WorkspaceOwned, Base):
    __tablename__ = "workspace_feedback"
    __table_args__ = (
        CheckConstraint(
            "reason_code IN (" + ", ".join(f"'{value}'" for value in FEEDBACK_REASONS) + ")",
            name="ck_workspace_feedback_reason_code",
        ),
    )

    tournament_id: Mapped[str | None] = mapped_column(
        ForeignKey("tournaments.id", ondelete="CASCADE"), index=True
    )
    target_type: Mapped[str] = mapped_column(String(48))
    target_id: Mapped[str] = mapped_column(String(36))
    reason_code: Mapped[str] = mapped_column(String(48))
    optional_text: Mapped[str | None] = mapped_column(Text)
    consent_scope: Mapped[str] = mapped_column(String(32), default="workspace_only")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class FeedbackConsent(IdMixin, Base):
    __tablename__ = "feedback_consents"

    anonymous_subject_id: Mapped[str] = mapped_column(String(128), index=True)
    consent_scope: Mapped[str] = mapped_column(String(32))
    consented_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revocation_token: Mapped[str] = mapped_column(String(128), unique=True)
    retained_feedback: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class IdempotencyKey(IdMixin, WorkspaceOwned, Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = (
        UniqueConstraint("workspace_id", "operation", "key", name="uq_idempotency_key"),
    )

    operation: Mapped[str] = mapped_column(String(80))
    key: Mapped[str] = mapped_column(String(128))
    request_digest: Mapped[str] = mapped_column(String(128))
    response_status: Mapped[int | None] = mapped_column(Integer)
    response_body: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class Job(IdMixin, WorkspaceOwned, Base):
    __tablename__ = "jobs"

    tournament_id: Mapped[str | None] = mapped_column(
        ForeignKey("tournaments.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


def _reject_mutation(_mapper: Any, _connection: Any, target: Any) -> None:
    raise ValueError(f"{target.__tablename__} rows are immutable")


for _immutable_model in (TournamentRevision, ScheduleVersion, AuditEvent):
    event.listen(_immutable_model, "before_update", _reject_mutation)
    event.listen(_immutable_model, "before_delete", _reject_mutation)
