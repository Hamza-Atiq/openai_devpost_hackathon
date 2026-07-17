import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { WeatherRiskPanel } from "./weather-risk-panel";

describe("Weather risk panel", () => {
  it("shows full coverage, freshness, interval, and attribution", () => {
    const markup = renderToStaticMarkup(<WeatherRiskPanel />);
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
    const markup = renderToStaticMarkup(<WeatherRiskPanel coverage={coverage} fixtures={[{ id: "G01", label: "Falcons vs Lions", venue: "Riverside", startsAt: "2026-09-07T10:00:00+05:00", risk: null }]} />);
    expect(markup).toContain(label);
    expect(markup).toContain("Unknown");
    expect(markup).not.toContain("Safe");
  });

  it("labels stale weather explicitly and does not rely on color", () => {
    const markup = renderToStaticMarkup(<WeatherRiskPanel stale />);
    expect(markup).toContain("Forecast is stale");
    expect(markup).toContain("High risk");
    expect(markup).toContain("▲");
  });
});
