"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { ApiProblemError, CrickOpsApiClient } from "@/lib/api-client";
import { workspaceQueryCache } from "@/lib/query-cache";

const samples = [
  {
    id: "global-community-cup",
    label: "International sample",
    name: "Global Community Cricket Cup",
    detail: "T20 · 8 teams · 2 venues · neutral judge-ready setup",
  },
  {
    id: "pakistan-community-cup",
    label: "Pakistan sample",
    name: "Pakistan Community Cricket Cup",
    detail: "T20 · 8 teams · 2 venues · original target-market scenario",
  },
] as const;

export function SampleChooser() {
  const router = useRouter();
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function start(sampleId?: string) {
    setPending(sampleId ?? "blank");
    setError(null);
    try {
      const workspace = await new CrickOpsApiClient().createWorkspace(sampleId);
      workspaceQueryCache.set("workspace", workspace);
      router.push("/workspace/setup");
    } catch (reason) {
      const message =
        reason instanceof ApiProblemError
          ? `${reason.message} Reference: ${reason.correlationId}`
          : "The workspace could not be created. Try again.";
      setError(message);
      setPending(null);
    }
  }

  return (
    <section className="sample-section" aria-labelledby="sample-heading">
      <div className="section-heading">
        <p className="eyebrow">Start in under ten seconds</p>
        <h2 id="sample-heading">Choose a tournament board</h2>
        <p>Load a complete sample, then compare and repair real solver-generated schedules.</p>
      </div>
      <div className="sample-grid">
        {samples.map((sample) => (
          <article className="sample-card" key={sample.id}>
            <p className="card-label">{sample.label}</p>
            <h3>{sample.name}</h3>
            <p>{sample.detail}</p>
            <button aria-label={`Load ${sample.name} sample`} disabled={pending !== null} onClick={() => start(sample.id)} type="button">
              {pending === sample.id ? "Creating workspace…" : "Load sample"}
            </button>
          </article>
        ))}
        <article className="sample-card blank-card">
          <p className="card-label">Guided setup</p>
          <h3>Build your own tournament</h3>
          <p>Start blank with the fixed Version 1 competition structure.</p>
          <button disabled={pending !== null} onClick={() => start()} type="button">
            {pending === "blank" ? "Creating workspace…" : "Create a blank tournament"}
          </button>
        </article>
      </div>
      {error ? <p className="error-banner" role="alert">{error}</p> : null}
      <p className="privacy-note">
        Guest workspaces expire after seven days of inactivity. Do not enter personal, confidential,
        financial, or payment information.
      </p>
    </section>
  );
}
