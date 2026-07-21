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
    expect(markup).toContain("Edit teams and groups");
    expect(markup).toContain("Group A");
    expect(markup).toContain("Group B");
    expect((markup.match(/Team display name/g) ?? [])).toHaveLength(8);
    expect(markup).toContain("Swap group with");
    expect(markup).not.toContain("Match duration override");
    expect(markup).toContain("Venue display name");
    expect(markup).toContain("City, country, area, or postal code");
    expect(markup).toContain("Use manual coordinates");
    expect(markup).toContain("Enter a decimal from -90 to 90");
    expect(markup).toContain("Enter a decimal from -180 to 180");
    expect(markup).toContain("Shared tournament timezone");
    expect(markup).toContain("Weekday start time");
    expect(markup).toContain("Weekend start times");
    expect(markup).toContain("Venue blackout date");
    expect(markup).toContain("Constraint Ledger");
    expect(markup).toContain("System invariant");
    expect(markup).toContain("No additional minimum rest configured");
    expect(markup).toContain("Enter a whole number from 0 to 168 hours");
    expect(markup).toContain("Soft preference");
    expect((markup.match(/class="ledger-rule-status/g) ?? [])).toHaveLength(5);
    expect((markup.match(/class="ledger-rule-content/g) ?? [])).toHaveLength(5);
    expect(markup).toContain("Confirm and generate schedules");
    expect(markup).toContain("Confirmation pending");
    expect(markup).toContain('aria-live="polite"');
  });

  it("gives a clear stale-revision recovery action", () => {
    const markup = renderToStaticMarkup(<GuidedSetup conflict="stale" />);

    expect(markup).toContain("Tournament setup changed in another request");
    expect(markup).toContain("Reload latest setup");
  });
});
