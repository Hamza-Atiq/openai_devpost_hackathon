"use client";

import React, { useState, type CSSProperties } from "react";

import { ScheduleApprovalDialog } from "./schedule-approval-dialog";

export type ComparisonMetrics = {
  weatherRisk: number | null;
  weatherCoverage: number;
  groupRestFairness: number;
  potentialKnockoutRest: number;
  venueBalance: number;
  slotBalance: number;
  preferenceSatisfaction: number;
};

export type ComparisonOption = {
  draftId?: string;
  profile: "balanced" | "weather-first" | "fairness-first" | "custom";
  label: string;
  validationValid: boolean;
  metrics: ComparisonMetrics;
  softViolations: string[];
};

type ProfileComparisonProps = {
  options?: ComparisonOption[];
  identicalProfiles?: string[];
  showCustom?: boolean;
  onGenerate?: (priorities?: Record<string, number>) => Promise<{
    options: ComparisonOption[];
    identicalProfiles: string[];
    runId?: string;
  }>;
  onApprove?: (draftId: string) => Promise<{ versionNumber: number; approvedAt: string }>;
};

const defaultOptions: ComparisonOption[] = [
  {
    profile: "balanced",
    label: "Balanced",
    validationValid: true,
    metrics: { weatherRisk: 31, weatherCoverage: 100, groupRestFairness: 92, potentialKnockoutRest: 85, venueBalance: 94, slotBalance: 88, preferenceSatisfaction: 91 },
    softViolations: ["One prime-time preference remains unmet."],
  },
  {
    profile: "weather-first",
    label: "Weather-first",
    validationValid: true,
    metrics: { weatherRisk: 22, weatherCoverage: 100, groupRestFairness: 86, potentialKnockoutRest: 81, venueBalance: 88, slotBalance: 84, preferenceSatisfaction: 87 },
    softViolations: ["Two teams receive a shorter rest margin than Balanced."],
  },
  {
    profile: "fairness-first",
    label: "Fairness-first",
    validationValid: true,
    metrics: { weatherRisk: 37, weatherCoverage: 100, groupRestFairness: 97, potentialKnockoutRest: 94, venueBalance: 98, slotBalance: 95, preferenceSatisfaction: 84 },
    softViolations: ["A preferred weekend slot is not used."],
  },
];

const metricRows: Array<{ key: keyof ComparisonMetrics; label: string; direction: string }> = [
  { key: "weatherRisk", label: "Weather risk", direction: "Lower is better" },
  { key: "weatherCoverage", label: "Weather coverage", direction: "Higher is better" },
  { key: "groupRestFairness", label: "Rest fairness", direction: "Higher is better" },
  { key: "potentialKnockoutRest", label: "Potential knockout rest", direction: "Higher is better" },
  { key: "venueBalance", label: "Venue balance", direction: "Higher is better" },
  { key: "slotBalance", label: "Slot balance", direction: "Higher is better" },
  { key: "preferenceSatisfaction", label: "Preference satisfaction", direction: "Higher is better" },
];

const customControls = [
  ["weather_coverage", "Minimize weather risk", 45],
  ["rest", "Maximize fair rest", 30],
  ["venue_balance", "Balance venue allocation", 10],
  ["slot_balance", "Balance time slots", 5],
  ["organizer_preferences", "Honor organizer preferences", 5],
  ["audience_timing", "Prefer audience-friendly timing", 5],
] as const;

function metricValue(value: number | null) {
  return value === null ? "Unknown" : `${value.toFixed(1)}%`;
}

export function metricBarWidth(key: keyof ComparisonMetrics, value: number | null) {
  if (value === null) return 0;
  return key === "weatherRisk" ? 100 - value : value;
}

export function ProfileComparison({
  options = defaultOptions,
  identicalProfiles = [],
  showCustom = false,
  onGenerate,
  onApprove,
}: ProfileComparisonProps) {
  const [customVisible, setCustomVisible] = useState(showCustom);
  const [selected, setSelected] = useState<string | null>(null);
  const [displayedOptions, setDisplayedOptions] = useState(options);
  const [identical, setIdentical] = useState(identicalProfiles);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [approvedVersion, setApprovedVersion] = useState<{ versionNumber: number; approvedAt: string } | null>(null);
  const [generatedRunId, setGeneratedRunId] = useState<string | null>(null);

  async function generate(priorities?: Record<string, number>) {
    if (!onGenerate) return;
    setPending(true);
    setError(null);
    try {
      const result = await onGenerate(priorities);
      setDisplayedOptions(result.options);
      setIdentical(result.identicalProfiles);
      setGeneratedRunId(result.runId ?? null);
      setSelected(null);
    } catch (generationError) {
      setError(generationError instanceof Error ? generationError.message : "Schedule generation failed.");
    } finally {
      setPending(false);
    }
  }

  function submitCustom(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = Object.fromEntries(
      Array.from(new FormData(event.currentTarget).entries()).map(([name, value]) => [name, Number(value)]),
    );
    void generate(values);
  }

  return (
    <section className="comparison-studio" aria-labelledby="comparison-title">
      <header className="comparison-head">
        <div>
          <p className="eyebrow">Schedule decision studio</p>
          <h1 id="comparison-title">Compare the trade-offs, fixture by fixture.</h1>
          <p>Every option uses the same confirmed hard constraints and the same metric version.</p>
        </div>
        <div className="comparison-actions">
          <span className="metric-version">Metrics · v1</span>
          {onGenerate && <button className="primary-action" type="button" disabled={pending} onClick={() => void generate()}>{pending ? "Solving and validating…" : "Generate three profiles"}</button>}
          <button className="secondary-action" type="button" onClick={() => setCustomVisible((value) => !value)} aria-expanded={customVisible}>
            {customVisible ? "Hide Custom priorities" : "Add Custom priorities"}
          </button>
        </div>
      </header>

      {error && <div className="error-banner" role="alert">{error} Keep the confirmed constraints and try again.</div>}
      {generatedRunId && <div className="operation-status" role="status">New validated schedule run loaded.</div>}

      {identical.length > 1 && (
        <aside className="identical-note" role="note">
          <strong>Same fixture placement</strong>
          <span>{identical.join(" and ")} produced the same fixture placement. Their metrics remain visible because their priorities are still different.</span>
        </aside>
      )}

      <div className="comparison-grid" aria-busy={pending} style={{ "--option-count": displayedOptions.length } as CSSProperties}>
        <div className="metric-spine" aria-hidden="true">
          <span>Validated options</span>
          {metricRows.map((row) => <span key={row.key}>{row.label}<small>{row.direction}</small></span>)}
          <span>Soft-constraint notes</span>
        </div>
        {displayedOptions.map((option) => (
          <article className={`profile-column profile-${option.profile}`} key={option.profile} aria-labelledby={`${option.profile}-title`}>
            <header>
              <p>{option.profile === "custom" ? "Organizer-weighted" : "Optimization preset"}</p>
              <h2 id={`${option.profile}-title`}>{option.label}</h2>
              <span className={option.validationValid ? "validation-pass" : "validation-fail"}>
                <b aria-hidden="true">{option.validationValid ? "✓" : "!"}</b>
                Independent validation {option.validationValid ? "passed" : "failed"}
              </span>
            </header>
            <dl>
              {metricRows.map((row) => {
                const value = option.metrics[row.key];
                return <div key={row.key}><dt>{row.label}</dt><dd>{metricValue(value)}</dd><span className="metric-track" aria-hidden="true"><i style={{ width: `${metricBarWidth(row.key, value)}%` }} /></span></div>;
              })}
            </dl>
            <div className="violation-list">
              <h3>Soft-constraint notes</h3>
              {option.softViolations.length ? <ul>{option.softViolations.map((item) => <li key={item}>{item}</li>)}</ul> : <p>No soft-constraint violations.</p>}
            </div>
            <button
              className="profile-select"
              type="button"
              disabled={!option.validationValid}
              aria-pressed={selected === option.profile}
              onClick={() => setSelected(option.profile)}
            >
              {selected === option.profile ? "Selected for review" : option.validationValid ? `Review ${option.label}` : "Unavailable · validation failed"}
            </button>
          </article>
        ))}
      </div>

      <p className="comparison-caveat">Weather results are planning guidance, not a safety or washout guarantee. Coverage is shown separately from risk.</p>

      {customVisible && (
        <form className="custom-priorities" onSubmit={submitCustom}>
          <fieldset>
            <legend>Custom priorities</legend>
            <p>Adjust soft-constraint weights. Confirmed hard constraints never change.</p>
            <div className="priority-control-grid">
              {customControls.map(([name, label, value]) => (
                <label key={name}>{label}<span><input name={name} type="range" min="0" max="100" defaultValue={value} /><output>{value}</output></span></label>
              ))}
            </div>
          </fieldset>
          <button className="primary-action" type="submit" disabled={pending}>{pending ? "Solving and validating…" : "Generate custom schedule"}</button>
        </form>
      )}

      {selected && onApprove && displayedOptions.find((option) => option.profile === selected)?.draftId && (
        <ScheduleApprovalDialog
          profileLabel={displayedOptions.find((option) => option.profile === selected)!.label}
          pending={pending}
          onCancel={() => setSelected(null)}
          onApprove={async () => {
            const option = displayedOptions.find((item) => item.profile === selected)!;
            setPending(true);
            try {
              const version = await onApprove(option.draftId!);
              setApprovedVersion(version);
              setSelected(null);
            } catch (approvalError) {
              setError(approvalError instanceof Error ? approvalError.message : "Approval failed.");
            } finally {
              setPending(false);
            }
          }}
        />
      )}
      {approvedVersion && <div className="official-confirmation" role="status"><strong>Official Version {approvedVersion.versionNumber}</strong><span>Approved {new Date(approvedVersion.approvedAt).toLocaleString()}</span></div>}
    </section>
  );
}
