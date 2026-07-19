from __future__ import annotations

from datetime import date

from app.domain.samples import available_samples, load_sample


def test_exactly_two_golden_samples_load_as_t20() -> None:
    sample_ids = available_samples()

    assert sample_ids == ("global-community-cup", "pakistan-community-cup")
    for sample_id in sample_ids:
        tournament = load_sample(sample_id)
        assert tournament.match_format_preset == "T20"
        assert tournament.allocation_minutes == 240
        assert len(tournament.teams) == 8
        assert len(tournament.groups) == 2
        assert len(tournament.venues) == 2


def test_samples_have_immediately_usable_capacity() -> None:
    for sample_id in available_samples():
        tournament = load_sample(sample_id)
        usable = [
            slot
            for slot in tournament.slots
            if slot.availability == "available"
            and (slot.ends_at_utc - slot.starts_at_utc).total_seconds() >= 240 * 60
        ]
        assert len(usable) >= 15


def test_samples_roll_into_forecast_horizon_with_real_repair_slack() -> None:
    reference = date(2026, 7, 19)

    for sample_id in available_samples():
        tournament = load_sample(sample_id, reference_date=reference)

        assert tournament.start_date == date(2026, 7, 22)
        assert tournament.end_date == date(2026, 7, 31)
        assert (tournament.end_date - reference).days <= 16
        assert len(tournament.slots) == 28
        assert len({(slot.venue_id, slot.starts_at_utc) for slot in tournament.slots}) == 28


def test_sample_names_do_not_use_known_team_or_tournament_brands() -> None:
    prohibited = {
        "ipl",
        "psl",
        "big bash",
        "karachi kings",
        "lahore qalandars",
        "islamabad united",
        "multan sultans",
        "peshawar zalmi",
        "quetta gladiators",
        "mumbai indians",
        "chennai super kings",
    }

    for sample_id in available_samples():
        tournament = load_sample(sample_id)
        names = [tournament.name]
        names.extend(team.display_name for team in tournament.teams)
        names.extend(venue.display_name for venue in tournament.venues)
        normalized = " | ".join(names).lower()
        assert not any(term in normalized for term in prohibited)
