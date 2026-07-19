"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  CrickOpsApiClient,
  type DirectorTurnResponse,
  type SystemModeResponse,
} from "@/lib/api-client";
import { workspaceQueryCache } from "@/lib/query-cache";

export function DirectorPanel() {
  const router = useRouter();
  const [pending, setPending] = useState<"reset" | "delete" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<SystemModeResponse | null>(null);
  const [chatOpen, setChatOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [turn, setTurn] = useState<DirectorTurnResponse | null>(null);
  const [chatPending, setChatPending] = useState(false);

  useEffect(() => {
    let active = true;
    new CrickOpsApiClient().getSystemMode().then(
      (response) => { if (active) setMode(response); },
      () => { if (active) setError("Agent mode could not be checked. Deterministic controls remain available."); },
    );
    return () => { active = false; };
  }, []);

  async function submitDirectorTurn(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const request = message.trim();
    if (!request) return;
    setChatPending(true);
    setError(null);
    try {
      const response = await new CrickOpsApiClient().sendDirectorTurn(request);
      setTurn(response);
      setMessage("");
      setMode((current) => current ? {
        ...current,
        mode: response.mode,
        label: response.mode === "gpt-5.6" ? "GPT-5.6 mode" : response.mode === "fallback-model" ? "Fallback model mode" : "Deterministic mode",
        provider: response.provider,
        model: response.model,
        conversational_available: response.message !== null,
      } : current);
    } catch (turnError) {
      setError(turnError instanceof Error ? turnError.message : "The Tournament Director could not respond.");
    } finally {
      setChatPending(false);
    }
  }

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
          <p className="director-status">
            {mode ? `${mode.label}${mode.model ? ` · ${mode.model}` : ""}` : "Checking agent mode…"}
          </p>
        </div>
      </div>
      <div className="director-message">
        <p>
          I’ll help interpret goals, explain trade-offs, and guide recovery. Confirmed
          decisions always remain visible in the workspace.
        </p>
      </div>
      <button
        className="quiet-button"
        type="button"
        aria-expanded={chatOpen}
        aria-controls="director-chat"
        onClick={() => setChatOpen((current) => !current)}
      >
        {chatOpen ? "Close Director chat" : "Open Director chat"}
      </button>
      {chatOpen && (
        <form id="director-chat" className="director-chat" onSubmit={submitDirectorTurn}>
          <label htmlFor="director-message">Scheduling request</label>
          <textarea
            id="director-message"
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            maxLength={4000}
            placeholder="For example: Prefer rivalry matches in evening prime-time slots."
            disabled={chatPending}
          />
          <button className="primary-action" type="submit" disabled={chatPending || !message.trim()}>
            {chatPending ? "Interpreting request…" : "Send to Tournament Director"}
          </button>
          <div className="director-turn" aria-live="polite">
            {turn?.message ? (
              <>
                <strong>Tournament Director</strong>
                <p>{turn.message}</p>
                {turn.proposed_state_changes.length > 0 && (
                  <div className="director-proposals">
                    <b>Review before applying</b>
                    <ul>
                      {turn.proposed_state_changes.map((change) => (
                        <li key={change.field}>{change.field.replaceAll("_", " ")}: {String(change.proposed_value)}</li>
                      ))}
                    </ul>
                    <span>These proposals have not changed any confirmed constraint.</span>
                  </div>
                )}
              </>
            ) : turn?.unavailable_reason ? (
              <p>{turn.unavailable_reason}</p>
            ) : (
              <p>Use chat for goals and interpretation. Review every important decision in structured controls.</p>
            )}
          </div>
        </form>
      )}
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
