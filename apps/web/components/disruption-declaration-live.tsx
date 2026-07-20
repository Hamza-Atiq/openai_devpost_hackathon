"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { CrickOpsApiClient, type OfficialScheduleResponse } from "@/lib/api-client";
import { formatVenueDateTime } from "@/lib/venue-time";

import { DisruptionDeclaration } from "./disruption-declaration";

export function DisruptionDeclarationLive() {
  const router = useRouter();
  const [official, setOfficial] = useState<OfficialScheduleResponse | null | undefined>();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    new CrickOpsApiClient().getOfficialSchedule().then(
      (response) => { if (active) setOfficial(response); },
      (loadError: unknown) => {
        if (active) setError(loadError instanceof Error ? loadError.message : "The official schedule could not be loaded.");
      },
    );
    return () => { active = false; };
  }, []);

  if (error) return <div className="operation-status operation-status-error" role="alert"><strong>Recovery unavailable</strong><p>{error}</p></div>;
  if (official === undefined) return <div className="operation-status" role="status">Loading the latest official schedule…</div>;
  if (official === null) return <div className="operation-status operation-status-error" role="alert"><strong>Approve a schedule first</strong><p>Recovery must start from the latest official workspace schedule.</p></div>;

  const slots = official.fixtures.map((fixture) => ({
    id: fixture.slot_id,
    fixture: `${fixture.code} · ${fixture.home} vs ${fixture.away}`,
    venue: fixture.venue,
    localTime: `${formatVenueDateTime(fixture.starts_at, fixture.timezone)} · ${fixture.timezone}`,
  }));
  return (
    <DisruptionDeclaration
      officialVersion={official.version_number}
      slots={slots}
      onRepairReady={(draftId) => router.push(`/workspace/recovery/diff?draft=${encodeURIComponent(draftId)}`)}
    />
  );
}
