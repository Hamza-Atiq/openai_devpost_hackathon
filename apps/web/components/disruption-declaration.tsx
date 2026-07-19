"use client";

import React, { useState } from "react";

import { CrickOpsApiClient } from "@/lib/api-client";

type AffectedSlot = { id: string; fixture: string; venue: string; localTime: string };
type Props = {
  officialVersion: number;
  slots: AffectedSlot[];
  onRepairReady?: (draftId: string) => void;
};

export function DisruptionDeclaration({ officialVersion, slots, onRepairReady }: Props) {
  const [type, setType] = useState<"rain" | "venue_unavailability">("rain");
  const [selected, setSelected] = useState<string[]>([]);
  const [pending, setPending] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!selected.length) { setError("Select at least one unavailable venue-time slot."); return; }
    setPending(true); setError(null);
    try {
      const repair = await new CrickOpsApiClient().declareAndRepairDisruption(type, selected);
      setResult(repair.draft_id);
      onRepairReady?.(repair.draft_id);
    } catch (declarationError) { setError(declarationError instanceof Error ? declarationError.message : "Recovery could not start."); }
    finally { setPending(false); }
  }

  return (
    <section className="disruption-console" aria-labelledby="disruption-title">
      <header><div><p className="eyebrow">Recovery control</p><h1 id="disruption-title">Declare an operational disruption</h1><p>Official Version {officialVersion} baseline · the official schedule remains unchanged until a repaired draft is approved.</p></div><span>Minimum-change workflow</span></header>
      <form onSubmit={submit}>
        <fieldset className="disruption-types"><legend>Disruption type</legend><label><input type="radio" name="type" checked={type === "rain"} onChange={() => setType("rain")} /><strong>Rain disruption</strong><span>Forecast threshold or organizer-declared rain impact.</span></label><label><input type="radio" name="type" checked={type === "venue_unavailability"} onChange={() => setType("venue_unavailability")} /><strong>Venue unavailable</strong><span>Block one or more venue-time slots.</span></label></fieldset>
        <fieldset className="affected-fixtures"><legend>Affected fixtures</legend><p>Select at least one unavailable venue-time slot from the official schedule.</p>{slots.length ? slots.map((slot) => <label key={slot.id}><input type="checkbox" checked={selected.includes(slot.id)} onChange={(event) => setSelected((current) => event.target.checked ? [...current, slot.id] : current.filter((id) => id !== slot.id))} /><span><strong>{slot.fixture}</strong><small>{slot.venue} · {slot.localTime}</small></span></label>) : <div className="operation-status">No official fixture slots are available for recovery.</div>}</fieldset>
        {error && <div className="error-banner" role="alert">{error}</div>}
        {result && <div className="official-confirmation" role="status"><strong>Repaired draft ready</strong><span>Draft {result} is awaiting review and approval.</span></div>}
        <button className="primary-action" type="submit" disabled={pending}>{pending ? "Repairing and validating…" : "Generate a repaired draft"}</button>
      </form>
    </section>
  );
}
