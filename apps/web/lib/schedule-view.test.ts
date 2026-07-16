import { describe, expect, it } from "vitest";

import { groupFixturesByLocalDate, type ScheduleFixtureView } from "./schedule-view";

const fixture = (id: string, startsAt: string): ScheduleFixtureView => ({
  id,
  stage: "group",
  home: "Team A",
  away: "Team B",
  venue: "Harbour Oval",
  startsAt,
  timezone: "Asia/Karachi",
  validation: "valid",
  change: "preserved",
});

describe("schedule view model", () => {
  it("sorts fixtures chronologically and groups them by venue-local date", () => {
    const groups = groupFixturesByLocalDate([
      fixture("late", "2026-09-08T18:00:00+05:00"),
      fixture("early", "2026-09-07T10:00:00+05:00"),
    ]);

    expect(groups.map((group) => group.date)).toEqual(["2026-09-07", "2026-09-08"]);
    expect(groups[0].fixtures[0].id).toBe("early");
  });
});
