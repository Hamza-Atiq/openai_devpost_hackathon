"use client";

import { useState } from "react";

import { loadProbeSession, mutateProbeSession, type ProbeSession } from "@/lib/session-probe";

export default function SessionProbePage() {
  const [session, setSession] = useState<ProbeSession | null>(null);
  const [message, setMessage] = useState("Probe has not run.");

  async function connect() {
    try {
      const next = await loadProbeSession();
      setSession(next);
      setMessage("Guest cookie accepted through the same-origin proxy.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Session probe failed.");
    }
  }

  async function mutate() {
    if (!session) return;
    try {
      const result = await mutateProbeSession(session.csrf_token, "browser-check");
      setSession({ ...session, mutation_count: result.mutation_count });
      setMessage("Origin and CSRF checks accepted the mutation.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Mutation probe failed.");
    }
  }

  return (
    <main style={{ fontFamily: "system-ui", margin: "4rem auto", maxWidth: 680, padding: "0 1rem" }}>
      <p style={{ color: "#1f6b45", fontWeight: 700 }}>CrickOps deployment spike</p>
      <h1>Guest session boundary check</h1>
      <p>
        This disposable page verifies proxy, secure-cookie, private-cache, environment-isolation,
        and mutation-protection behavior. It is not the Version 1 workspace UI.
      </p>
      <div style={{ display: "flex", gap: 12, margin: "2rem 0" }}>
        <button type="button" onClick={connect}>Connect guest session</button>
        <button type="button" onClick={mutate} disabled={!session}>Test protected mutation</button>
      </div>
      <output aria-live="polite">
        <strong>{message}</strong>
        {session ? (
          <dl>
            <dt>Environment</dt><dd>{session.environment}</dd>
            <dt>Opaque session fingerprint</dt><dd>{session.session_id}</dd>
            <dt>Accepted mutations</dt><dd>{session.mutation_count}</dd>
          </dl>
        ) : null}
      </output>
    </main>
  );
}
