"use client";

import { useEffect, useState } from "react";

import { CrickOpsApiClient, type ScheduleWeatherResponse } from "@/lib/api-client";

import { WeatherRiskPanel } from "./weather-risk-panel";

export function WeatherRiskPanelLive({ runId, refreshVersion = 0 }: { runId?: string; refreshVersion?: number }) {
  const [weather, setWeather] = useState<ScheduleWeatherResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) return;
    let active = true;
    const client = new CrickOpsApiClient();
    client
      .getScheduleComparison(runId)
      .then((comparison) => {
        const draftId = comparison.options[0]?.draft_id;
        if (!draftId) {
          throw new Error("No validated schedule option is available for weather review.");
        }
        return client.getScheduleWeather(draftId);
      })
      .then(
        (response) => { if (active) setWeather(response); },
        (loadError: unknown) => {
          if (active) {
            setError(
              loadError instanceof Error
                ? loadError.message
                : "Weather evidence could not be loaded.",
            );
          }
        },
      );
    return () => { active = false; };
  }, [runId, refreshVersion]);

  if (!runId) {
    return <div className="operation-status"><strong>No schedule weather yet</strong><p>Generate schedule options to view fixture-level weather evidence.</p></div>;
  }
  if (error) {
    return <div className="operation-status operation-status-error" role="alert"><strong>Weather evidence unavailable</strong><p>{error}</p></div>;
  }
  if (!weather) {
    return <div className="operation-status" role="status">Loading real fixture weather evidence…</div>;
  }
  const issuedAt = weather.issued_at
    ? new Date(weather.issued_at).toLocaleString()
    : "Unavailable";
  return (
    <WeatherRiskPanel
      coverage={weather.coverage}
      issuedAt={issuedAt}
      stale={weather.quality === "stale"}
      provider={
        weather.provider ??
        (weather.mode === "deterministic" ? "Deterministic demo" : "Unavailable")
      }
      allocationMinutes={weather.allocation_minutes}
      fixtures={weather.fixtures.map((fixture) => ({
        id: fixture.id,
        label: fixture.label,
        venue: fixture.venue,
        startsAt: fixture.starts_at,
        timezone: fixture.timezone,
        risk: fixture.risk,
      }))}
    />
  );
}
