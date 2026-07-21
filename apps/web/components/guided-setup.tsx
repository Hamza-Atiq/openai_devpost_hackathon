"use client";

import { useMemo, useState } from "react";

import { ApiProblemError, CrickOpsApiClient } from "@/lib/api-client";
import {
  draftFromSetup,
  defaultSetupTeams,
  type SetupSaveState,
  type SetupTeamValue,
  type SetupVenueValue,
  type TournamentSetupSaveInput,
  type TournamentSetupView,
} from "@/lib/setup-contract";
import { allocationMinutes, type MatchFormatPreset } from "@/lib/setup-state";
import { parseCoordinateInput, type CoordinateKind } from "@/lib/coordinate-input";

type GuidedSetupProps = {
  conflict?: "stale" | null;
  revision?: number;
  apiClient?: Pick<CrickOpsApiClient, "confirmSetup">;
  initialSetup?: TournamentSetupView;
  saveState?: SetupSaveState;
  onDraftChange?: (draft: TournamentSetupSaveInput) => void;
  onConfirmAndGenerate?: (input: {
    confirmation: true;
    expected_revision: number;
    selection: { match_format_preset: MatchFormatPreset; allocation_minutes: number };
  }) => Promise<void>;
};

const competitionInvariants = [
  ["Fixed competition structure", "8 teams · 2 groups · 15 fixtures", "System invariant"],
  ["Daily team limit", "A team plays at most once per local calendar day", "System invariant"],
  ["Knockout chronology", "Groups → semifinals → final", "System invariant"],
] as const;

function fallbackDraft(revision: number): TournamentSetupSaveInput {
  const venue = (name: string): SetupVenueValue => ({
    display_name: name,
    city: "Auckland",
    country_code: "NZ",
    latitude: -36.8485,
    longitude: 174.7633,
    iana_time_zone: "Pacific/Auckland",
  });
  return {
    expected_revision: revision,
    match_format_preset: "T20",
    start_date: "2026-09-07",
    end_date: "2026-09-20",
    venues: [venue("Harbour Oval"), venue("Riverside Cricket Ground")],
    teams: defaultSetupTeams(),
    weekday_start_times: ["18:00"],
    weekend_start_times: ["10:00", "18:00"],
    blackout_dates: [],
    minimum_rest_minutes: 0,
    priorities: {
      minimize_weather_risk: true,
      maximize_fair_rest: true,
      balance_venue_allocation: true,
      prefer_selected_time_slots: true,
      minimize_schedule_changes: true,
    },
  };
}

export function GuidedSetup({
  conflict = null,
  revision = 0,
  apiClient = new CrickOpsApiClient(),
  initialSetup,
  saveState = "saved",
  onDraftChange,
  onConfirmAndGenerate,
}: GuidedSetupProps) {
  const [draft, setDraft] = useState<TournamentSetupSaveInput>(
    initialSetup ? draftFromSetup(initialSetup) : fallbackDraft(revision),
  );
  const [manualCoordinates, setManualCoordinates] = useState(Boolean(initialSetup));
  const [coordinateText, setCoordinateText] = useState(() =>
    (initialSetup?.venues ?? fallbackDraft(revision).venues).map((venue) => ({
      latitude: String(venue.latitude),
      longitude: String(venue.longitude),
    })),
  );
  const [coordinateErrors, setCoordinateErrors] = useState<Record<string, string>>({});
  const [confirmed, setConfirmed] = useState(false);
  const [restHoursText, setRestHoursText] = useState(() => String((initialSetup?.setup_draft.minimum_rest_minutes ?? 0) / 60));
  const [setupStatus, setSetupStatus] = useState<
    "pending" | "saving" | "ready" | "error"
  >("pending");
  const [staleConflict, setStaleConflict] = useState(conflict === "stale");
  const allocation = useMemo(
    () => allocationMinutes(draft.match_format_preset),
    [draft.match_format_preset],
  );
  const parsedRestHours = Number(restHoursText);
  const restHoursValid = /^\d+$/.test(restHoursText) && Number.isInteger(parsedRestHours) && parsedRestHours >= 0 && parsedRestHours <= 168;
  const coordinatesValid = Object.keys(coordinateErrors).length === 0;
  const constraintLedger = useMemo(
    () => [
      ...competitionInvariants,
      [
        "Minimum rest",
        draft.minimum_rest_minutes > 0
          ? `${draft.minimum_rest_minutes} minutes across group and knockout paths`
          : "No additional minimum rest configured",
        draft.minimum_rest_minutes > 0 ? "Organizer hard constraint" : "Not configured",
      ],
      ["Audience timing", "Prefer selected prime-time and weekend slots", "Soft preference"],
    ],
    [draft.minimum_rest_minutes],
  );

  function updateDraft(
    update: (current: TournamentSetupSaveInput) => TournamentSetupSaveInput,
  ) {
    setDraft((current) => {
      const next = update(current);
      onDraftChange?.(next);
      return next;
    });
  }

  function updateVenue(index: number, update: Partial<SetupVenueValue>) {
    updateDraft((current) => ({
      ...current,
      venues: current.venues.map((venue, venueIndex) =>
        venueIndex === index ? { ...venue, ...update } : venue,
      ) as [SetupVenueValue, SetupVenueValue],
    }));
  }

  function commitCoordinate(index: number, kind: CoordinateKind) {
    const key = `${index}-${kind}`;
    const parsed = parseCoordinateInput(coordinateText[index][kind], kind);
    if ("error" in parsed) {
      setCoordinateErrors((current) => ({ ...current, [key]: parsed.error }));
      return;
    }
    setCoordinateErrors((current) => {
      const next = { ...current };
      delete next[key];
      return next;
    });
    updateVenue(index, { [kind]: parsed.value });
  }

  function updateTeam(teamId: string, update: Partial<SetupTeamValue>) {
    updateDraft((current) => ({
      ...current,
      teams: current.teams.map((team) => team.id === teamId ? { ...team, ...update } : team),
    }));
  }

  function swapTeams(teamId: string, otherId: string) {
    if (!otherId) return;
    updateDraft((current) => {
      const team = current.teams.find((item) => item.id === teamId);
      const other = current.teams.find((item) => item.id === otherId);
      if (!team || !other || team.group_id === other.group_id) return current;
      return {
        ...current,
        teams: current.teams.map((item) =>
          item.id === teamId ? { ...item, group_id: other.group_id }
          : item.id === otherId ? { ...item, group_id: team.group_id }
          : item,
        ),
      };
    });
  }

  async function confirmHardConstraints() {
    setSetupStatus("saving");
    setStaleConflict(false);
    try {
      const input = {
        confirmation: true,
        expected_revision: draft.expected_revision,
        selection: {
          match_format_preset: draft.match_format_preset,
          allocation_minutes: allocation,
        },
      } as const;
      if (onConfirmAndGenerate) {
        await onConfirmAndGenerate(input);
        setSetupStatus("ready");
      } else {
        const result = await apiClient.confirmSetup(input);
        setSetupStatus(result.ready ? "ready" : "error");
      }
    } catch (error) {
      if (error instanceof ApiProblemError && error.code === "stale_tournament_revision") {
        setStaleConflict(true);
      }
      setSetupStatus("error");
    }
  }

  return (
    <div className="guided-setup">
      {staleConflict && (
        <div className="conflict-banner" role="alert">
          <div>
            <strong>Tournament setup changed in another request</strong>
            <span>Review the latest saved revision before confirming constraints.</span>
          </div>
          <button type="button" onClick={() => window.location.reload()}>
            Reload latest setup
          </button>
        </div>
      )}

      <section className="setup-block" id="format-and-teams" aria-labelledby="format-heading">
        <div className="block-heading">
          <span>01 / Playing format</span>
          <div>
            <h2 id="format-heading">Set the match footprint</h2>
            <p>One preset applies to every fixture.</p>
          </div>
        </div>
        <fieldset className="format-switch">
          <legend>Match-format preset</legend>
          {(["T10", "T20"] as MatchFormatPreset[]).map((preset) => (
            <label
              key={preset}
              className={draft.match_format_preset === preset ? "selected" : undefined}
            >
              <input
                type="radio"
                name="format"
                value={preset}
                checked={draft.match_format_preset === preset}
                onChange={() =>
                  updateDraft((current) => ({
                    ...current,
                    match_format_preset: preset,
                  }))
                }
              />
              <strong>{preset}</strong>
              <span>{allocationMinutes(preset)}-minute operational venue allocation</span>
            </label>
          ))}
        </fieldset>
        <p className="allocation-note">
          <b>{allocation} minutes reserved per fixture.</b> This planning allocation
          includes play, intervals, setup, and turnover; it is not a guaranteed match
          duration.
        </p>
        <div className="team-editor">
          <h3>Edit teams and groups</h3>
          <p>Rename teams or swap one team with a team in the other group. Each group always keeps four teams.</p>
          <div className="team-groups">
            {(["A", "B"] as const).map((code) => {
              const groupId = initialSetup?.groups?.find((group) => group.code === code)?.id
                ?? (code === "A" ? draft.teams[0]?.group_id : draft.teams[4]?.group_id);
              const members = draft.teams.filter((team) => team.group_id === groupId);
              const others = draft.teams.filter((team) => team.group_id !== groupId);
              return <fieldset key={code}><legend>Group {code}</legend>{members.map((team) => <div key={team.id} className="team-editor-row"><label>Team display name<input value={team.display_name} onChange={(event) => updateTeam(team.id, { display_name: event.target.value })} /></label><label>Swap group with<select aria-label={`Swap ${team.display_name} group with`} defaultValue="" onChange={(event) => { swapTeams(team.id, event.target.value); event.currentTarget.value = ""; }}><option value="">Choose team</option>{others.map((other) => <option key={other.id} value={other.id}>{other.display_name}</option>)}</select></label></div>)}</fieldset>;
            })}
          </div>
        </div>
      </section>

      <section className="setup-block" id="venues-and-location" aria-labelledby="venue-heading">
        <div className="block-heading">
          <span>02 / Ground coordinates</span>
          <div>
            <h2 id="venue-heading">Confirm two operating venues</h2>
            <p>The venue name and geographic location stay separate.</p>
          </div>
        </div>
        <div className="venue-board">
          {draft.venues.map((venue, index) => (
            <fieldset className="venue-card" key={`venue-${index + 1}`}>
              <legend>Venue {index + 1}</legend>
              <label>
                Venue display name
                <input
                  name={`venue-${index + 1}-name`}
                  value={venue.display_name}
                  onChange={(event) => updateVenue(index, { display_name: event.target.value })}
                />
              </label>
              <label>
                City, country, area, or postal code
                <input
                  name={`venue-${index + 1}-query`}
                  value={venue.city}
                  onChange={(event) => updateVenue(index, { city: event.target.value })}
                />
              </label>
              <div className="location-status">
                <span aria-hidden="true">◎</span>
                <p>
                  <b>Coordinates ready for review</b>
                  <small>Edits are not treated as confirmed until they save successfully.</small>
                </p>
              </div>
              {manualCoordinates && (
                <div className="coordinate-grid">
                  <label>
                    Country code
                    <input
                      name={`venue-${index + 1}-country`}
                      maxLength={2}
                      value={venue.country_code}
                      onChange={(event) =>
                        updateVenue(index, { country_code: event.target.value.toUpperCase() })
                      }
                    />
                  </label>
                  <label>
                    Latitude
                    <input
                      name={`venue-${index + 1}-latitude`}
                      inputMode="decimal"
                      value={coordinateText[index].latitude}
                      aria-invalid={Boolean(coordinateErrors[`${index}-latitude`])}
                      aria-describedby={`venue-${index + 1}-latitude-help`}
                      onChange={(event) => setCoordinateText((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, latitude: event.target.value } : item))}
                      onBlur={() => commitCoordinate(index, "latitude")}
                    />
                    <small id={`venue-${index + 1}-latitude-help`}>{coordinateErrors[`${index}-latitude`] ?? "Enter a decimal from -90 to 90."}</small>
                  </label>
                  <label>
                    Longitude
                    <input
                      name={`venue-${index + 1}-longitude`}
                      inputMode="decimal"
                      value={coordinateText[index].longitude}
                      aria-invalid={Boolean(coordinateErrors[`${index}-longitude`])}
                      aria-describedby={`venue-${index + 1}-longitude-help`}
                      onChange={(event) => setCoordinateText((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, longitude: event.target.value } : item))}
                      onBlur={() => commitCoordinate(index, "longitude")}
                    />
                    <small id={`venue-${index + 1}-longitude-help`}>{coordinateErrors[`${index}-longitude`] ?? "Enter a decimal from -180 to 180."}</small>
                  </label>
                </div>
              )}
            </fieldset>
          ))}
        </div>
        {!manualCoordinates && <p className="field-help">Manual coordinates accept decimals: Enter a decimal from -90 to 90 latitude and Enter a decimal from -180 to 180 longitude.</p>}
        <button
          className="text-action"
          type="button"
          aria-expanded={manualCoordinates}
          onClick={() => setManualCoordinates((value) => !value)}
        >
          {manualCoordinates ? "Hide manual coordinates" : "Use manual coordinates"}
        </button>
        <label className="timezone-field">
          Shared tournament timezone
          <input
            value={draft.venues[0].iana_time_zone}
            onChange={(event) =>
              updateDraft((current) => ({
                ...current,
                venues: current.venues.map((item) => ({
                  ...item,
                  iana_time_zone: event.target.value,
                })) as [SetupVenueValue, SetupVenueValue],
              }))
            }
            aria-describedby="timezone-help"
          />
          <small id="timezone-help">
            Both venues must use the same confirmed IANA timezone in Version 1.
          </small>
        </label>
      </section>

      <section className="setup-block" id="dates-and-slots" aria-labelledby="slot-heading">
        <div className="block-heading">
          <span>03 / Fixture strip</span>
          <div>
            <h2 id="slot-heading">Shape the tournament window</h2>
            <p>Define local start patterns; the selected allocation controls overlap and capacity.</p>
          </div>
        </div>
        <div className="date-grid">
          <label>
            Tournament starts
            <input
              type="date"
              value={draft.start_date}
              onChange={(event) =>
                updateDraft((current) => ({ ...current, start_date: event.target.value }))
              }
            />
          </label>
          <label>
            Tournament ends
            <input
              type="date"
              value={draft.end_date}
              onChange={(event) =>
                updateDraft((current) => ({ ...current, end_date: event.target.value }))
              }
            />
          </label>
          <label>
            Venue blackout date
            <input
              type="date"
              value={draft.blackout_dates[0] ?? ""}
              onChange={(event) =>
                updateDraft((current) => ({
                  ...current,
                  blackout_dates: event.target.value ? [event.target.value] : [],
                }))
              }
            />
          </label>
        </div>
        <div className="slot-pattern">
          <div>
            <span>MON—FRI</span>
            <label>
              Weekday start time
              <input
                type="time"
                value={draft.weekday_start_times[0] ?? ""}
                onChange={(event) =>
                  updateDraft((current) => ({
                    ...current,
                    weekday_start_times: [event.target.value],
                  }))
                }
              />
            </label>
          </div>
          <div>
            <span>SAT—SUN</span>
            <label>
              Weekend start times
              <input
                value={draft.weekend_start_times.join(", ")}
                onChange={(event) =>
                  updateDraft((current) => ({
                    ...current,
                    weekend_start_times: event.target.value
                      .split(",")
                      .map((value) => value.trim())
                      .filter(Boolean),
                  }))
                }
              />
            </label>
          </div>
          <div className="slot-readout">
            <small>Current allocation</small>
            <strong>{draft.match_format_preset} / {allocation} min</strong>
            <span>No individual duration overrides</span>
          </div>
        </div>
      </section>

      <section className="ledger" id="constraints" aria-labelledby="ledger-heading">
        <div className="ledger-head">
          <div>
            <p className="eyebrow">Authoritative review</p>
            <h2 id="ledger-heading">Constraint Ledger</h2>
          </div>
          <span>{constraintLedger.length} review items</span>
        </div>
        <div className="ledger-list">
          {constraintLedger.map(([name, detail, kind]) => (
            <div className="ledger-row" key={name}>
              <span
                className={`ledger-rule-status ${kind === "Soft preference" ? "rule-soft" : "rule-hard"}`}
              >
                {kind}
              </span>
              <div className="ledger-rule-content">
                <strong>{name}</strong>
                <p>{detail}</p>
              </div>
            </div>
          ))}
        </div>
        <label className="timezone-field">
          Minimum rest in hours
          <input
            type="number"
            min="0"
            max="168"
            value={restHoursText}
            aria-invalid={!restHoursValid}
            aria-describedby="minimum-rest-help"
            onChange={(event) => {
              const next = event.target.value;
              setRestHoursText(next);
              const hours = Number(next);
              if (/^\d+$/.test(next) && Number.isInteger(hours) && hours >= 0 && hours <= 168) {
                updateDraft((current) => ({ ...current, minimum_rest_minutes: hours * 60 }));
              }
            }}
          />
          <small id="minimum-rest-help">{restHoursValid ? "Enter a whole number from 0 to 168 hours." : "Minimum rest must be a whole number from 0 to 168 hours. This value has not been saved."}</small>
        </label>
        <p className="setup-save-status" aria-live="polite">
          {saveState === "saved" && "All changes saved"}
          {saveState === "dirty" && "Unsaved changes"}
          {saveState === "saving" && "Saving setup changes…"}
          {saveState === "error" && "Changes could not be saved. Your draft remains in this browser."}
        </p>
        <label className="confirm-check">
          <input
            type="checkbox"
            checked={confirmed}
            onChange={(event) => setConfirmed(event.target.checked)}
          />
          <span>I reviewed the hard constraints and confirm they reflect the tournament.</span>
        </label>
        <p className="setup-confirm-status" aria-live="polite">
          {setupStatus === "pending" && "Confirmation pending"}
          {setupStatus === "saving" && "Checking confirmed constraints…"}
          {setupStatus === "ready" && "Setup ready for schedule generation"}
          {setupStatus === "error" && !staleConflict &&
            "Setup is not ready. Review the highlighted requirements and try again."}
        </p>
        <button
          className="primary-action"
          type="button"
          disabled={!confirmed || !restHoursValid || !coordinatesValid || setupStatus === "saving" || saveState !== "saved"}
          onClick={() => void confirmHardConstraints()}
        >
          Confirm and generate schedules
        </button>
      </section>
    </div>
  );
}
