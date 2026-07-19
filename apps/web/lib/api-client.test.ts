import { afterEach, describe, expect, it, vi } from "vitest";

import { CrickOpsApiClient } from "./api-client";
import type { TournamentSetupSaveInput, TournamentSetupView } from "./setup-contract";

describe("CrickOpsApiClient", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("binds the browser fetch receiver when no test fetcher is injected", async () => {
    const browserFetch = vi.fn(function (this: typeof globalThis) {
      if (this !== globalThis) throw new TypeError("Illegal invocation");
      return Promise.resolve(
        new Response(JSON.stringify({ items: [], next_cursor: null, has_more: false }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    });
    vi.stubGlobal("fetch", browserFetch);

    await new CrickOpsApiClient().getAuditEvents();

    expect(browserFetch).toHaveBeenCalledOnce();
  });

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
      expect.objectContaining({
        method: "POST",
        credentials: "same-origin",
        body: JSON.stringify({ expected_revision: 4 }),
      }),
    );
  });

  it("loads and saves the complete revisioned setup through typed endpoints", async () => {
    vi.stubGlobal("crypto", { randomUUID: () => "setup-save-key" });
    const setup = {
      name: "Pakistan Community Cricket Cup",
      revision: 3,
    } as TournamentSetupView;
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify(setup), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ...setup, revision: 4 }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    const client = new CrickOpsApiClient(fetcher);
    const update = {
      expected_revision: 3,
      match_format_preset: "T10",
    } as TournamentSetupSaveInput;

    await client.getTournamentSetup();
    await client.saveTournamentSetup(update);

    expect(fetcher).toHaveBeenNthCalledWith(
      1,
      "/api/v1/tournament",
      expect.objectContaining({ method: "GET", cache: "no-store" }),
    );
    expect(fetcher).toHaveBeenNthCalledWith(
      2,
      "/api/v1/tournament",
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify(update),
        headers: expect.objectContaining({ "Idempotency-Key": "setup-save-key" }),
      }),
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

  it("reads the active agent mode and submits a Director turn", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            mode: "gpt-5.6",
            label: "GPT-5.6 mode",
            provider: "openai",
            model: "gpt-5.6",
            conversational_available: true,
            deterministic_services_available: true,
            fabricated_agent_response: false,
            emergency_cached_results: false,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            message: "Review this preferred evening-slot interpretation.",
            mode: "gpt-5.6",
            provider: "openai",
            model: "gpt-5.6",
            proposed_state_changes: [],
            specialist_requests: [],
            evidence_refs: [],
            ui_actions: [],
            attempt_count: 1,
            transitions: ["primary_active"],
            unavailable_reason: null,
            fabricated_agent_response: false,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    const client = new CrickOpsApiClient(fetcher);

    const mode = await client.getSystemMode();
    const turn = await client.sendDirectorTurn("Prefer evening matches.");

    expect(mode.conversational_available).toBe(true);
    expect(turn.message).toContain("evening-slot");
    expect(fetcher).toHaveBeenNthCalledWith(
      1,
      "/api/v1/system/mode",
      expect.objectContaining({ method: "GET", cache: "no-store" }),
    );
    expect(fetcher).toHaveBeenNthCalledWith(
      2,
      "/api/v1/director/turn",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ message: "Prefer evening matches." }),
      }),
    );
  });
});
