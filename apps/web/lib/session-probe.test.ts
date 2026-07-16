import { describe, expect, it, vi } from "vitest";

import { loadProbeSession, mutateProbeSession } from "./session-probe";

describe("TASK-005 browser probe client", () => {
  it("loads the session through the same-origin API path", async () => {
    const fetcher = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ session_id: "guest-a", csrf_token: "csrf", environment: "preview" }),
    });

    await loadProbeSession(fetcher);

    expect(fetcher).toHaveBeenCalledWith("/api/v1/spike/session", {
      cache: "no-store",
      credentials: "same-origin",
    });
  });

  it("sends the CSRF token on a same-origin mutation", async () => {
    const fetcher = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ mutation_count: 1 }),
    });

    await mutateProbeSession("csrf", "browser-check", fetcher);

    expect(fetcher).toHaveBeenCalledWith(
      "/api/v1/spike/session/mutations",
      expect.objectContaining({
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": "csrf" },
        body: JSON.stringify({ value: "browser-check" }),
      }),
    );
  });

  it("surfaces a rejected probe request", async () => {
    const fetcher = vi.fn().mockResolvedValue({ ok: false, status: 403 });

    await expect(loadProbeSession(fetcher)).rejects.toThrow("Session probe failed (403)");
  });
});
