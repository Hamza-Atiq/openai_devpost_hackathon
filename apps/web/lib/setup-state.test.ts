import { describe, expect, it } from "vitest";

import {
  allocationMinutes,
  buildVenueLocation,
  validateSharedTimezone,
  type SetupVenue,
} from "./setup-state";

const venue = (overrides: Partial<SetupVenue> = {}): SetupVenue => ({
  id: "venue-1",
  name: "Harbour Oval",
  locationQuery: "Auckland, New Zealand",
  latitude: -36.8485,
  longitude: 174.7633,
  timezone: "Pacific/Auckland",
  locationConfirmed: true,
  blackoutDates: [],
  ...overrides,
});

describe("guided setup rules", () => {
  it("maps the two supported presets to operational allocation blocks", () => {
    expect(allocationMinutes("T10")).toBe(120);
    expect(allocationMinutes("T20")).toBe(240);
  });

  it("accepts confirmed manual coordinates separately from the venue name", () => {
    const location = buildVenueLocation({
      locationQuery: "Lahore, Pakistan",
      latitude: 31.5204,
      longitude: 74.3587,
      timezone: "Asia/Karachi",
    });

    expect(location).toEqual({
      locationQuery: "Lahore, Pakistan",
      latitude: 31.5204,
      longitude: 74.3587,
      timezone: "Asia/Karachi",
      locationConfirmed: true,
    });
  });

  it("rejects a venue pair with different IANA timezones", () => {
    const result = validateSharedTimezone([
      venue(),
      venue({ id: "venue-2", timezone: "Australia/Sydney" }),
    ]);

    expect(result).toEqual({
      valid: false,
      message: "Version 1 requires both venues to use the same IANA timezone.",
    });
  });

  it("preserves organizer-entered blackout dates", () => {
    const configured = venue({ blackoutDates: ["2026-09-12"] });

    expect(configured.blackoutDates).toEqual(["2026-09-12"]);
  });
});
