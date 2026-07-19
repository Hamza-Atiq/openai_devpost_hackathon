# Setup-to-Schedule Recovery Design

**Status:** Approved in conversation on 2026-07-19

## Problem

The deployed guided setup presents editable controls that are not connected to authoritative workspace state. Confirming setup sends only the match-format preset, does not start a schedule run, and leaves the organizer without a next action. Navigation remounts the form with generic defaults. The Schedule page always renders bundled fixtures labelled as an official Version 2, even when the workspace has no approved schedule.

This violates FR-004–FR-009, FR-025, UX-002, UX-006, UX-008, UX-011, DATA-001–DATA-003, AC-002, AC-016, Quality Gate 13, and Quality Gate 14.

## Design goals

1. The selected sample is the initial value of every setup control.
2. Every organizer edit is represented in one typed setup draft and persisted to the guest workspace.
3. Navigation and refresh restore that draft.
4. Confirmation validates the exact saved revision and starts genuine three-profile generation through one explicit action.
5. The organizer sees named progress, success, infeasibility, and retry states.
6. Options and official schedules are rendered only from backend results.
7. No official schedule is implied before explicit approval.
8. Dates, venues, slots, format, blackout periods, and preferences used by the solver match what the organizer reviewed.

## Interaction model

### Loading and editing

`/workspace/setup` loads `GET /api/v1/tournament` before rendering editable controls. A typed `SetupDraft` is initialized from that response. Fields remain controlled React values, never isolated `defaultValue` inputs.

After a valid field change, a debounced save sends the complete editable setup command with the last observed revision. The page shows one of four persistent states: `Saved`, `Unsaved changes`, `Saving…`, or `Could not save`. Navigation is permitted while saving, but the shared workspace provider flushes a pending save before route change where possible. A page reload always restores the last successful server revision.

### Venue confirmation and slots

Venue display name stays separate from location information. Manual coordinates require display name, city, two-letter country code, latitude, longitude, and shared IANA timezone. Confirmation creates typed venues and rebuilds venue slots from the organizer’s date window, weekday start time, weekend start times, blackout date, and selected T10/T20 allocation.

Slot expansion is backend-owned so UTC conversion, local dates, allocation duration, overlap, blackout handling, and deterministic validation do not depend on browser calculations. The API returns the expanded slot count and readiness evidence.

### Confirmation and generation

The final primary action is **Confirm and generate schedules**. It executes this ordered workflow:

1. Flush and persist the current setup draft.
2. Run deterministic readiness checks against the saved revision.
3. Require explicit hard-constraint confirmation.
4. Start one schedule run for Balanced, Weather-first, and Fairness-first.
5. Observe run progress through the existing event/status contract.
6. Fetch the validated comparison only after all required options are ready.
7. Navigate to `/workspace/options?run_id=…`.

The progress panel names the current stage: `Saving setup`, `Checking capacity`, `Generating three schedules`, `Independently validating`, and `Preparing comparison`. The action is idempotent and cannot be double-submitted.

Infeasibility replaces progress with deterministic evidence and concrete remedies. Unexpected failure preserves the saved setup and offers retry. Neither state displays a schedule.

### Options and official schedule

The Options route loads the run identified in the URL or the latest ready run in workspace state. It never fabricates empty profile cards. Approval remains an explicit backend command.

The Schedule route loads `GET /schedule-versions` and the current official schedule payload. With no approved version it displays an honest empty state with one action: `Compare schedule options`. After approval it renders exactly 15 backend placements with their actual teams, venues, local times, timezone, validation status, version, and approval timestamp.

Bundled fixtures may remain only as explicit test fixtures passed through component props; they are not production defaults.

## Backend contracts

Introduce strict commands rather than accepting raw dictionaries:

- `TournamentSetupDraftInput`: preset, venue inputs, date window, weekday/weekend start patterns, blackout dates, minimum rest, and priority toggles.
- `TournamentSetupView`: normalized editable fields, revision, save state, expanded slot count, and confirmation state.
- `SetupSaveResult`: normalized tournament plus deterministic draft validation findings.
- `OfficialScheduleView`: official version metadata, validation metadata, and 15 fixture views.

`PUT /tournament` requires the expected revision and an idempotency key. It validates the fixed Version 1 format, builds normalized venues and slots, increments the revision, marks constraints unconfirmed when an authoritative field changes, persists the workspace, and appends an audit event without logging sensitive content.

`POST /tournament/precheck` must run the real pre-solver checks. It cannot return ready merely because a confirmation flag exists.

`POST /schedule-runs` must require `READY_TO_SCHEDULE`, a matching confirmed revision, and a valid precheck before solving.

## State ownership

- PostgreSQL-backed guest workspace state is authoritative.
- The React draft is an editable projection of one server revision.
- The URL carries the active schedule-run identifier.
- Generated drafts and official versions remain backend-owned.
- A 409 revision conflict never silently overwrites another saved revision; the UI reloads the server version and explains the conflict.

## Error and accessibility behavior

- All save and generation state changes use an `aria-live` status region.
- The primary action retains focus while its label and disabled state change.
- Field errors are associated with the corresponding control.
- Progress never relies on animation or color alone.
- Browser navigation cannot expose a fake official schedule.
- Safe error copy contains a correlation ID but no stack trace, prompt, token, or provider secret.

## Verification strategy

The first failing tests reproduce the deployed defect rather than rendering isolated components:

1. Load the Pakistan sample and assert its real venue/date values appear in Setup.
2. Edit preset, venues, coordinates, date window, blackout, and slot patterns; navigate away and return; assert values persist.
3. Confirm and generate; assert a schedule run is created and named progress is visible.
4. Assert the generated option placements use the saved venue/date/slot configuration.
5. Assert Schedule shows an empty state before approval.
6. Approve one option; assert Schedule renders the backend official version and all 15 placements.
7. Refresh and assert setup, run, drafts, approval, and official fixtures persist.
8. Seed infeasible capacity and assert no option or official schedule appears.

Component tests remain useful for rendering states, but Quality Gates 13 and 14 require API-backed browser tests with no direct route-skipping.

## Known adjacent defect

The Tournament Director and six specialist agents are still disconnected from the organizer request path. This recovery does not disguise that defect. After the deterministic setup-to-schedule path is reliable, the agent orchestration will be connected as a separate test-first change while deterministic services retain fixture authority.
