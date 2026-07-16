import { describe, expect, it } from "vitest";

import { productName } from "./project";

describe("project scaffold", () => {
  it("uses the approved product name", () => {
    expect(productName).toBe("CrickOps AI");
  });
});
