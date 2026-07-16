import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ScheduleRail } from "./schedule-rail";

describe("Schedule Rail", () => {
  it("renders chronology, local timezone, validation, stage gates, and official versioning", () => {
    const markup = renderToStaticMarkup(<ScheduleRail status="official" version={2} />);

    expect(markup).toContain("Official workspace schedule");
    expect(markup).toContain("Version 2");
    expect(markup).toContain("Independently validated");
    expect(markup).toContain("Asia/Karachi");
    expect(markup).toContain("Group stage complete");
    expect(markup).toContain("Semifinals complete");
    expect(markup).toContain("Schedule version");
    expect(markup).not.toContain("Publish externally");
  });

  it("labels a repaired draft and exposes explicit approval without color-only meaning", () => {
    const markup = renderToStaticMarkup(<ScheduleRail status="draft" version={3} repair />);

    expect(markup).toContain("Draft repair — not official");
    expect(markup).toContain("Preserved fixture");
    expect(markup).toContain("Changed fixture");
    expect(markup).toContain("Approve schedule");
    expect(markup).toContain("Keep Version 2 official");
  });
});
