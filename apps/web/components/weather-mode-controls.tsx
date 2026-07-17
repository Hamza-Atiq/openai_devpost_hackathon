"use client";

import React, { useState } from "react";

import { CrickOpsApiClient } from "@/lib/api-client";

type ThresholdProposal = { metric: string; value: number };
type WeatherModeControlsProps = {
  initialMode?: "live" | "deterministic";
  initialProviderUnavailable?: boolean;
  initialProposal?: ThresholdProposal;
};

export function WeatherModeControls({ initialMode = "deterministic", initialProviderUnavailable = false, initialProposal }: WeatherModeControlsProps) {
  const [mode, setMode] = useState(initialMode);
  const [providerUnavailable, setProviderUnavailable] = useState(initialProviderUnavailable);
  const [proposal, setProposal] = useState<ThresholdProposal | undefined>(initialProposal);
  const [confirmedRevision, setConfirmedRevision] = useState<number | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function selectMode(next: "live" | "deterministic") {
    setPending(true); setError(null);
    try {
      const status = next === "deterministic" ? await new CrickOpsApiClient().activateRainDemo() : await new CrickOpsApiClient().refreshWeather("live");
      setMode(status.mode); setProviderUnavailable(status.quality === "unavailable");
    } catch (modeError) { setError(modeError instanceof Error ? modeError.message : "Weather mode change failed."); }
    finally { setPending(false); }
  }

  async function propose(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setPending(true); setError(null);
    const form = new FormData(event.currentTarget);
    try {
      const result = await new CrickOpsApiClient().proposeWeatherThreshold(String(form.get("metric")), Number(form.get("value")));
      setProposal(result.threshold); setConfirmed(false); setConfirmedRevision(null);
    } catch (proposalError) { setError(proposalError instanceof Error ? proposalError.message : "Threshold proposal failed."); }
    finally { setPending(false); }
  }

  return (
    <section className="weather-controls" aria-labelledby="weather-controls-title">
      <header><div><p className="eyebrow">Weather decision controls</p><h2 id="weather-controls-title">Choose the evidence mode</h2></div><span className={`weather-mode-state mode-${mode}`}>{mode === "live" ? "Live forecast mode" : "Deterministic demo mode"}</span></header>
      <div className="mode-switch" role="group" aria-label="Weather data mode"><button type="button" aria-pressed={mode === "live"} disabled={pending} onClick={() => void selectMode("live")}>Live forecast</button><button type="button" aria-pressed={mode === "deterministic"} disabled={pending} onClick={() => void selectMode("deterministic")}>Deterministic demo</button></div>
      {providerUnavailable && <div className="weather-warning" role="alert"><strong>Live provider unavailable</strong><span>Deterministic mode is available. CrickOps will never imitate or fabricate a live forecast.</span></div>}
      {error && <div className="error-banner" role="alert">{error}</div>}
      <form className="threshold-form" onSubmit={propose}><label>Weather measure<select name="metric" defaultValue="precipitation_probability"><option value="precipitation_probability">Precipitation probability</option><option value="temperature_max_c">Maximum temperature</option><option value="wind_speed_kmh">Wind speed</option></select></label><label>Threshold value<input name="value" type="number" min="0" max="100" defaultValue="70" /></label><button className="secondary-action" type="submit" disabled={pending}>Propose threshold</button></form>
      {proposal && <div className="threshold-proposal"><div><span>Proposed · still advisory</span><strong>{proposal.metric.replaceAll("_", " ")} · {proposal.value}</strong><small>Forecast uncertainty does not block a slot until you explicitly confirm this threshold.</small></div><label><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} /> I understand this makes crossings unavailable for scheduling.</label><button className="primary-action" type="button" disabled={!confirmed || pending || confirmedRevision !== null} onClick={async () => { setPending(true); try { setConfirmedRevision(await new CrickOpsApiClient().confirmWeatherThreshold(proposal.metric, proposal.value)); } catch (confirmError) { setError(confirmError instanceof Error ? confirmError.message : "Threshold confirmation failed."); } finally { setPending(false); } }}>{confirmedRevision ? `Confirmed · revision ${confirmedRevision}` : "Confirm as hard constraint"}</button></div>}
      <p className="weather-disclaimer">CrickOps provides risk guidance only. The organizer remains responsible for official safety, delay, move, and cancellation decisions.</p>
    </section>
  );
}
