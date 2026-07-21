import { describe, expect, it } from "vitest";

import { parseCoordinateInput } from "./coordinate-input";

describe("coordinate input parsing", () => {
  it("accepts complete decimal coordinates", () => {
    expect(parseCoordinateInput("3.140", "latitude")).toEqual({ value: 3.14 });
    expect(parseCoordinateInput("-74.3587", "longitude")).toEqual({ value: -74.3587 });
  });

  it("keeps incomplete or invalid text out of authoritative setup state", () => {
    expect(parseCoordinateInput("3.", "latitude")).toHaveProperty("error");
    expect(parseCoordinateInput("letters", "longitude")).toHaveProperty("error");
    expect(parseCoordinateInput("3140", "latitude")).toHaveProperty("error");
  });
});
