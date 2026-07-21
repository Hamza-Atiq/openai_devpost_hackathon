import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { metricBarWidth, ProfileComparison, type ComparisonOption } from "./profile-comparison";

const invalidOption: ComparisonOption = {
  profile: "balanced",
  label: "Balanced",
  validationValid: false,
  metrics: {
    weatherRisk: 42,
    weatherCoverage: 80,
    groupRestFairness: 88,
    potentialKnockoutRest: 82,
    venueBalance: 91,
    slotBalance: 86,
    preferenceSatisfaction: 90,
  },
  softViolations: ["Prime-time preference missed for G07"],
};

describe("Profile comparison", () => {
  it("inverts lower-is-better weather bars", () => {
    expect(metricBarWidth("weatherRisk", 20)).toBe(80);
    expect(metricBarWidth("weatherRisk", 70)).toBe(30);
    expect(metricBarWidth("groupRestFairness", 70)).toBe(70);
  });
  it("renders three aligned validated options without inventing a recommendation", () => {
    const markup = renderToStaticMarkup(<ProfileComparison />);

    expect(markup).toContain("Balanced");
    expect(markup).toContain("Weather-first");
    expect(markup).toContain("Fairness-first");
    expect(markup).toContain("Independent validation passed");
    expect(markup).toContain("Weather coverage");
    expect(markup).toContain("Potential knockout rest");
    expect(markup).toContain("Soft-constraint notes");
    expect(markup).not.toContain("Recommended");
    expect(markup).not.toContain("Custom schedule</h2>");
  });

  it("explains identical schedules and prevents selection of invalid output", () => {
    const markup = renderToStaticMarkup(
      <ProfileComparison
        options={[invalidOption]}
        identicalProfiles={["Balanced", "Fairness-first"]}
      />,
    );

    expect(markup).toContain("Same fixture placement");
    expect(markup).toContain("Balanced and Fairness-first produced the same fixture placement");
    expect(markup).toContain("Independent validation failed");
    expect(markup).toContain("disabled");
    expect(markup).toContain("Prime-time preference missed for G07");
  });

  it("shows Custom controls only when explicitly requested", () => {
    const hidden = renderToStaticMarkup(<ProfileComparison />);
    const visible = renderToStaticMarkup(<ProfileComparison showCustom />);

    expect(hidden).not.toContain("Custom priorities</legend>");
    expect(visible).toContain("Custom priorities</legend>");
    expect(visible).toContain("Generate custom schedule");
    expect(visible).toContain("Minimize weather risk");
  });
});
