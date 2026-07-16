from __future__ import annotations

import pytest
from app.domain.matches import MatchStage
from app.scheduling.pairings import generate_match_graph
from app.scheduling.qualification_paths import (
    InvalidQualificationAssignmentError,
    QualificationRole,
    build_qualification_path_matrix,
    validate_role_assignment,
)
from tests.domain.factories import valid_tournament


def test_enumerates_every_exclusive_group_to_final_path() -> None:
    tournament = valid_tournament()
    matches = generate_match_graph(tournament)

    matrix = build_qualification_path_matrix(tournament, matches)

    assert len(matrix.team_paths) == 16
    assert len(matrix.final_paths) == 2
    assert matrix.exclusive_role_sets == (
        frozenset((QualificationRole.A1, QualificationRole.A2)),
        frozenset((QualificationRole.B1, QualificationRole.B2)),
    )

    groups = {group.code: group for group in tournament.groups}
    expected_roles = {
        "A": {QualificationRole.A1, QualificationRole.A2},
        "B": {QualificationRole.B1, QualificationRole.B2},
    }
    for group_code, group in groups.items():
        for team_id in group.team_ids:
            paths = tuple(path for path in matrix.team_paths if path.team_id == team_id)
            assert {path.role for path in paths} == expected_roles[group_code]
            assert all(len(path.source_group_match_ids) == 3 for path in paths)
            assert all(
                path.final_match_id == matrix.final_paths[0].final_match_id for path in paths
            )

    semifinal_ids = {path.semifinal_match_id for path in matrix.final_paths}
    assert len(semifinal_ids) == 2
    assert all(
        path.final_match_id == matrix.final_paths[0].final_match_id
        for path in matrix.final_paths
    )


def test_role_assignment_rejects_same_team_in_multiple_knockout_roles() -> None:
    tournament = valid_tournament()
    matrix = build_qualification_path_matrix(tournament, generate_match_graph(tournament))
    group_a = next(group for group in tournament.groups if group.code == "A")
    group_b = next(group for group in tournament.groups if group.code == "B")

    valid_assignment = {
        QualificationRole.A1: group_a.team_ids[0],
        QualificationRole.A2: group_a.team_ids[1],
        QualificationRole.B1: group_b.team_ids[0],
        QualificationRole.B2: group_b.team_ids[1],
    }
    validate_role_assignment(matrix, valid_assignment)

    invalid_assignment = {**valid_assignment, QualificationRole.A2: group_a.team_ids[0]}
    with pytest.raises(InvalidQualificationAssignmentError, match="multiple qualification roles"):
        validate_role_assignment(matrix, invalid_assignment)


def test_role_assignment_rejects_team_from_the_wrong_group() -> None:
    tournament = valid_tournament()
    matrix = build_qualification_path_matrix(tournament, generate_match_graph(tournament))
    group_b = next(group for group in tournament.groups if group.code == "B")

    with pytest.raises(InvalidQualificationAssignmentError, match="does not belong to Group A"):
        validate_role_assignment(matrix, {QualificationRole.A1: group_b.team_ids[0]})


def test_semifinal_paths_are_independent_so_same_day_is_not_forbidden() -> None:
    tournament = valid_tournament()
    matches = generate_match_graph(tournament)
    matrix = build_qualification_path_matrix(tournament, matches)

    semifinal_ids = tuple(path.semifinal_match_id for path in matrix.final_paths)
    assert semifinal_ids[0] != semifinal_ids[1]
    semifinals = tuple(match for match in matches if match.stage is MatchStage.SEMIFINAL)
    assert all(not (set(match.dependency_ids) & set(semifinal_ids)) for match in semifinals)
