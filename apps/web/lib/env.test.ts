import { describe, expect, it } from "vitest";

import { parsePublicEnv, serializePublicEnv } from "./env";

describe("public environment boundary", () => {
  it("uses a same-origin API default and accepts valid public metadata", () => {
    expect(parsePublicEnv({})).toEqual({ apiBaseUrl: "/api/v1" });
    expect(
      parsePublicEnv({
        NEXT_PUBLIC_API_BASE_URL: "https://preview.crickops.example/api/v1",
        NEXT_PUBLIC_BUILD_SHA: "abcdef1",
      }),
    ).toEqual({
      apiBaseUrl: "https://preview.crickops.example/api/v1",
      buildSha: "abcdef1",
    });
  });

  it.each([
    { NEXT_PUBLIC_API_BASE_URL: "javascript:alert(1)" },
    { NEXT_PUBLIC_API_BASE_URL: "//untrusted.example/api/v1" },
    { NEXT_PUBLIC_BUILD_SHA: "not a commit" },
  ])("rejects malformed public values", (environment) => {
    expect(() => parsePublicEnv(environment)).toThrow(/public environment/i);
  });

  it.each(["OPENAI_API_KEY", "DATABASE_URL", "NEXT_PUBLIC_OPENAI_API_KEY"])(
    "rejects non-allowlisted name %s",
    (name) => {
      expect(() => parsePublicEnv({ [name]: "server-only" })).toThrow(
        /unknown public environment variable/i,
      );
    },
  );

  it("serializes only the allowlisted public schema", () => {
    const serialized = serializePublicEnv(
      parsePublicEnv({ NEXT_PUBLIC_API_BASE_URL: "/api/v1" }),
    );

    expect(serialized).toBe('{"apiBaseUrl":"/api/v1"}');
    expect(serialized).not.toContain("server-only");
  });
});
