import { DirectorPanel } from "@/components/director-panel";
import { OfficialScheduleLive } from "@/components/official-schedule-live";
import { WorkspaceShell } from "@/components/workspace-shell";

export default function SchedulePage() {
  return (
    <WorkspaceShell director={<DirectorPanel />}>
      <OfficialScheduleLive />
    </WorkspaceShell>
  );
}
