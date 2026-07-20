import { DirectorPanel } from "@/components/director-panel";
import { GuidedSetupLive } from "@/components/guided-setup-live";
import { SetupSectionNav } from "@/components/setup-section-nav";
import { WorkspaceShell } from "@/components/workspace-shell";

export default function SetupPage() {
  return (
    <WorkspaceShell director={<DirectorPanel />}>
      <section className="setup-intro" id="setup">
        <p className="eyebrow">Tournament setup</p>
        <h1>Confirm the playing field</h1>
        <p>
          Teams, venues, slots, and constraints will remain reviewable here before any
          schedule is generated.
        </p>
        <SetupSectionNav />
      </section>
      <GuidedSetupLive />
    </WorkspaceShell>
  );
}
