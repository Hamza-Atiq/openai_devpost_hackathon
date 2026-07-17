import { DirectorPanel } from "@/components/director-panel";
import { ProfileComparisonLive } from "@/components/profile-comparison-live";
import { WeatherRiskPanel } from "@/components/weather-risk-panel";
import { WorkspaceShell } from "@/components/workspace-shell";

export default function OptionsPage() {
  return (
    <WorkspaceShell director={<DirectorPanel />}>
      <ProfileComparisonLive />
      <WeatherRiskPanel />
    </WorkspaceShell>
  );
}
