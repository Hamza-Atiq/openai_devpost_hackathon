"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { CrickOpsApiClient } from "@/lib/api-client";

import { ProfileComparisonLive } from "./profile-comparison-live";
import { WeatherWorkspaceLive } from "./weather-workspace-live";

export function OptionsWorkspaceLive({ initialRunId }: { initialRunId?: string }) {
  const router = useRouter();
  const [runId, setRunId] = useState(initialRunId);
  const [resolved, setResolved] = useState(Boolean(initialRunId));

  useEffect(() => {
    if (initialRunId) return;
    let active = true;
    new CrickOpsApiClient().getLatestScheduleRun().then(
      (latest) => { if (active) { setRunId(latest.run_id); setResolved(true); } },
      () => { if (active) setResolved(true); },
    );
    return () => { active = false; };
  }, [initialRunId]);

  if (!resolved) {
    return <div className="operation-status" role="status">Restoring your latest validated options…</div>;
  }
  function handleRunChange(nextRunId: string) {
    setRunId(nextRunId);
    router.replace(`/workspace/options?run_id=${encodeURIComponent(nextRunId)}`);
  }

  return <><ProfileComparisonLive initialRunId={runId} onRunChange={handleRunChange} /><WeatherWorkspaceLive runId={runId} /></>;
}
