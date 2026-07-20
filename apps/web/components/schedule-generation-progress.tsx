export type GenerationStage =
  | "idle"
  | "confirming"
  | "solving"
  | "validating"
  | "ready"
  | "failed";

type ScheduleGenerationProgressProps = {
  stage: GenerationStage;
  error?: string | null;
  evidence?: string[];
  remedies?: string[];
};

const stages = [
  ["confirming", "Confirming constraints", "Checking the saved revision and deterministic feasibility."],
  ["solving", "Solving three profiles", "Generating Balanced, Weather-first, and Fairness-first schedules."],
  ["validating", "Independently validating", "Verifying every hard constraint before any option is shown."],
] as const;

export function ScheduleGenerationProgress({ stage, error, evidence = [], remedies = [] }: ScheduleGenerationProgressProps) {
  if (stage === "idle") return null;
  const activeIndex = stages.findIndex(([name]) => name === stage);
  const busy = stage !== "ready" && stage !== "failed";

  return (
    <section className="generation-progress" aria-live="polite" aria-busy={busy}>
      {stage === "failed" ? (
        <div className="generation-failure" role="alert">
          <strong>Generation stopped safely</strong>
          <p>{error ?? "Review the setup and try again. No invalid schedule was created."}</p>
          {evidence.length > 0 && <><h3>Likely conflicts</h3><ul>{evidence.map((item) => <li key={item}>{item}</li>)}</ul></>}
          {remedies.length > 0 && <><h3>Ways to resolve this</h3><ul>{remedies.map((item) => <li key={item}>{item}</li>)}</ul></>}
          <a href="#format-teams">Edit tournament setup</a>
        </div>
      ) : (
        <>
          <div className="generation-progress-head">
            <span className="progress-pulse" aria-hidden="true" />
            <div>
              <strong>{stage === "ready" ? "Schedules ready" : "Building validated options"}</strong>
              <p>{stage === "ready" ? "Opening the comparison studio…" : "Keep this page open while CrickOps completes the real solver workflow."}</p>
            </div>
          </div>
          <ol>
            {stages.map(([name, label, detail], index) => {
              const complete = stage === "ready" || index < activeIndex;
              const active = name === stage;
              return (
                <li key={name} className={complete ? "complete" : active ? "active" : "pending"} aria-current={active ? "step" : undefined}>
                  <span aria-hidden="true">{complete ? "✓" : index + 1}</span>
                  <div><strong>{label}</strong><small>{detail}</small></div>
                </li>
              );
            })}
          </ol>
        </>
      )}
    </section>
  );
}
