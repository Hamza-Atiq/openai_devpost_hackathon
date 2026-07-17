import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { DisruptionDeclaration } from "./disruption-declaration";

describe("Disruption declaration", () => {
  it("offers only rain and venue unavailability against the official baseline", () => {
    const markup = renderToStaticMarkup(<DisruptionDeclaration officialVersion={2} />);
    expect(markup).toContain("Official Version 2 baseline");
    expect(markup).toContain("Rain disruption");
    expect(markup).toContain("Venue unavailable");
    expect(markup).not.toContain("Team withdrawal");
    expect(markup).toContain("Affected fixtures");
  });

  it("explains that declaration creates a draft repair, not an immediate schedule change", () => {
    const markup = renderToStaticMarkup(<DisruptionDeclaration officialVersion={1} />);
    expect(markup).toContain("Generate a repaired draft");
    expect(markup).toContain("official schedule remains unchanged");
    expect(markup).toContain("Select at least one unavailable venue-time slot");
  });
});
