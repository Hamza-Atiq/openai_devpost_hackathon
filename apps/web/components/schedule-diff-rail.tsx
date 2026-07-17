"use client";

import React, { useState } from "react";

type DiffFixture = { id: string; fixture: string; detail: string };
type Props = {
  validated?: boolean;
  unchanged?: DiffFixture[];
  moved?: DiffFixture[];
  added?: DiffFixture[];
  removed?: DiffFixture[];
  metricDeltas?: Record<string, number>;
  versions?: Array<{ id: string; number: number; label: string }>;
  onApprove?: () => Promise<void>;
  onReject?: () => Promise<void>;
  onRestore?: (versionId: string) => Promise<void>;
};

const defaults = {
  unchanged: [
    { id: "G01", fixture: "Falcons vs Lions", detail: "07 Sep · 10:00 · National Cricket Ground" },
    { id: "G02", fixture: "Mariners vs Royals", detail: "07 Sep · 18:00 · Riverside Oval" },
  ],
  moved: [{ id: "G07", fixture: "Strikers vs United", detail: "10 Sep 18:00 → 11 Sep 10:00 · Riverside Oval" }],
  added: [] as DiffFixture[],
  removed: [] as DiffFixture[],
};

const metricLabels: Record<string, { label: string; positive: "up" | "down" }> = {
  weather_risk: { label: "Weather risk", positive: "down" },
  group_rest_fairness: { label: "Rest fairness", positive: "up" },
  venue_balance: { label: "Venue balance", positive: "up" },
  slot_balance: { label: "Slot balance", positive: "up" },
  preference_satisfaction: { label: "Preference satisfaction", positive: "up" },
};

function DiffGroup({ title, kind, fixtures }: { title: string; kind: string; fixtures: DiffFixture[] }) {
  return <section className={`diff-group diff-${kind}`}><h3><span aria-hidden="true">{kind === "preserved" ? "=" : kind === "moved" ? "→" : kind === "added" ? "+" : "−"}</span>{title}<b>{fixtures.length}</b></h3>{fixtures.length ? <ul>{fixtures.map((fixture) => <li key={fixture.id}><strong>{fixture.id} · {fixture.fixture}</strong><span>{fixture.detail}</span></li>)}</ul> : <p>None</p>}</section>;
}

export function ScheduleDiffRail({ validated = true, unchanged = defaults.unchanged, moved = defaults.moved, added = defaults.added, removed = defaults.removed, metricDeltas = { weather_risk: -9.4, group_rest_fairness: 1.8, venue_balance: 0, slot_balance: -2.1, preference_satisfaction: -1.4 }, versions = [{ id: "version-1", number: 1, label: "Original official schedule" }], onApprove, onReject, onRestore }: Props) {
  const [status, setStatus] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  async function act(action: () => Promise<void>, success: string) { setPending(true); try { await action(); setStatus(success); } catch (error) { setStatus(error instanceof Error ? error.message : "Action failed."); } finally { setPending(false); } }
  return (
    <section className="repair-review" aria-labelledby="repair-review-title">
      <header><div><p className="eyebrow">Minimum-change repair</p><h1 id="repair-review-title">What changed—and what did not</h1><p>Draft repair compared with the latest immutable official workspace schedule.</p></div><span className={validated ? "validation-pass" : "validation-fail"}>{validated ? "✓ Independently validated" : "! Repair validation failed"}</span></header>
      <div className="diff-rail"><DiffGroup title="Preserved fixtures" kind="preserved" fixtures={unchanged} /><DiffGroup title="Moved fixtures" kind="moved" fixtures={moved} /><DiffGroup title="Added fixtures" kind="added" fixtures={added} /><DiffGroup title="Removed fixtures" kind="removed" fixtures={removed} /></div>
      <div className="repair-evidence"><section><p className="eyebrow">Metric difference · draft minus official</p><dl>{Object.entries(metricDeltas).map(([key, delta]) => { const config = metricLabels[key] ?? { label: key.replaceAll("_", " "), positive: "up" as const }; const improved = config.positive === "up" ? delta > 0 : delta < 0; return <div key={key}><dt>{config.label}</dt><dd className={delta === 0 ? "delta-flat" : improved ? "delta-good" : "delta-tradeoff"}>{delta > 0 ? "+" : ""}{delta.toFixed(1)}</dd></div>; })}</dl></section><section><p className="eyebrow">Recovery explanation</p><h2>One fixture moved; the rest stay anchored.</h2><p>The disrupted venue-time slot became unavailable. The repair engine first minimized changed fixtures, then movement distance, then quality degradation.</p><ul><li><strong>Solver evidence:</strong> changed-fixture optimum preserved.</li><li><strong>Validator evidence:</strong> all hard constraints and stage chronology passed.</li><li><strong>Trade-off:</strong> slot balance decreases slightly to reduce weather exposure.</li></ul></section></div>
      {validated ? <div className="schedule-approval"><div><strong>Review complete?</strong><span>Approval creates a new official version. Until then, the current official schedule remains unchanged.</span></div><button className="secondary-action" type="button" disabled={pending} onClick={() => onReject && void act(onReject, "Repair rejected. Official schedule unchanged.")}>Reject repair</button><button className="primary-action" type="button" disabled={pending} onClick={() => onApprove && void act(onApprove, "Repaired schedule approved as a new official version.")}>Approve repaired schedule</button></div> : <div className="error-banner" role="alert">This repair cannot be approved; the official baseline remains unchanged.</div>}
      {status && <div className="official-confirmation" role="status">{status}</div>}
      <section className="version-history" aria-labelledby="version-history-title"><div><p className="eyebrow">Official history</p><h2 id="version-history-title">Restore an earlier schedule</h2><p>Restoration creates a new official version; history is never rewritten.</p></div><ul>{versions.map((version) => <li key={version.id}><span><strong>Version {version.number}</strong><small>{version.label}</small></span><button className="secondary-action" type="button" disabled={pending} onClick={() => onRestore && void act(() => onRestore(version.id), `Version ${version.number} restored as a new official version.`)}>Restore this version</button></li>)}</ul></section>
    </section>
  );
}
