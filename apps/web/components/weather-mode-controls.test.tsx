import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { WeatherModeControls } from "./weather-mode-controls";

describe("Weather mode controls", () => {
  it("keeps the active mode explicit and explains provider failure", () => {
    const markup = renderToStaticMarkup(<WeatherModeControls initialMode="live" initialProviderUnavailable />);
    expect(markup).toContain("Live forecast mode");
    expect(markup).toContain("Live provider unavailable");
    expect(markup).toContain("Deterministic mode is available");
    expect(markup).not.toContain("silently");
  });

  it("requires a separate confirmation before a proposed threshold is hard", () => {
    const markup = renderToStaticMarkup(<WeatherModeControls initialProposal={{ metric: "precipitation_probability", value: 70 }} />);
    expect(markup).toContain("Proposed · still advisory");
    expect(markup).toContain("Confirm as hard constraint");
    expect(markup).toContain("disabled");
    expect(markup).toContain("organizer remains responsible");
  });
});
