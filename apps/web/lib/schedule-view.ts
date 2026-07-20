import { formatVenueTime } from "./venue-time";

export type FixtureStage = "group" | "semifinal" | "final";
export type FixtureChange = "preserved" | "changed" | "new";

export type ScheduleFixtureView = {
  id: string;
  stage: FixtureStage;
  home: string;
  away: string;
  venue: string;
  startsAt: string;
  timezone: string;
  validation: "valid" | "invalid";
  change: FixtureChange;
};

export type LocalDateGroup = { date: string; fixtures: ScheduleFixtureView[] };

export function groupFixturesByLocalDate(fixtures: ScheduleFixtureView[]): LocalDateGroup[] {
  const sorted = [...fixtures].sort((left, right) => left.startsAt.localeCompare(right.startsAt));
  return sorted.reduce<LocalDateGroup[]>((groups, fixture) => {
    const date = fixture.startsAt.slice(0, 10);
    const current = groups.at(-1);
    if (current?.date === date) current.fixtures.push(fixture);
    else groups.push({ date, fixtures: [fixture] });
    return groups;
  }, []);
}

export function localTimeLabel(startsAt: string, timezone: string): string {
  return formatVenueTime(startsAt, timezone);
}
