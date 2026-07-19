import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { WeatherWorkspaceLive } from "./weather-workspace-live";

describe("Weather workspace", () => {
  it("renders the saved server mode instead of resetting to a component default", () => {
    const markup = renderToStaticMarkup(
      <WeatherWorkspaceLive
        initialStatus={{ mode: "live", quality: "complete", coverage: 100 }}
      />,
    );

    expect(markup).toContain("Live forecast mode");
    expect(markup).not.toContain("Deterministic demo mode");
  });

  it("explains when tournament edits invalidate prior weather evidence", () => {
    const markup = renderToStaticMarkup(
      <WeatherWorkspaceLive
        initialStatus={{
          mode: "live",
          quality: "refresh_required",
          invalidation_reason: "Tournament slots changed.",
        }}
      />,
    );

    expect(markup).toContain("Weather refresh required");
    expect(markup).toContain("Tournament slots changed.");
  });
});
