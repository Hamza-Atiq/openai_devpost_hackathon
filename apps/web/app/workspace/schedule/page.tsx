import { DirectorPanel } from "@/components/director-panel";
import { ScheduleRail } from "@/components/schedule-rail";
import { WorkspaceShell } from "@/components/workspace-shell";

export default function SchedulePage() {
  return (
    <WorkspaceShell director={<DirectorPanel />}>
      <ScheduleRail status="official" version={2} />
    </WorkspaceShell>
  );
}
