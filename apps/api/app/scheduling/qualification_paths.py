from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from app.domain.matches import MatchDefinition, MatchStage
from app.domain.tournament import TournamentConfig


class QualificationRole(StrEnum):
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"


class InvalidQualificationAssignmentError(ValueError):
    """Raised when concrete teams violate qualification-role exclusivity."""


@dataclass(frozen=True, slots=True)
class TeamQualificationPath:
    team_id: UUID
    role: QualificationRole
    source_group_match_ids: tuple[UUID, ...]
    semifinal_match_id: UUID
    final_match_id: UUID


@dataclass(frozen=True, slots=True)
class FinalQualificationPath:
    semifinal_match_id: UUID
    final_match_id: UUID


@dataclass(frozen=True, slots=True)
class QualificationPathMatrix:
    team_paths: tuple[TeamQualificationPath, ...]
    final_paths: tuple[FinalQualificationPath, ...]
    exclusive_role_sets: tuple[frozenset[QualificationRole], ...]


_ROLES_BY_GROUP = {
    "A": (QualificationRole.A1, QualificationRole.A2),
    "B": (QualificationRole.B1, QualificationRole.B2),
}


def build_qualification_path_matrix(
    tournament: TournamentConfig,
    matches: Sequence[MatchDefinition],
) -> QualificationPathMatrix:
    group_matches = tuple(match for match in matches if match.stage is MatchStage.GROUP)
    semifinals = tuple(match for match in matches if match.stage is MatchStage.SEMIFINAL)
    finals = tuple(match for match in matches if match.stage is MatchStage.FINAL)
    if len(group_matches) != 12 or len(semifinals) != 2 or len(finals) != 1:
        raise ValueError("qualification paths require the fixed 15-match graph")

    semifinal_by_role: dict[QualificationRole, MatchDefinition] = {}
    for semifinal in semifinals:
        for participant in (semifinal.participant_a, semifinal.participant_b):
            try:
                role = QualificationRole(participant)
            except ValueError as error:
                raise ValueError(f"unknown semifinal qualification role: {participant}") from error
            if role in semifinal_by_role:
                raise ValueError(f"qualification role appears more than once: {role}")
            semifinal_by_role[role] = semifinal

    if set(semifinal_by_role) != set(QualificationRole):
        raise ValueError("semifinal graph must contain A1, A2, B1, and B2 exactly once")

    final = finals[0]
    team_paths: list[TeamQualificationPath] = []
    for group in sorted(tournament.groups, key=lambda item: item.code):
        for team_id in sorted(group.team_ids, key=str):
            team_group_matches = tuple(
                match.id
                for match in group_matches
                if str(team_id) in (match.participant_a, match.participant_b)
            )
            if len(team_group_matches) != 3:
                raise ValueError(f"team {team_id} must have exactly three group matches")
            for role in _ROLES_BY_GROUP[group.code]:
                team_paths.append(
                    TeamQualificationPath(
                        team_id=team_id,
                        role=role,
                        source_group_match_ids=team_group_matches,
                        semifinal_match_id=semifinal_by_role[role].id,
                        final_match_id=final.id,
                    )
                )

    final_paths = tuple(
        FinalQualificationPath(semifinal_match_id=semifinal.id, final_match_id=final.id)
        for semifinal in sorted(semifinals, key=lambda item: item.sequence)
    )
    return QualificationPathMatrix(
        team_paths=tuple(team_paths),
        final_paths=final_paths,
        exclusive_role_sets=(
            frozenset(_ROLES_BY_GROUP["A"]),
            frozenset(_ROLES_BY_GROUP["B"]),
        ),
    )


def validate_role_assignment(
    matrix: QualificationPathMatrix,
    assignment: Mapping[QualificationRole, UUID],
) -> None:
    assigned_teams = tuple(assignment.values())
    if len(set(assigned_teams)) != len(assigned_teams):
        raise InvalidQualificationAssignmentError(
            "a team cannot occupy multiple qualification roles"
        )

    allowed_by_role = {
        role: {path.team_id for path in matrix.team_paths if path.role is role}
        for role in QualificationRole
    }
    for role, team_id in assignment.items():
        if team_id not in allowed_by_role[role]:
            raise InvalidQualificationAssignmentError(
                f"team {team_id} does not belong to Group {role.value[0]}"
            )
