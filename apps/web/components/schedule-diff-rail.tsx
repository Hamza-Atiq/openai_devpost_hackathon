"use client";

import React, { useState } from "react";

import { metricDeltaSentence, metricDisplay, metricLabel } from "@/lib/metric-display";

type DiffFixture = { id: string; fixture: string; detail: string };
type Props = {
  validated: boolean;
  unchanged: DiffFixture[];
  moved: DiffFixture[];
  added: DiffFixture[];
  removed: DiffFixture[];
  metricDeltas: Record<string, number>;
  versions?: Array<{ id: string; number: number; label: string }>;
  onApprove?: () => Promise<void>;
  onReject?: () => Promise<void>;
  onRestore?: (versionId: string) => Promise<void>;
};

function DiffGroup({ title, kind, fixtures }: { title: string; kind: string; fixtures: DiffFixture[] }) {
  const symbol = kind === "preserved" ? "=" : kind === "moved" ? "→" : kind === "added" ? "+" : "−";
  return (
    <section className={`diff-group diff-${kind}`}>
      <h3><span aria-hidden="true">{symbol}</span>{title}<b>{fixtures.length}</b></h3>
      {fixtures.length ? (
        <ul>{fixtures.map((fixture) => <li key={fixture.id}><strong>{fixture.id} · {fixture.fixture}</strong><span>{fixture.detail}</span></li>)}</ul>
      ) : <p>None</p>}
    </section>
  );
}

export function ScheduleDiffRail({ validated, unchanged, moved, added, removed, metricDeltas, versions = [], onApprove, onReject, onRestore }: Props) {
  const [status, setStatus] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  async function act(action: () => Promise<void>, success: string) {
    setPending(true);
    try { await action(); setStatus(success); }
    catch (error) { setStatus(error instanceof Error ? error.message : "Action failed."); }
    finally { setPending(false); }
  }
  const changedCount = moved.length + added.length + removed.length;
  return (
    <section className="repair-review" aria-labelledby="repair-review-title">
      <header>
        <div><p className="eyebrow">Minimum-change repair</p><h1 id="repair-review-title">What changed—and what did not</h1><p>Draft repair compared with the latest immutable official workspace schedule.</p></div>
        <span className={validated ? "validation-pass" : "validation-fail"}>{validated ? "✓ Independently validated" : "! Repair validation failed"}</span>
      </header>
      <div className="diff-rail">
        <DiffGroup title="Preserved fixtures" kind="preserved" fixtures={unchanged} />
        <DiffGroup title="Moved fixtures" kind="moved" fixtures={moved} />
        <DiffGroup title="Added fixtures" kind="added" fixtures={added} />
        <DiffGroup title="Removed fixtures" kind="removed" fixtures={removed} />
      </div>
      <div className="repair-evidence">
        <section>
          <p className="eyebrow">Metric difference · draft minus official</p>
          {Object.keys(metricDeltas).length ? (
            <dl>{Object.entries(metricDeltas).map(([key, delta]) => {
              const config = metricDisplay[key as keyof typeof metricDisplay];
              const improved = config?.better === "lower" ? delta < 0 : delta > 0;
              return <div key={key}><dt>{metricLabel(key)}</dt><dd className={delta === 0 ? "delta-flat" : improved ? "delta-good" : "delta-tradeoff"}>{delta > 0 ? "+" : ""}{delta.toFixed(1)}</dd></div>;
            })}</dl>
          ) : <p>No comparable numeric metric changed.</p>}
        </section>
        <section>
          <p className="eyebrow">Recovery explanation</p>
          <h2>{moved.length} fixture{moved.length === 1 ? "" : "s"} moved; {unchanged.length} preserved.</h2>
          <p>The selected venue-time slot became unavailable. The deterministic repair engine minimized changed fixtures before movement distance and quality degradation.</p>
          {Object.keys(metricDeltas).length > 0 && <ul aria-label="Repair trade-offs">{Object.entries(metricDeltas).map(([key, delta]) => <li key={key}>{metricDeltaSentence(key, delta)}</li>)}</ul>}
          <ul><li><strong>Solver evidence:</strong> {changedCount} changed placement{changedCount === 1 ? "" : "s"}.</li><li><strong>Validator evidence:</strong> {validated ? "all hard constraints and stage chronology passed" : "validation failed"}.</li></ul>
        </section>
      </div>
      {validated ? (
        <div className="schedule-approval"><div><strong>Review complete?</strong><span>Approval creates a new official version. Until then, the current official schedule remains unchanged.</span></div><button className="secondary-action" type="button" disabled={pending} onClick={() => onReject && void act(onReject, "Repair rejected. Official schedule unchanged.")}>Reject repair</button><button className="primary-action" type="button" disabled={pending} onClick={() => onApprove && void act(onApprove, "Repaired schedule approved as a new official version.")}>Approve repaired schedule</button></div>
      ) : <div className="error-banner" role="alert">This repair cannot be approved; the official baseline remains unchanged.</div>}
      {status && <div className="official-confirmation" role="status">{status}</div>}
      <section className="version-history" aria-labelledby="version-history-title">
        <div><p className="eyebrow">Official history</p><h2 id="version-history-title">Restore an earlier schedule</h2><p>Restoration creates a new official version; history is never rewritten.</p></div>
        <ul>{versions.map((version) => <li key={version.id}><span><strong>Version {version.number}</strong><small>{version.label}</small></span><button className="secondary-action" type="button" disabled={pending} onClick={() => onRestore && void act(() => onRestore(version.id), `Version ${version.number} restored as a new official version.`)}>Restore this version</button></li>)}</ul>
      </section>
    </section>
  );
}
