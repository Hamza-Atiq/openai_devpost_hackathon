import { describe, expect, it } from "vitest";

import { parseStartTimesInput, startTimesInputValue } from "./setup-contract";

describe("setup start-time controls", () => {
  it("shows every persisted time and parses the organizer's complete list", () => {
    expect(startTimesInputValue(["10:00:00", "15:00:00"])).toBe("10:00, 15:00");
    expect(parseStartTimesInput("10:00, 15:00")).toEqual(["10:00", "15:00"]);
  });
});
