import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ScheduleGenerationProgress } from "./schedule-generation-progress";

describe("schedule generation progress", () => {
  it("names the real workflow stages and marks the active stage", () => {
    const markup = renderToStaticMarkup(
      <ScheduleGenerationProgress stage="solving" />,
    );

    expect(markup).toContain("Confirming constraints");
    expect(markup).toContain("Solving three profiles");
    expect(markup).toContain("Independently validating");
    expect(markup).toContain('aria-current="step"');
    expect(markup).toContain('aria-busy="true"');
  });

  it("shows an actionable failure without claiming completion", () => {
    const markup = renderToStaticMarkup(
      <ScheduleGenerationProgress
        stage="failed"
        error="Add more venue slots before generating."
      />,
    );

    expect(markup).toContain("Generation stopped safely");
    expect(markup).toContain("Add more venue slots before generating.");
    expect(markup).not.toContain("Schedules ready");
  });

  it("renders deterministic conflicts, concrete remedies, and an edit action", () => {
    const markup = renderToStaticMarkup(
      <ScheduleGenerationProgress
        stage="failed"
        error="Confirmed constraints and available slots are infeasible."
        evidence={["A 160-hour rest requirement cannot fit the tournament window."]}
        remedies={["Reduce minimum team rest or extend the tournament window."]}
      />,
    );

    expect(markup).toContain("Likely conflicts");
    expect(markup).toContain("160-hour rest requirement");
    expect(markup).toContain("Ways to resolve this");
    expect(markup).toContain("Reduce minimum team rest");
    expect(markup).toContain('href="#format-teams"');
  });
});
