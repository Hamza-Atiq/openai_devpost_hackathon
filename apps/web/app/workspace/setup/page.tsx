import { DirectorPanel } from "@/components/director-panel";
import { GuidedSetupLive } from "@/components/guided-setup-live";
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
        <ol className="setup-steps" aria-label="Setup progress">
          <li aria-current="step"><b>01</b><span>Format and teams</span></li>
          <li><b>02</b><span>Venues and location</span></li>
          <li><b>03</b><span>Dates and slots</span></li>
          <li><b>04</b><span>Constraints</span></li>
        </ol>
      </section>
      <GuidedSetupLive />
    </WorkspaceShell>
  );
}
