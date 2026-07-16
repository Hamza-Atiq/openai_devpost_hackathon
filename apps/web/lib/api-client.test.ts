import { describe, expect, it, vi } from "vitest";

import { CrickOpsApiClient } from "./api-client";

describe("CrickOpsApiClient", () => {
  it("creates a sample workspace with private same-origin credentials", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ workspace_id: "workspace-1", tournament: { name: "Global Cup" } }),
        { status: 201, headers: { "Content-Type": "application/json" } },
      ),
    );

    const result = await new CrickOpsApiClient(fetcher).createWorkspace(
      "global-community-cup",
    );

    expect(result.workspace_id).toBe("workspace-1");
    expect(fetcher).toHaveBeenCalledWith(
      "/api/v1/workspaces",
      expect.objectContaining({
        method: "POST",
        credentials: "same-origin",
        cache: "no-store",
      }),
    );
  });

  it("preserves the typed Problem Details contract", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          type: "https://crickops.dev/problems/invalid_sample",
          title: "Invalid sample",
          status: 422,
          code: "invalid_sample",
          detail: "Unknown sample",
          correlation_id: "correlation-1",
          retryable: false,
        }),
        { status: 422, headers: { "Content-Type": "application/problem+json" } },
      ),
    );

    await expect(
      new CrickOpsApiClient(fetcher).createWorkspace("missing"),
    ).rejects.toHaveProperty("code", "invalid_sample");
  });
});
