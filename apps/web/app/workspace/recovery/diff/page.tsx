import { DirectorPanel } from "@/components/director-panel";
import { ScheduleDiffRail } from "@/components/schedule-diff-rail";
import { WorkspaceShell } from "@/components/workspace-shell";

export default function RepairDiffPage() {
  return <WorkspaceShell director={<DirectorPanel />}><ScheduleDiffRail /></WorkspaceShell>;
}
