from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence

from app.domain.matches import MatchDefinition
from app.domain.schedules import FixturePlacement
from app.domain.tournament import TournamentConfig


def _digest(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def validation_input_digest(
    tournament: TournamentConfig,
    matches: Sequence[MatchDefinition],
    minimum_rest_minutes: int,
) -> str:
    return _digest(
        {
            "tournament": tournament.model_dump(mode="json"),
            "matches": [
                match.model_dump(mode="json")
                for match in sorted(matches, key=lambda item: str(item.id))
            ],
            "minimum_rest_minutes": minimum_rest_minutes,
        }
    )


def placement_digest(placements: Sequence[FixturePlacement]) -> str:
    return _digest(
        [
            placement.model_dump(mode="json")
            for placement in sorted(
                placements,
                key=lambda item: (str(item.match_id), str(item.slot_id)),
            )
        ]
    )
