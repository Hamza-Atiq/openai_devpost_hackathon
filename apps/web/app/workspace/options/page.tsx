import { DirectorPanel } from "@/components/director-panel";
import { ProfileComparisonLive } from "@/components/profile-comparison-live";
import { WeatherWorkspaceLive } from "@/components/weather-workspace-live";
import { WorkspaceShell } from "@/components/workspace-shell";

export default async function OptionsPage({
  searchParams,
}: {
  searchParams: Promise<{ run_id?: string }>;
}) {
  const { run_id: runId } = await searchParams;
  return (
    <WorkspaceShell director={<DirectorPanel />}>
      <ProfileComparisonLive initialRunId={runId} />
      <WeatherWorkspaceLive runId={runId} />
    </WorkspaceShell>
  );
}
