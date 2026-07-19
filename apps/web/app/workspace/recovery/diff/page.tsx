import { DirectorPanel } from "@/components/director-panel";
import { RepairReviewLive } from "@/components/repair-review-live";
import { WorkspaceShell } from "@/components/workspace-shell";

export default async function RepairDiffPage({ searchParams }: { searchParams: Promise<{ draft?: string }> }) {
  const { draft } = await searchParams;
  return <WorkspaceShell director={<DirectorPanel />}>{draft ? <RepairReviewLive draftId={draft} /> : <div className="operation-status operation-status-error" role="alert"><strong>No repair draft selected</strong><p>Declare a disruption and generate a validated repair before reviewing differences.</p></div>}</WorkspaceShell>;
}
