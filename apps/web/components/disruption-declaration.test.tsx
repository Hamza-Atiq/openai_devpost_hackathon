import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { DisruptionDeclaration } from "./disruption-declaration";

const slots = [
  {
    id: "slot-official-1",
    fixture: "G01 · Azure XI vs Cedar XI",
    venue: "Riverside Community Ground",
    localTime: "22 Jul, 10:00 · Asia/Kuala_Lumpur",
  },
];

describe("Disruption declaration", () => {
  it("offers only rain and venue unavailability against the official baseline", () => {
    const markup = renderToStaticMarkup(<DisruptionDeclaration officialVersion={2} slots={slots} />);
    expect(markup).toContain("Official Version 2 baseline");
    expect(markup).toContain("Rain disruption");
    expect(markup).toContain("Venue unavailable");
    expect(markup).not.toContain("Team withdrawal");
    expect(markup).toContain("Affected fixtures");
  });

  it("explains that declaration creates a draft repair, not an immediate schedule change", () => {
    const markup = renderToStaticMarkup(<DisruptionDeclaration officialVersion={1} slots={slots} />);
    expect(markup).toContain("Generate a repaired draft");
    expect(markup).toContain("official schedule remains unchanged");
    expect(markup).toContain("Select at least one unavailable venue-time slot from the official schedule");
  });
});
