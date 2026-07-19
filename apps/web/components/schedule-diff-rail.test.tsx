import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ScheduleDiffRail } from "./schedule-diff-rail";

describe("Schedule diff rail", () => {
  it("labels preserved, moved, added, removed and grounded metric deltas", () => {
    const markup = renderToStaticMarkup(<ScheduleDiffRail validated unchanged={[{ id: "G01", fixture: "Azure XI vs Cedar XI", detail: "22 Jul · Riverside" }]} moved={[{ id: "G07", fixture: "Ember XI vs Harbour XI", detail: "22 Jul → 23 Jul" }]} added={[]} removed={[]} metricDeltas={{ weather_risk: -4.2 }} versions={[{ id: "version-1", number: 1, label: "Official schedule" }]} />);
    expect(markup).toContain("Preserved fixtures");
    expect(markup).toContain("Moved fixtures");
    expect(markup).toContain("Added fixtures");
    expect(markup).toContain("Removed fixtures");
    expect(markup).toContain("Weather risk");
    expect(markup).toContain("Weather risk improved by 4.2 points");
    expect(markup).toContain("Solver evidence");
    expect(markup).toContain("Approve repaired schedule");
    expect(markup).toContain("Reject repair");
    expect(markup).toContain("Restore this version");
    expect(markup).toContain("history is never rewritten");
  });

  it("never exposes approval for an invalid repair", () => {
    const markup = renderToStaticMarkup(<ScheduleDiffRail validated={false} unchanged={[]} moved={[]} added={[]} removed={[]} metricDeltas={{}} />);
    expect(markup).toContain("Repair validation failed");
    expect(markup).not.toContain("Approve repaired schedule");
    expect(markup).toContain("official baseline remains unchanged");
  });
});
