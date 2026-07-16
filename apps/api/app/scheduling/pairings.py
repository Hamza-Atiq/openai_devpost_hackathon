from __future__ import annotations

from hashlib import sha256
from itertools import combinations
from uuid import UUID

from app.domain.matches import MatchDefinition, MatchStage
from app.domain.tournament import TournamentConfig


def _stable_uuid7(tournament_id: UUID, match_code: str) -> UUID:
    raw = bytearray(sha256(f"{tournament_id}:match:{match_code}".encode()).digest()[:16])
    raw[6] = (raw[6] & 0x0F) | 0x70
    raw[8] = (raw[8] & 0x3F) | 0x80
    return UUID(bytes=bytes(raw))


def generate_match_graph(tournament: TournamentConfig) -> tuple[MatchDefinition, ...]:
    """Build the fixed V1 round-robin and knockout dependency graph."""
    matches: list[MatchDefinition] = []

    for group in sorted(tournament.groups, key=lambda item: item.code):
        for team_a, team_b in combinations(sorted(group.team_ids, key=str), 2):
            sequence = len(matches) + 1
            matches.append(
                MatchDefinition(
                    id=_stable_uuid7(tournament.id, f"G{sequence:02d}"),
                    stage=MatchStage.GROUP,
                    sequence=sequence,
                    participant_a=str(team_a),
                    participant_b=str(team_b),
                )
            )

    group_match_ids = tuple(match.id for match in matches)
    semifinal_specs = (("SF1", "A1", "B2"), ("SF2", "B1", "A2"))
    semifinals: list[MatchDefinition] = []
    for code, participant_a, participant_b in semifinal_specs:
        sequence = len(matches) + 1
        semifinal = MatchDefinition(
            id=_stable_uuid7(tournament.id, code),
            stage=MatchStage.SEMIFINAL,
            sequence=sequence,
            participant_a=participant_a,
            participant_b=participant_b,
            dependency_ids=group_match_ids,
        )
        matches.append(semifinal)
        semifinals.append(semifinal)

    matches.append(
        MatchDefinition(
            id=_stable_uuid7(tournament.id, "F1"),
            stage=MatchStage.FINAL,
            sequence=15,
            participant_a="SF1 Winner",
            participant_b="SF2 Winner",
            dependency_ids=tuple(match.id for match in semifinals),
        )
    )
    return tuple(matches)
