import {
  groupFixturesByLocalDate,
  localTimeLabel,
  type ScheduleFixtureView,
} from "@/lib/schedule-view";

type ScheduleRailProps = {
  status: "official" | "draft";
  version: number;
  repair?: boolean;
  fixtures?: ScheduleFixtureView[];
};

const teams = ["Falcons", "Mariners", "Strikers", "Royals", "Blues", "Lions", "Titans", "United"];
const groupFixtures: ScheduleFixtureView[] = Array.from({ length: 12 }, (_, index) => ({
  id: `G${String(index + 1).padStart(2, "0")}`,
  stage: "group",
  home: teams[index % 8],
  away: teams[(index + 3) % 8],
  venue: index % 2 === 0 ? "National Cricket Ground" : "Riverside Oval",
  startsAt: `2026-09-${String(7 + Math.floor(index / 2)).padStart(2, "0")}T${index % 2 === 0 ? "10:00" : "18:00"}:00+05:00`,
  timezone: "Asia/Karachi",
  validation: "valid",
  change: index === 3 ? "changed" : "preserved",
}));

const defaultFixtures: ScheduleFixtureView[] = [
  ...groupFixtures,
  { id: "SF1", stage: "semifinal", home: "Group A Winner", away: "Group B Runner-up", venue: "National Cricket Ground", startsAt: "2026-09-15T10:00:00+05:00", timezone: "Asia/Karachi", validation: "valid", change: "preserved" },
  { id: "SF2", stage: "semifinal", home: "Group B Winner", away: "Group A Runner-up", venue: "Riverside Oval", startsAt: "2026-09-15T18:00:00+05:00", timezone: "Asia/Karachi", validation: "valid", change: "preserved" },
  { id: "F", stage: "final", home: "Semifinal 1 Winner", away: "Semifinal 2 Winner", venue: "National Cricket Ground", startsAt: "2026-09-18T18:00:00+05:00", timezone: "Asia/Karachi", validation: "valid", change: "new" },
];

const stageName = { group: "Group stage", semifinal: "Semifinal", final: "Final" } as const;
const changeName = { preserved: "Preserved fixture", changed: "Changed fixture", new: "New placement" } as const;

export function ScheduleRail({ status, version, repair = false, fixtures = defaultFixtures }: ScheduleRailProps) {
  const groups = groupFixturesByLocalDate(fixtures);
  const timezone = fixtures[0]?.timezone ?? "Asia/Karachi";

  return (
    <section className="schedule-board" aria-labelledby="schedule-title">
      <header className="schedule-board-head">
        <div>
          <p className="eyebrow">Schedule control</p>
          <h1 id="schedule-title">The Schedule Rail</h1>
          <p>{status === "official" ? "Official workspace schedule" : "Draft repair — not official"} · Version {version}</p>
        </div>
        <div className="schedule-controls">
          <label>Schedule version<select defaultValue={String(version)}><option value="2">Version 2 — official</option><option value="3">Version 3 — draft</option></select></label>
          <span className="validation-badge"><b aria-hidden="true">✓</b> Independently validated</span>
        </div>
      </header>

      <div className="rail-key" aria-label="Schedule legend">
        <span><i className="key-official" aria-hidden="true" />{status === "official" ? "Official baseline" : "Draft candidate"}</span>
        {repair && <><span><i className="key-preserved" aria-hidden="true" />Preserved fixture</span><span><i className="key-changed" aria-hidden="true" />Changed fixture</span></>}
        <span className="timezone-key">Local times · {timezone}</span>
      </div>

      <ol className="schedule-rail" aria-label={`Version ${version} fixtures in chronological order`}>
        {groups.map((group, groupIndex) => {
          const stage = group.fixtures[0].stage;
          const priorStage = groupIndex > 0 ? groups[groupIndex - 1].fixtures[0].stage : null;
          return (
            <li className="rail-day" key={group.date}>
              {stage === "semifinal" && priorStage === "group" && <div className="stage-gate" role="note"><span>Stage gate</span><strong>Group stage complete</strong><small>All 12 group fixtures finish before either semifinal begins.</small></div>}
              {stage === "final" && priorStage === "semifinal" && <div className="stage-gate" role="note"><span>Stage gate</span><strong>Semifinals complete</strong><small>Both semifinal allocations finish before the final begins.</small></div>}
              <div className="day-label"><time dateTime={group.date}>{new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "2-digit", month: "short", timeZone: timezone }).format(new Date(`${group.date}T12:00:00+05:00`))}</time><span>{stageName[stage]}</span></div>
              <div className="day-fixtures">
                {group.fixtures.map((fixture) => (
                  <article className={`fixture-card fixture-${fixture.change}`} key={fixture.id}>
                    <div className="fixture-meta"><span>{fixture.id}</span><span>{stageName[fixture.stage]}</span>{repair && <b>{changeName[fixture.change]}</b>}</div>
                    <div className="fixture-time"><time dateTime={fixture.startsAt}>{localTimeLabel(fixture.startsAt, fixture.timezone)}</time><span>{fixture.timezone}</span></div>
                    <div className="fixture-teams"><strong>{fixture.home}</strong><i>vs</i><strong>{fixture.away}</strong></div>
                    <footer><span>{fixture.venue}</span><span>✓ Valid</span></footer>
                  </article>
                ))}
              </div>
            </li>
          );
        })}
      </ol>

      {status === "draft" && (
        <div className="schedule-approval">
          <div><strong>Set Version {version} as the official workspace schedule?</strong><span>The current Version 2 remains preserved in activity history.</span></div>
          <button className="secondary-action" type="button">Keep Version 2 official</button>
          <button className="primary-action" type="button">Approve schedule</button>
        </div>
      )}
    </section>
  );
}
