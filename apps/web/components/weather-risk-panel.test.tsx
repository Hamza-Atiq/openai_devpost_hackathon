import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { WeatherRiskPanel } from "./weather-risk-panel";

const fixtures = [
  { id: "G01", label: "Azure XI vs Cedar XI", venue: "Riverside", startsAt: "2026-07-22T10:00:00+08:00", risk: 78 },
];

function panel(overrides: Partial<React.ComponentProps<typeof WeatherRiskPanel>> = {}) {
  return <WeatherRiskPanel coverage={100} issuedAt="19 Jul 2026, 14:00 MYT" stale={false} provider="Open-Meteo" fixtures={fixtures} allocationMinutes={240} {...overrides} />;
}

describe("Weather risk panel", () => {
  it("shows full coverage, freshness, interval, and attribution", () => {
    const markup = renderToStaticMarkup(panel());
    expect(markup).toContain("100.0% forecast coverage");
    expect(markup).toContain("Issued");
    expect(markup).toContain("4-hour allocation block");
    expect(markup).toContain("Weather data by Open-Meteo");
    expect(markup).toContain("planning guidance");
  });

  it.each([
    [60, "Partial forecast coverage"],
    [0, "No forecast coverage"],
  ])("explains incomplete coverage without calling unknown slots safe", (coverage, label) => {
    const markup = renderToStaticMarkup(panel({ coverage, fixtures: [{ ...fixtures[0], risk: null }] }));
    expect(markup).toContain(label);
    expect(markup).toContain("Unknown");
    expect(markup).not.toContain("Safe");
  });

  it("labels stale weather explicitly and does not rely on color", () => {
    const markup = renderToStaticMarkup(panel({ stale: true }));
    expect(markup).toContain("Forecast is stale");
    expect(markup).toContain("High risk");
    expect(markup).toContain("▲");
  });
});
