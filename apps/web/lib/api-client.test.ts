import { afterEach, describe, expect, it, vi } from "vitest";

import { CrickOpsApiClient } from "./api-client";

describe("CrickOpsApiClient", () => {
  afterEach(() => vi.unstubAllGlobals());

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

  it("confirms constraints and checks persisted readiness through the API", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ status: "ready_to_schedule", revision: 4 }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ready: true, violations: [] }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );

    const result = await new CrickOpsApiClient(fetcher).confirmSetup({
      confirmation: true,
      expected_revision: 3,
      selection: { match_format_preset: "T20", allocation_minutes: 240 },
    });

    expect(result.ready).toBe(true);
    expect(fetcher).toHaveBeenNthCalledWith(
      1,
      "/api/v1/constraints/confirm",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
    expect(fetcher).toHaveBeenNthCalledWith(
      2,
      "/api/v1/tournament/precheck",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
  });

  it("generates Custom only on request and retrieves the validated comparison", async () => {
    vi.stubGlobal("crypto", { randomUUID: () => "run-key-1" });
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ run_id: "run-1", status: "accepted" }), {
          status: 202,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ run_id: "run-1", metric_version: "schedule-metrics/v1", options: [], identical_solution_groups: [] }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );

    await new CrickOpsApiClient(fetcher).generateScheduleOptions({
      weather_coverage: 45,
      rest: 30,
      venue_balance: 10,
      slot_balance: 5,
      organizer_preferences: 5,
      audience_timing: 5,
    });

    expect(fetcher).toHaveBeenNthCalledWith(
      1,
      "/api/v1/schedule-runs",
      expect.objectContaining({
        method: "POST",
        body: expect.stringContaining('"custom"'),
        headers: expect.objectContaining({ "Idempotency-Key": "run-key-1" }),
      }),
    );
    expect(fetcher).toHaveBeenNthCalledWith(
      2,
      "/api/v1/schedule-comparisons?run_id=run-1",
      expect.objectContaining({ method: "GET", credentials: "same-origin" }),
    );
  });

  it("loads organizer-safe audit events and records structured workspace feedback", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ items: [], next_cursor: null, has_more: false }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ draft_id: "draft-1", reason: "venue_preference" }), {
          status: 201,
          headers: { "Content-Type": "application/json" },
        }),
      );
    const client = new CrickOpsApiClient(fetcher);

    await client.getAuditEvents();
    await client.recordScheduleFeedback("draft-1", "venue_preference", "Prefer Riverside Oval.");

    expect(fetcher).toHaveBeenNthCalledWith(
      1,
      "/api/v1/audit-events",
      expect.objectContaining({ method: "GET", credentials: "same-origin" }),
    );
    expect(fetcher).toHaveBeenNthCalledWith(
      2,
      "/api/v1/schedule-drafts/draft-1/feedback",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ reason: "venue_preference", note: "Prefer Riverside Oval." }),
      }),
    );
  });

  it("sends the double-submit CSRF token on workspace mutations", async () => {
    vi.stubGlobal("document", {
      cookie: "theme=dark; __Host-crickops_csrf=csrf-token-123; locale=en",
    });
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ status: "ready_to_schedule", revision: 4 }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ready: true, violations: [] }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );

    await new CrickOpsApiClient(fetcher).confirmSetup({
      confirmation: true,
      expected_revision: 3,
      selection: { match_format_preset: "T20", allocation_minutes: 240 },
    });

    expect(fetcher).toHaveBeenNthCalledWith(
      1,
      "/api/v1/constraints/confirm",
      expect.objectContaining({
        headers: expect.objectContaining({ "X-CSRF-Token": "csrf-token-123" }),
      }),
    );
  });
});
