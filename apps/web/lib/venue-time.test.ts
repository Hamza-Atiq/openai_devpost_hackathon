import { describe, expect, it } from "vitest";

import { formatVenueDateTime, formatVenueTime } from "./venue-time";

describe("venue-local time formatting", () => {
  it("formats an instant in the supplied IANA timezone rather than the browser timezone", () => {
    const instant = "2026-07-22T02:00:00Z";

    expect(formatVenueDateTime(instant, "Asia/Kuala_Lumpur")).toBe("22 Jul, 10:00");
    expect(formatVenueTime(instant, "Asia/Kuala_Lumpur")).toBe("10:00");
  });

  it("does not add seconds to judge-facing fixture times", () => {
    expect(formatVenueDateTime("2026-07-22T10:00:00+08:00", "Asia/Kuala_Lumpur"))
      .not.toContain(":00:00");
  });
});
