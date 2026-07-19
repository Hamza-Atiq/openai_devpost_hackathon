import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ScheduleRail } from "./schedule-rail";

const fixtures = [
  { id: "G01", stage: "group" as const, home: "Falcons", away: "Royals", venue: "Ground One", startsAt: "2026-09-07T10:00:00+05:00", timezone: "Asia/Karachi", validation: "valid" as const, change: "preserved" as const },
  { id: "SF1", stage: "semifinal" as const, home: "Group A Winner", away: "Group B Runner-up", venue: "Ground One", startsAt: "2026-09-15T10:00:00+05:00", timezone: "Asia/Karachi", validation: "valid" as const, change: "changed" as const },
  { id: "F1", stage: "final" as const, home: "Semifinal 1 Winner", away: "Semifinal 2 Winner", venue: "Ground One", startsAt: "2026-09-18T18:00:00+05:00", timezone: "Asia/Karachi", validation: "valid" as const, change: "new" as const },
];

describe("Schedule Rail", () => {
  it("renders chronology, local timezone, validation, stage gates, and official versioning", () => {
    const markup = renderToStaticMarkup(<ScheduleRail status="official" version={2} fixtures={fixtures} />);

    expect(markup).toContain("Official workspace schedule");
    expect(markup).toContain("Version 2");
    expect(markup).toContain("Independently validated");
    expect(markup).toContain("Asia/Karachi");
    expect(markup).toContain("Group stage complete");
    expect(markup).toContain("Semifinals complete");
    expect(markup).toContain("Version 2 · official");
    expect(markup).not.toContain("Publish externally");
  });

  it("labels a repaired draft and exposes explicit approval without color-only meaning", () => {
    const markup = renderToStaticMarkup(<ScheduleRail status="draft" version={3} repair fixtures={fixtures} />);

    expect(markup).toContain("Draft repair — not official");
    expect(markup).toContain("Preserved fixture");
    expect(markup).toContain("Changed fixture");
    expect(markup).toContain("Approve schedule");
    expect(markup).toContain("Keep Version 2 official");
  });
});
