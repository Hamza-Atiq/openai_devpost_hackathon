import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { GuidedSetup } from "./guided-setup";

describe("guided tournament setup", () => {
  it("renders presets, venue confirmation, slot patterns, and the Constraint Ledger", () => {
    const markup = renderToStaticMarkup(<GuidedSetup />);

    expect(markup).toContain("T10");
    expect(markup).toContain("120-minute operational venue allocation");
    expect(markup).toContain("T20");
    expect(markup).toContain("240-minute operational venue allocation");
    expect(markup).not.toContain("Match duration override");
    expect(markup).toContain("Venue display name");
    expect(markup).toContain("City, country, area, or postal code");
    expect(markup).toContain("Use manual coordinates");
    expect(markup).toContain("Shared tournament timezone");
    expect(markup).toContain("Weekday start time");
    expect(markup).toContain("Weekend start times");
    expect(markup).toContain("Venue blackout date");
    expect(markup).toContain("Constraint Ledger");
    expect(markup).toContain("Hard rule");
    expect(markup).toContain("Preferred");
    expect(markup).toContain("Confirm hard constraints");
  });

  it("gives a clear stale-revision recovery action", () => {
    const markup = renderToStaticMarkup(<GuidedSetup conflict="stale" />);

    expect(markup).toContain("Tournament setup changed in another request");
    expect(markup).toContain("Reload latest setup");
  });
});
