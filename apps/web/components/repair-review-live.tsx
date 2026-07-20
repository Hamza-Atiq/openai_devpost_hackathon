"use client";

import React, { useEffect, useState } from "react";

import { CrickOpsApiClient } from "@/lib/api-client";
import { formatVenueDateTime } from "@/lib/venue-time";

import { ScheduleDiffRail } from "./schedule-diff-rail";

export function RepairReviewLive({ draftId }: { draftId: string }) {
  const [versions, setVersions] = useState<Array<{ id: string; number: number; label: string }>>([]);
  const [diff, setDiff] = useState<Awaited<ReturnType<CrickOpsApiClient["getScheduleDiff"]>> | null>(null);
  const [error, setError] = useState<string | null>(null);
  async function refreshVersions() {
    const items = await new CrickOpsApiClient().getScheduleVersions();
    setVersions(items.map((item) => ({ id: item.version_id, number: item.version_number, label: new Date(item.approved_at).toLocaleString() })));
  }
  useEffect(() => {
    let active = true;
    Promise.all([new CrickOpsApiClient().getScheduleDiff(draftId), new CrickOpsApiClient().getScheduleVersions()]).then(
      ([loadedDiff, items]) => { if (active) { setDiff(loadedDiff); setVersions(items.map((item) => ({ id: item.version_id, number: item.version_number, label: new Date(item.approved_at).toLocaleString() }))); } },
      (loadError: unknown) => { if (active) setError(loadError instanceof Error ? loadError.message : "The repair comparison could not be loaded."); },
    );
    return () => { active = false; };
  }, [draftId]);
  if (error) return <div className="operation-status operation-status-error" role="alert"><strong>Repair comparison unavailable</strong><p>{error}</p></div>;
  if (!diff) return <div className="operation-status" role="status">Loading the validated repair difference…</div>;
  const placementDetail = (placement: typeof diff.fixture_views[number]["before"]) => placement ? `${formatVenueDateTime(placement.starts_at, placement.timezone)} · ${placement.venue} · ${placement.timezone}` : "No placement";
  const fixtures = (change: typeof diff.fixture_views[number]["change"]) => diff.fixture_views.filter((item) => item.change === change).map((item) => ({ id: item.code, fixture: item.fixture, detail: change === "moved" ? `${placementDetail(item.before)} → ${placementDetail(item.after)}` : placementDetail(item.after ?? item.before) }));
  return <ScheduleDiffRail validated={diff.validation_valid} unchanged={fixtures("unchanged")} moved={fixtures("moved")} added={fixtures("added")} removed={fixtures("removed")} metricDeltas={diff.metric_deltas} versions={versions} onApprove={async () => { await new CrickOpsApiClient().approveSchedule(draftId); await refreshVersions(); }} onReject={() => new CrickOpsApiClient().rejectSchedule(draftId)} onRestore={async (versionId) => { await new CrickOpsApiClient().restoreScheduleVersion(versionId); await refreshVersions(); }} />;
}
