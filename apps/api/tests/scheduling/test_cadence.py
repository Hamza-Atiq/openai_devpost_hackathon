from app.api.schedules import cadence_penalty


def test_cadence_targets_spread_fixture_sequence_across_available_starts() -> None:
    assert cadence_penalty(sequence=1, fixture_count=15, rank=0, last_rank=20) == 0
    assert cadence_penalty(sequence=8, fixture_count=15, rank=10, last_rank=20) == 0
    assert cadence_penalty(sequence=15, fixture_count=15, rank=20, last_rank=20) == 0


def test_cadence_penalizes_packed_groups_and_artificial_knockout_gap() -> None:
    early_group_penalty = cadence_penalty(
        sequence=12, fixture_count=15, rank=5, last_rank=20
    )
    late_semifinal_penalty = cadence_penalty(
        sequence=13, fixture_count=15, rank=20, last_rank=20
    )

    assert early_group_penalty > 50
    assert late_semifinal_penalty > 10
