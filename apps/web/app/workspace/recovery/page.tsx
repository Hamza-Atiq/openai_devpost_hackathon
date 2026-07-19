import { DirectorPanel } from "@/components/director-panel";
import { DisruptionDeclarationLive } from "@/components/disruption-declaration-live";
import { WorkspaceShell } from "@/components/workspace-shell";

export default function RecoveryPage() {
  return <WorkspaceShell director={<DirectorPanel />}><DisruptionDeclarationLive /></WorkspaceShell>;
}
