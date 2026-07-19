"use client";

import { useEffect, useState } from "react";

import { CrickOpsApiClient, type OfficialScheduleResponse, type OfficialScheduleVersion } from "@/lib/api-client";
import type { ScheduleFixtureView } from "@/lib/schedule-view";

import { ScheduleRail } from "./schedule-rail";
import { ScheduleVersionBrowser } from "./schedule-version-browser";

type OfficialScheduleLiveProps = {
  initialSchedule?: OfficialScheduleResponse | null;
  initialVersions?: OfficialScheduleVersion[];
};

export function OfficialScheduleLive({ initialSchedule, initialVersions = [] }: OfficialScheduleLiveProps) {
  const [schedule, setSchedule] = useState<OfficialScheduleResponse | null | undefined>(initialSchedule);
  const [versions, setVersions] = useState(initialVersions);
  const [currentId, setCurrentId] = useState(initialSchedule?.current_official ? initialSchedule.version_id : "");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initialSchedule !== undefined) return;
    let active = true;
    const client = new CrickOpsApiClient();
    Promise.all([client.getOfficialSchedule(), client.getScheduleVersions()]).then(
      ([loaded, history]) => {
        if (!active) return;
        setSchedule(loaded);
        setVersions(history);
        setCurrentId(loaded?.version_id ?? "");
      },
      (loadError: unknown) => {
        if (active) setError(loadError instanceof Error ? loadError.message : "The official schedule could not be loaded.");
      },
    );
    return () => { active = false; };
  }, [initialSchedule]);

  async function selectVersion(versionId: string) {
    setPending(true);
    setError(null);
    try { setSchedule(await new CrickOpsApiClient().getScheduleVersion(versionId)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "The selected version could not be loaded."); }
    finally { setPending(false); }
  }

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
  return (
    <>
      <ScheduleVersionBrowser versions={versions} selectedId={schedule.version_id} currentId={currentId || schedule.version_id} pending={pending} onSelect={(id) => void selectVersion(id)} />
      <ScheduleRail status={schedule.current_official === false ? "historical" : "official"} version={schedule.version_number} fixtures={fixtures} />
    </>
  );
}
