"use client";

import React, { useEffect, useState } from "react";

import { CrickOpsApiClient } from "@/lib/api-client";

import { ScheduleDiffRail } from "./schedule-diff-rail";

export function RepairReviewLive({ draftId }: { draftId: string }) {
  const [versions, setVersions] = useState<Array<{ id: string; number: number; label: string }>>([]);
  async function refreshVersions() {
    const items = await new CrickOpsApiClient().getScheduleVersions();
    setVersions(items.map((item) => ({ id: item.version_id, number: item.version_number, label: new Date(item.approved_at).toLocaleString() })));
  }
  useEffect(() => { void refreshVersions(); }, []);
  return <ScheduleDiffRail versions={versions} onApprove={async () => { await new CrickOpsApiClient().approveSchedule(draftId); await refreshVersions(); }} onReject={() => new CrickOpsApiClient().rejectSchedule(draftId)} onRestore={async (versionId) => { await new CrickOpsApiClient().restoreScheduleVersion(versionId); await refreshVersions(); }} />;
}
