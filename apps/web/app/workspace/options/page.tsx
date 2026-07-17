import { DirectorPanel } from "@/components/director-panel";
import { ProfileComparisonLive } from "@/components/profile-comparison-live";
import { WorkspaceShell } from "@/components/workspace-shell";

export default function OptionsPage() {
  return (
    <WorkspaceShell director={<DirectorPanel />}>
      <ProfileComparisonLive />
    </WorkspaceShell>
  );
}
