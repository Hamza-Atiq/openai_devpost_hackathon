import { DirectorPanel } from "@/components/director-panel";
import { ProfileComparisonLive } from "@/components/profile-comparison-live";
import { WeatherRiskPanelLive } from "@/components/weather-risk-panel-live";
import { WeatherModeControls } from "@/components/weather-mode-controls";
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
      <WeatherRiskPanelLive runId={runId} />
      <WeatherModeControls />
    </WorkspaceShell>
  );
}
