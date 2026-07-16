from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from app.domain.common import DomainModel
from app.domain.schedules import ScheduleProfile
from app.scheduling.profiles import GeneratedProfileOption

METRIC_VERSION = "schedule-metrics/v1"


class ProfileComparison(DomainModel):
    metric_version: str
    options: tuple[GeneratedProfileOption, ...]
    identical_solution_groups: tuple[tuple[ScheduleProfile, ...], ...]


def compare_profile_options(options: Sequence[GeneratedProfileOption]) -> ProfileComparison:
    if not options:
        raise ValueError("comparison requires at least one validated option")
    if not all(option.validation_report.valid for option in options):
        raise ValueError("comparison cannot include an invalid option")
    config_versions = {(option.config_version, option.config_checksum) for option in options}
    if len(config_versions) != 1:
        raise ValueError("comparison options must share one configuration version")

    profiles_by_digest: dict[str, list[ScheduleProfile]] = defaultdict(list)
    for option in options:
        profiles_by_digest[option.validation_report.placement_digest].append(option.profile)
    identical_groups = tuple(
        tuple(profiles) for profiles in profiles_by_digest.values() if len(profiles) > 1
    )
    return ProfileComparison(
        metric_version=METRIC_VERSION,
        options=tuple(options),
        identical_solution_groups=identical_groups,
    )
