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
});
