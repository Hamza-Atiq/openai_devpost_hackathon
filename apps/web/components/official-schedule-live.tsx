"use client";

import { useEffect, useState } from "react";

import { CrickOpsApiClient, type OfficialScheduleResponse } from "@/lib/api-client";
import type { ScheduleFixtureView } from "@/lib/schedule-view";

import { ScheduleRail } from "./schedule-rail";

type OfficialScheduleLiveProps = {
  initialSchedule?: OfficialScheduleResponse | null;
};

export function OfficialScheduleLive({ initialSchedule }: OfficialScheduleLiveProps) {
  const [schedule, setSchedule] = useState<OfficialScheduleResponse | null | undefined>(initialSchedule);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initialSchedule !== undefined) return;
    let active = true;
    new CrickOpsApiClient().getOfficialSchedule().then(
      (loaded) => { if (active) setSchedule(loaded); },
      (loadError: unknown) => { if (active) setError(loadError instanceof Error ? loadError.message : "The official schedule could not be loaded."); },
    );
    return () => { active = false; };
  }, [initialSchedule]);

  if (error) return <div className="operation-status operation-status-error" role="alert"><strong>Schedule unavailable</strong><p>{error}</p></div>;
  if (schedule === undefined) return <div className="operation-status" role="status">Loading the official workspace schedule…</div>;
  if (schedule === null) return <div className="operation-status"><strong>No official schedule yet</strong><p>Generate options, review the solver metrics, and explicitly approve one schedule.</p></div>;

  const fixtures: ScheduleFixtureView[] = schedule.fixtures.map((fixture) => ({
    id: fixture.code,
    stage: fixture.stage,
    home: fixture.home,
    away: fixture.away,
    venue: fixture.venue,
    startsAt: fixture.starts_at,
    timezone: fixture.timezone,
    validation: fixture.validation,
    change: "preserved",
  }));
  return <ScheduleRail status="official" version={schedule.version_number} fixtures={fixtures} />;
}
