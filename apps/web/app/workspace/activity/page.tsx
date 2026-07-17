import { ActivityTimelineLive } from "@/components/activity-timeline-live";
import { DirectorPanel } from "@/components/director-panel";
import { WorkspaceShell } from "@/components/workspace-shell";

export default function ActivityPage() {
  return <WorkspaceShell director={<DirectorPanel />}><ActivityTimelineLive /></WorkspaceShell>;
}
