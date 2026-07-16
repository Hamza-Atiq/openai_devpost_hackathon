from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from app.domain.tournament import TournamentConfig


@dataclass(slots=True)
class GuestWorkspace:
    workspace_id: str
    tournament: TournamentConfig | None
    weather: dict[str, Any] = field(
        default_factory=lambda: {
            "mode": "live",
            "quality": "not_requested",
            "demo_mode_available": True,
            "scenario_id": None,
        }
    )
    schedule_runs: dict[str, dict[str, Any]] = field(default_factory=dict)
    drafts: dict[str, Any] = field(default_factory=dict)
    idempotency: dict[str, dict[str, object]] = field(default_factory=dict)
    official_versions: list[dict[str, object]] = field(default_factory=list)
    edits: dict[str, dict[str, object]] = field(default_factory=dict)
    disruptions: dict[str, dict[str, object]] = field(default_factory=dict)
    schedule_diffs: dict[str, dict[str, object]] = field(default_factory=dict)


class GuestWorkspaceStore:
    def __init__(self) -> None:
        self._items: dict[str, GuestWorkspace] = {}

    @staticmethod
    def _digest(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def create(self, tournament: TournamentConfig | None) -> tuple[str, GuestWorkspace]:
        token = secrets.token_urlsafe(32)
        workspace = GuestWorkspace(workspace_id=str(uuid4()), tournament=tournament)
        self._items[self._digest(token)] = workspace
        return token, workspace

    def get(self, token: str | None) -> GuestWorkspace | None:
        if not token:
            return None
        return self._items.get(self._digest(token))

    def delete(self, token: str) -> None:
        self._items.pop(self._digest(token), None)
