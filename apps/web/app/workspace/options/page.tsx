import { DirectorPanel } from "@/components/director-panel";
import { OptionsWorkspaceLive } from "@/components/options-workspace-live";
import { WorkspaceShell } from "@/components/workspace-shell";

export default async function OptionsPage({
  searchParams,
}: {
  searchParams: Promise<{ run_id?: string }>;
}) {
  const { run_id: runId } = await searchParams;
  return (
    <WorkspaceShell director={<DirectorPanel />}>
      <OptionsWorkspaceLive initialRunId={runId} />
    </WorkspaceShell>
  );
}
