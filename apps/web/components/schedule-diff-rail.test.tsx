import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ScheduleDiffRail } from "./schedule-diff-rail";

describe("Schedule diff rail", () => {
  it("labels preserved, moved, added, removed and grounded metric deltas", () => {
    const markup = renderToStaticMarkup(<ScheduleDiffRail />);
    expect(markup).toContain("Preserved fixtures");
    expect(markup).toContain("Moved fixtures");
    expect(markup).toContain("Added fixtures");
    expect(markup).toContain("Removed fixtures");
    expect(markup).toContain("Weather risk");
    expect(markup).toContain("Solver evidence");
    expect(markup).toContain("Approve repaired schedule");
    expect(markup).toContain("Reject repair");
    expect(markup).toContain("Restore this version");
    expect(markup).toContain("history is never rewritten");
  });

  it("never exposes approval for an invalid repair", () => {
    const markup = renderToStaticMarkup(<ScheduleDiffRail validated={false} />);
    expect(markup).toContain("Repair validation failed");
    expect(markup).not.toContain("Approve repaired schedule");
    expect(markup).toContain("official baseline remains unchanged");
  });
});
