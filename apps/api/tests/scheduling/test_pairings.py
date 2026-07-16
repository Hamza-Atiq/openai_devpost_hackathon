from __future__ import annotations

from itertools import combinations

from app.domain.matches import MatchStage
from app.domain.teams import Team
from app.domain.tournament import TournamentConfig
from app.scheduling.pairings import generate_match_graph
from tests.domain.factories import valid_tournament


def test_generates_all_unique_group_pairings_and_fixed_knockout_graph() -> None:
    tournament = valid_tournament()

    matches = generate_match_graph(tournament)

    assert len(matches) == 15
    assert len({match.id for match in matches}) == 15
    assert [match.sequence for match in matches] == list(range(1, 16))

    group_matches = tuple(match for match in matches if match.stage is MatchStage.GROUP)
    semifinals = tuple(match for match in matches if match.stage is MatchStage.SEMIFINAL)
    final = tuple(match for match in matches if match.stage is MatchStage.FINAL)
    assert len(group_matches) == 12
    assert len(semifinals) == 2
    assert len(final) == 1

    for group in tournament.groups:
        expected_pairs = {
            frozenset((str(team_a), str(team_b)))
            for team_a, team_b in combinations(group.team_ids, 2)
        }
        actual_pairs = {
            frozenset((match.participant_a, match.participant_b))
            for match in group_matches
            if match.participant_a in {str(team_id) for team_id in group.team_ids}
        }
        assert actual_pairs == expected_pairs

    assert [(match.participant_a, match.participant_b) for match in semifinals] == [
        ("A1", "B2"),
        ("B1", "A2"),
    ]
    group_match_ids = {match.id for match in group_matches}
    assert all(set(semifinal.dependency_ids) == group_match_ids for semifinal in semifinals)
    assert set(final[0].dependency_ids) == {match.id for match in semifinals}
    assert (final[0].participant_a, final[0].participant_b) == ("SF1 Winner", "SF2 Winner")


def test_match_ids_are_stable_when_display_names_and_input_order_change() -> None:
    tournament = valid_tournament()
    renamed_teams = tuple(
        Team(id=team.id, display_name=f"Renamed {index}", group_id=team.group_id)
        for index, team in enumerate(reversed(tournament.teams), start=1)
    )
    renamed = TournamentConfig.model_validate(
        {
            **tournament.model_dump(),
            "name": "Renamed tournament",
            "teams": renamed_teams,
            "groups": tuple(reversed(tournament.groups)),
        }
    )

    original_graph = generate_match_graph(tournament)
    renamed_graph = generate_match_graph(renamed)

    assert renamed_graph == original_graph
    assert all(match.id.version == 7 for match in original_graph)
