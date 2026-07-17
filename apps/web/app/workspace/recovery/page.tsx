import { DirectorPanel } from "@/components/director-panel";
import { DisruptionDeclaration } from "@/components/disruption-declaration";
import { WorkspaceShell } from "@/components/workspace-shell";

export default function RecoveryPage() {
  return <WorkspaceShell director={<DirectorPanel />}><DisruptionDeclaration officialVersion={2} /></WorkspaceShell>;
}
