"use client";

import { useMemo, useState } from "react";

import { ApiProblemError, CrickOpsApiClient } from "@/lib/api-client";
import { allocationMinutes, type MatchFormatPreset } from "@/lib/setup-state";

type GuidedSetupProps = {
  conflict?: "stale" | null;
  revision?: number;
  apiClient?: Pick<CrickOpsApiClient, "confirmSetup">;
};

const constraints = [
  ["Fixed competition structure", "8 teams · 2 groups · 15 fixtures", "Hard rule"],
  ["Daily team limit", "A team plays at most once per local calendar day", "Hard rule"],
  ["Knockout chronology", "Groups → semifinals → final", "Hard rule"],
  ["Minimum rest", "Prefer fair rest across group and knockout stages", "Preferred"],
  ["Audience timing", "Prefer prime-time and weekend slots", "Preferred"],
] as const;

export function GuidedSetup({
  conflict = null,
  revision = 0,
  apiClient = new CrickOpsApiClient(),
}: GuidedSetupProps) {
  const [format, setFormat] = useState<MatchFormatPreset>("T20");
  const [manualCoordinates, setManualCoordinates] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [setupStatus, setSetupStatus] = useState<"pending" | "saving" | "ready" | "error">("pending");
  const [staleConflict, setStaleConflict] = useState(conflict === "stale");
  const allocation = useMemo(() => allocationMinutes(format), [format]);

  async function confirmHardConstraints() {
    setSetupStatus("saving");
    setStaleConflict(false);
    try {
      const result = await apiClient.confirmSetup({
        confirmation: true,
        expected_revision: revision,
        selection: { match_format_preset: format, allocation_minutes: allocation },
      });
      setSetupStatus(result.ready ? "ready" : "error");
    } catch (error) {
      if (error instanceof ApiProblemError && error.code === "stale_tournament_revision") {
        setStaleConflict(true);
      }
      setSetupStatus("error");
    }
  }

  return (
    <div className="guided-setup">
      {staleConflict && (
        <div className="conflict-banner" role="alert">
          <div>
            <strong>Tournament setup changed in another request</strong>
            <span>Review the latest revision before confirming constraints.</span>
          </div>
          <button type="button">Reload latest setup</button>
        </div>
      )}

      <section className="setup-block" aria-labelledby="format-heading">
        <div className="block-heading">
          <span>01 / Playing format</span>
          <div><h2 id="format-heading">Set the match footprint</h2><p>One preset applies to every fixture.</p></div>
        </div>
        <fieldset className="format-switch">
          <legend>Match-format preset</legend>
          {(["T10", "T20"] as MatchFormatPreset[]).map((preset) => (
            <label key={preset} className={format === preset ? "selected" : undefined}>
              <input type="radio" name="format" value={preset} checked={format === preset} onChange={() => setFormat(preset)} />
              <strong>{preset}</strong>
              <span>{allocationMinutes(preset)}-minute operational venue allocation</span>
            </label>
          ))}
        </fieldset>
        <p className="allocation-note"><b>{allocation} minutes reserved per fixture.</b> This planning allocation includes play, intervals, setup, and turnover; it is not a guaranteed match duration.</p>
      </section>

      <section className="setup-block" aria-labelledby="venue-heading">
        <div className="block-heading">
          <span>02 / Ground coordinates</span>
          <div><h2 id="venue-heading">Confirm two operating venues</h2><p>The venue name and geographic location stay separate.</p></div>
        </div>
        <div className="venue-board">
          {[1, 2].map((number) => (
            <fieldset className="venue-card" key={number}>
              <legend>Venue {number}</legend>
              <label>Venue display name<input name={`venue-${number}-name`} placeholder={number === 1 ? "Harbour Oval" : "Riverside Cricket Ground"} /></label>
              <label>City, country, area, or postal code<input name={`venue-${number}-query`} placeholder="Auckland, New Zealand" /></label>
              <div className="location-status"><span aria-hidden="true">◎</span><p><b>Location awaiting confirmation</b><small>Search does not discover cricket grounds.</small></p></div>
              {manualCoordinates && (
                <div className="coordinate-grid">
                  <label>Latitude<input name={`venue-${number}-latitude`} inputMode="decimal" placeholder="-36.8485" /></label>
                  <label>Longitude<input name={`venue-${number}-longitude`} inputMode="decimal" placeholder="174.7633" /></label>
                </div>
              )}
            </fieldset>
          ))}
        </div>
        <button className="text-action" type="button" aria-expanded={manualCoordinates} onClick={() => setManualCoordinates((value) => !value)}>Use manual coordinates</button>
        <label className="timezone-field">Shared tournament timezone<input defaultValue="Pacific/Auckland" aria-describedby="timezone-help" /><small id="timezone-help">Both venues must use the same confirmed IANA timezone in Version 1.</small></label>
      </section>

      <section className="setup-block" aria-labelledby="slot-heading">
        <div className="block-heading">
          <span>03 / Fixture strip</span>
          <div><h2 id="slot-heading">Shape the tournament window</h2><p>Define local start patterns; the selected allocation controls overlap and capacity.</p></div>
        </div>
        <div className="date-grid">
          <label>Tournament starts<input type="date" defaultValue="2026-09-07" /></label>
          <label>Tournament ends<input type="date" defaultValue="2026-09-20" /></label>
          <label>Venue blackout date<input type="date" /></label>
        </div>
        <div className="slot-pattern">
          <div><span>MON—FRI</span><label>Weekday start time<input type="time" defaultValue="18:00" /></label></div>
          <div><span>SAT—SUN</span><label>Weekend start times<input defaultValue="10:00, 18:00" /></label></div>
          <div className="slot-readout"><small>Current allocation</small><strong>{format} / {allocation} min</strong><span>No individual duration overrides</span></div>
        </div>
      </section>

      <section className="ledger" aria-labelledby="ledger-heading">
        <div className="ledger-head"><div><p className="eyebrow">Authoritative review</p><h2 id="ledger-heading">Constraint Ledger</h2></div><span>{constraints.length} decisions</span></div>
        <div className="ledger-list">
          {constraints.map(([name, detail, kind]) => (
            <div className="ledger-row" key={name}><span className={kind === "Hard rule" ? "rule-hard" : "rule-soft"}>{kind}</span><div><strong>{name}</strong><p>{detail}</p></div><button type="button" aria-label={`Edit ${name}`}>Edit</button></div>
          ))}
        </div>
        <label className="confirm-check"><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} /><span>I reviewed the hard constraints and confirm they reflect the tournament.</span></label>
        <p className="setup-save-status" aria-live="polite">
          {setupStatus === "pending" && "Confirmation pending"}
          {setupStatus === "saving" && "Saving confirmed constraints…"}
          {setupStatus === "ready" && "Setup ready for schedule generation"}
          {setupStatus === "error" && !staleConflict && "Setup could not be confirmed. Review the fields and try again."}
        </p>
        <button
          className="primary-action"
          type="button"
          disabled={!confirmed || setupStatus === "saving"}
          onClick={confirmHardConstraints}
        >
          Confirm hard constraints
        </button>
      </section>
    </div>
  );
}
