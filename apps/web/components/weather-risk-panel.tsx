import React from "react";

export type FixtureWeatherView = {
  id: string;
  label: string;
  venue: string;
  startsAt: string;
  risk: number | null;
};

type WeatherRiskPanelProps = {
  coverage: number;
  issuedAt: string;
  stale: boolean;
  provider: string;
  fixtures: FixtureWeatherView[];
  allocationMinutes: number;
};

function riskPresentation(risk: number | null) {
  if (risk === null) return { label: "Unknown", symbol: "?", level: "unknown" };
  if (risk >= 70) return { label: "High risk", symbol: "▲", level: "high" };
  if (risk >= 35) return { label: "Moderate risk", symbol: "◆", level: "moderate" };
  return { label: "Lower risk", symbol: "●", level: "low" };
}

export function weatherAttribution(provider: string, issuedAt: string) {
  return `Weather data by ${provider}. Forecast issued ${issuedAt}. CrickOps provides planning guidance only.`;
}

export function WeatherRiskPanel({ coverage, issuedAt, stale, provider, fixtures, allocationMinutes }: WeatherRiskPanelProps) {
  const coverageLabel = coverage === 0 ? "No forecast coverage" : coverage < 100 ? "Partial forecast coverage" : `${coverage.toFixed(1)}% forecast coverage`;
  return (
    <section className="weather-intelligence" aria-labelledby="weather-title">
      <header className="weather-intelligence-head">
        <div><p className="eyebrow">Weather intelligence</p><h2 id="weather-title">Risk across the operational allocation</h2><p>Each score covers the full {allocationMinutes / 60}-hour allocation block, including setup and turnover.</p></div>
        <div className={`coverage-seal coverage-${coverage === 100 ? "full" : coverage === 0 ? "none" : "partial"}`}><strong>{coverage.toFixed(1)}%</strong><span>{coverageLabel}</span></div>
      </header>
      {stale && <div className="weather-warning" role="status"><strong>Forecast is stale</strong><span>Refresh before using these scores for a scheduling decision.</span></div>}
      {coverage < 100 && <div className="weather-warning" role="status"><strong>{coverageLabel}</strong><span>Uncovered fixtures remain Unknown and receive the configured missing-coverage penalty.</span></div>}
      <div className="risk-ledger" role="list" aria-label="Fixture weather risks">
        {fixtures.length ? fixtures.map((fixture) => {
          const presentation = riskPresentation(fixture.risk);
          return <article className={`risk-row risk-${presentation.level}`} role="listitem" key={fixture.id}><span className="risk-symbol" aria-hidden="true">{presentation.symbol}</span><div><strong>{fixture.id} · {fixture.label}</strong><span>{fixture.venue} · <time dateTime={fixture.startsAt}>{new Date(fixture.startsAt).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })}</time></span></div><div className="risk-reading"><strong>{fixture.risk === null ? "—" : fixture.risk.toFixed(1)}</strong><span>{presentation.label}</span></div></article>;
        }) : <div className="operation-status">No scheduled fixture weather is available.</div>}
      </div>
      <footer className="weather-attribution"><span>Issued {issuedAt}</span><span>{weatherAttribution(provider, issuedAt)}</span></footer>
      <p className="weather-disclaimer">Risk scores are planning guidance. CrickOps does not make official safety, medical, venue, or regulatory decisions and cannot guarantee prevention of washouts.</p>
    </section>
  );
}
