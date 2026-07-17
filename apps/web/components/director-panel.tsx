"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { CrickOpsApiClient } from "@/lib/api-client";
import { workspaceQueryCache } from "@/lib/query-cache";

export function DirectorPanel() {
  const router = useRouter();
  const [pending, setPending] = useState<"reset" | "delete" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function resetDemo() {
    if (!window.confirm("Reset this workspace and load the international sample?")) return;
    setPending("reset");
    setError(null);
    try {
      const workspace = await new CrickOpsApiClient().resetWorkspace();
      workspaceQueryCache.set("workspace", workspace);
      router.push("/workspace/setup");
    } catch {
      setError("The demo could not be reset. Your current workspace is unchanged.");
    } finally {
      setPending(null);
    }
  }

  async function deleteWorkspace() {
    if (!window.confirm("Delete this guest workspace and its tournament data?")) return;
    setPending("delete");
    setError(null);
    try {
      await new CrickOpsApiClient().deleteWorkspace();
      workspaceQueryCache.invalidate("");
      router.push("/");
    } catch {
      setError("The workspace could not be deleted. No data was removed.");
    } finally {
      setPending(null);
    }
  }

  return (
    <aside className="director-panel" aria-label="Tournament Director">
      <div className="director-heading">
        <span className="status-dot" aria-hidden="true" />
        <div>
          <p className="eyebrow">Tournament Director</p>
          <p className="director-status">Deterministic mode ready</p>
        </div>
      </div>
      <div className="director-message">
        <p>
          I’ll help interpret goals, explain trade-offs, and guide recovery. Confirmed
          decisions always remain visible in the workspace.
        </p>
      </div>
      <button className="quiet-button" type="button" aria-expanded="false">
        Open Director chat
      </button>
      <div className="workspace-actions" aria-label="Workspace data actions">
        <a href="/api/v1/workspace/export">Export tournament</a>
        <button disabled={pending !== null} onClick={resetDemo} type="button">
          {pending === "reset" ? "Resetting…" : "Reset demo"}
        </button>
        <button disabled={pending !== null} onClick={deleteWorkspace} type="button">
          {pending === "delete" ? "Deleting…" : "Delete workspace"}
        </button>
      </div>
      <p className="director-action-status" aria-live="polite">
        {error ?? "Guest data expires after inactivity; product-wide feedback is opt-in only."}
      </p>
    </aside>
  );
}
