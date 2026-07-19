"use client";

import { useEffect, useState } from "react";

import { CrickOpsApiClient, type WeatherStatus } from "@/lib/api-client";

import { WeatherModeControls } from "./weather-mode-controls";
import { WeatherRiskPanelLive } from "./weather-risk-panel-live";

export function WeatherWorkspaceLive({
  runId,
  initialStatus,
}: {
  runId?: string;
  initialStatus?: WeatherStatus;
}) {
  const [status, setStatus] = useState<WeatherStatus | null>(initialStatus ?? null);
  const [refreshVersion, setRefreshVersion] = useState(0);

  useEffect(() => {
    if (initialStatus) return;
    let active = true;
    new CrickOpsApiClient().getWeather().then(
      (weather) => { if (active) setStatus(weather); },
      () => { if (active) setStatus({ mode: "live", quality: "unavailable" }); },
    );
    return () => { active = false; };
  }, [initialStatus]);

  if (!status) {
    return <div className="operation-status" role="status">Loading saved weather mode…</div>;
  }

  return (
    <>
      <WeatherRiskPanelLive runId={runId} refreshVersion={refreshVersion} />
      <WeatherModeControls
        key={`${status.mode}:${status.quality}`}
        initialMode={status.mode}
        initialProviderUnavailable={status.quality === "unavailable"}
        onModeChanged={(next) => {
          setStatus(next);
          setRefreshVersion((version) => version + 1);
        }}
      />
      {status.quality === "refresh_required" && (
        <div className="weather-warning" role="status">
          <strong>Weather refresh required</strong>
          <span>{status.invalidation_reason ?? "Tournament inputs changed. Refresh weather before relying on risk guidance."}</span>
        </div>
      )}
      {refreshVersion > 0 && runId && (
        <div className="weather-warning" role="status">
          <strong>Weather evidence updated</strong>
          <span>Regenerate schedules to update profile comparison metrics.</span>
        </div>
      )}
    </>
  );
}
