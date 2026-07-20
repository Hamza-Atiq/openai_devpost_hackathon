# Final Hero UX Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the verified hero-journey UX, correctness, accessibility, and production-cleanup defects before final deployed testing.

**Architecture:** Shared presentation primitives will make timezone formatting and modal behavior consistent. Typed deterministic failure evidence and exactly-eight-team setup data will flow through existing API contracts; deterministic scheduling and validation remain authoritative.

**Tech Stack:** Next.js 15, React 19, TypeScript, Vitest, FastAPI, Pydantic, pytest.

## Global Constraints

- Preserve exactly 8 teams, 2 groups of 4, 2 venues, and 15 matches.
- Never relax a confirmed hard constraint or bypass independent validation.
- Start each change with a focused failing test and finish with consolidated gates.
- Keep weather language as risk guidance and approval as workspace-internal.

---

### Task 1: Venue-local formatting

**Files:**
- Create: `apps/web/lib/venue-time.ts`
- Create: `apps/web/lib/venue-time.test.ts`
- Modify: `apps/web/components/disruption-declaration-live.tsx`
- Modify: `apps/web/components/repair-review-live.tsx`
- Modify: `apps/web/components/weather-risk-panel.tsx`
- Modify: `apps/web/components/weather-risk-panel-live.tsx`

**Interface:** `formatVenueDateTime(instant: string, timeZone: string, variant?: "compact" | "date" | "time"): string`.

- [ ] Add tests that set a non-venue runtime timezone and expect `2026-07-22T10:00:00+08:00` to display as `22 Jul, 10:00` in `Asia/Kuala_Lumpur`, without seconds.
- [ ] Run the focused tests and confirm existing browser-local formatting fails.
- [ ] Implement the shared formatter and carry each fixture's IANA timezone into recovery, diff, and weather views.
- [ ] Run formatter and affected component tests.

### Task 2: Actionable infeasibility

**Files:**
- Modify: `apps/api/app/api/schedules.py`
- Modify: `apps/api/tests/test_schedule_api.py`
- Modify: `apps/web/lib/api-client.ts`
- Modify: `apps/web/components/guided-setup-live.tsx`
- Modify: `apps/web/components/guided-setup-live.test.tsx`

**Interface:** RFC 9457 responses retain `evidence: string[]` and `remedies: string[]`; `ApiProblemError` exposes both.

- [ ] Add API tests proving the 160-hour-rest failure returns deterministic conflict evidence and concrete remedies.
- [ ] Add frontend tests proving both lists and an edit-setup action render.
- [ ] Preserve typed evidence/remedies in precheck and solver error responses and in `ApiProblemError`.
- [ ] Render the conflict panel without displaying an invalid schedule.
- [ ] Run focused API and frontend tests.

### Task 3: Eight-team, 4+4 editor

**Files:**
- Modify: `apps/api/app/api/setup_models.py`
- Modify: `apps/api/app/scheduling/slot_patterns.py`
- Modify: `apps/api/tests/test_setup_api.py`
- Modify: `apps/web/lib/setup-contract.ts`
- Modify: `apps/web/components/guided-setup.tsx`
- Modify: `apps/web/components/guided-setup-live.tsx`
- Modify: `apps/web/components/guided-setup.test.tsx`

**Interface:** Setup draft carries eight `{id, display_name, group_id}` records. Renames preserve IDs; group changes are atomic swaps, so both groups always contain four teams.

- [ ] Add contract/API tests for eight persisted names and four members in each group.
- [ ] Add component tests for editable Group A/B columns and atomic swap controls.
- [ ] Extend setup serialization and reconstruction while preserving stable IDs.
- [ ] Implement the two-column editor and swap operation.
- [ ] Run setup tests and assert the generated tournament remains 8/4+4/15.

### Task 4: Accessible application dialogs

**Files:**
- Create: `apps/web/components/app-dialog.tsx`
- Create: `apps/web/components/app-dialog.test.tsx`
- Modify: `apps/web/components/schedule-approval-dialog.tsx`
- Modify: `apps/web/components/director-panel.tsx`

**Interface:** `AppDialog` owns initial focus, Tab wrapping, Escape dismissal, trigger-focus restoration, and inert background behavior.

- [ ] Add DOM tests for focus entry, forward/backward wrapping, Escape, restoration, and inert background.
- [ ] Implement `AppDialog` without adding a new dependency.
- [ ] Migrate approval, Reset demo, and Delete workspace confirmations; destructive actions run only from explicit dialog buttons.
- [ ] Run dialog and Director tests.

### Task 5: Authoritative rest validation

**Files:**
- Modify: `apps/web/components/guided-setup.tsx`
- Modify: `apps/web/components/guided-setup-live.tsx`
- Modify: `apps/web/components/guided-setup.test.tsx`

**Interface:** Minimum-rest input accepts integer hours from 0 through 168; only valid values update the saved draft and ledger.

- [ ] Add tests showing `300` produces a field error and never appears as `18000 minutes` or reaches autosave.
- [ ] Separate the input text from the last valid authoritative value.
- [ ] Render the allowed range next to the field and disable generation while invalid.
- [ ] Run guided-setup tests.

### Task 6: Judge-facing polish and production cleanup

**Files:**
- Modify: `apps/web/app/globals.css`
- Modify: `apps/web/components/director-panel.tsx`
- Modify: `apps/web/components/weather-risk-panel.tsx`
- Modify: `apps/api/app/main.py`
- Modify: `apps/api/tests/test_main.py`
- Delete or isolate: `apps/api/app/session_probe.py`
- Remove unused production calls from: `apps/web/lib/session-probe.ts`

- [ ] Add tests that the session probe is absent outside local/test configuration and weather provenance appears before fixtures.
- [ ] Make the sticky header opaque, remove the duplicate Director label, and standardize compact dates through the shared formatter.
- [ ] Move deterministic/live mode and attribution beside coverage at the top of the weather panel.
- [ ] Disable the spike route in production and remove unused frontend probe behavior.
- [ ] Record measured operation durations before making any performance change; do not alter the static progress indicator without evidence.
- [ ] Run focused tests.

### Task 7: Consolidated verification

- [ ] Run `pnpm lint` and `pnpm test`.
- [ ] Run `uv run ruff check .` and `uv run pytest`.
- [ ] Run production builds for web and API.
- [ ] After deployment, manually execute the three-minute hero path in a non-venue browser timezone, including infeasibility, approval keyboard behavior, reset/delete cancellation, weather provenance, and recovery diff.
- [ ] Record changed files, requirement IDs, test output, limitations, and deployment impact in the handoff.
