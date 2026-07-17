import { DirectorPanel } from "@/components/director-panel";
import { ScheduleDiffRail } from "@/components/schedule-diff-rail";
import { RepairReviewLive } from "@/components/repair-review-live";
import { WorkspaceShell } from "@/components/workspace-shell";

export default async function RepairDiffPage({ searchParams }: { searchParams: Promise<{ draft?: string }> }) {
  const { draft } = await searchParams;
  return <WorkspaceShell director={<DirectorPanel />}>{draft ? <RepairReviewLive draftId={draft} /> : <ScheduleDiffRail />}</WorkspaceShell>;
}
