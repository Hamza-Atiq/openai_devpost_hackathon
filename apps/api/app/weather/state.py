from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping

from app.domain.tournament import TournamentConfig


def weather_slot_digest(tournament: TournamentConfig) -> str:
    payload = {
        "allocation_minutes": tournament.allocation_minutes,
        "venues": [
            {
                "id": str(venue.id),
                "latitude": venue.latitude,
                "longitude": venue.longitude,
                "iana_time_zone": venue.iana_time_zone,
            }
            for venue in tournament.venues
        ],
        "slots": [
            {
                "id": str(slot.id),
                "venue_id": str(slot.venue_id),
                "starts_at_utc": slot.starts_at_utc.isoformat(),
                "availability": slot.availability,
            }
            for slot in tournament.slots
        ],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


def bind_weather_state(
    weather: Mapping[str, object], tournament: TournamentConfig
) -> dict[str, object]:
    return {
        **weather,
        "tournament_revision": tournament.revision,
        "slot_digest": weather_slot_digest(tournament),
    }


def invalidate_weather(
    previous: Mapping[str, object], tournament: TournamentConfig
) -> dict[str, object]:
    return {
        "mode": previous.get("mode", "live"),
        "quality": "refresh_required",
        "demo_mode_available": previous.get("demo_mode_available", True),
        "scenario_id": previous.get("scenario_id"),
        "provider": previous.get("provider"),
        "coverage": 0.0,
        "slot_risks": {},
        "slot_details": {},
        "tournament_revision": tournament.revision,
        "slot_digest": weather_slot_digest(tournament),
        "invalidation_reason": (
            "Tournament dates, format, venues, or available slots changed. "
            "Refresh weather before relying on risk guidance."
        ),
        "guidance": "Weather risk is planning guidance only.",
    }
