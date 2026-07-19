# Setup-to-Schedule Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make organizer setup persistent and authoritative, launch genuine three-profile generation with visible progress, and render only backend-owned schedule data.

**Architecture:** FastAPI owns normalization of editable setup into a valid `TournamentConfig`, including venue slots and revisions. The Next.js client maintains a controlled local draft backed by the server, autosaves through typed commands, and explicitly launches generation. Options and Schedule read generated drafts and approved versions from the API rather than using bundled defaults.

**Tech Stack:** Next.js 15, React 19, TypeScript, FastAPI, Pydantic, PostgreSQL-backed workspace snapshots, OR-Tools CP-SAT, Vitest, pytest, Playwright.

## Global Constraints

- Preserve exactly 8 teams, 2 groups, 2 venues, and 15 matches.
- Use one shared IANA timezone and one tournament-wide T10 120-minute or T20 240-minute allocation.
- Never relax a confirmed hard constraint or display an unvalidated draft.
- All authoritative state is backend-owned and scoped to the secure guest workspace.
- Start every behavior with a failing test and finish with focused plus consolidated verification.
- Do not start optional or Version 1.1 work.

---

### Task 1: Typed persisted setup contract

**Files:**
- Create: `apps/api/app/api/setup_models.py`
- Create: `apps/api/app/scheduling/slot_patterns.py`
- Modify: `apps/api/app/api/routes.py`
- Modify: `apps/api/app/api/workspace.py`
- Test: `apps/api/tests/api/test_setup_persistence_contract.py`

**Interfaces:**
- Produces: `TournamentSetupDraftInput`, `TournamentSetupView`, `expand_slot_patterns(...)`.
- Consumes: the current workspace tournament and its immutable team/group identifiers.

- [ ] Write failing API tests proving Pakistan sample values are returned, a complete setup edit increments revision, slots reflect T10/T20 and blackout patterns, and refresh restores the edit.
- [ ] Run `uv run pytest apps/api/tests/api/test_setup_persistence_contract.py -q`; expect failures because no typed setup view/save contract exists.
- [ ] Implement strict setup input/output models and backend slot-pattern expansion with timezone conversion, fixed allocations, blackout availability, and stable venue/team/group ownership.
- [ ] Replace raw `PUT /tournament` handling with revision-checked, idempotent setup persistence and an audit event.
- [ ] Run the focused API tests and `uv run pytest apps/api/tests/api/test_workspace_setup_weather_contract.py apps/api/tests/domain apps/api/tests/scheduling/test_precheck.py -q`; expect all pass.

### Task 2: Real readiness and generation protections

**Files:**
- Modify: `apps/api/app/api/routes.py`
- Modify: `apps/api/app/api/schedules.py`
- Test: `apps/api/tests/api/test_setup_generation_flow.py`

**Interfaces:**
- Consumes: saved setup revision and `run_pre_solver_checks(...)` evidence.
- Produces: confirmation tied to an exact revision and schedule-run refusal for incomplete, stale, or infeasible setup.

- [ ] Write failing tests showing precheck rejects inadequate capacity and schedule generation rejects draft, stale, or unconfirmed revisions.
- [ ] Run `uv run pytest apps/api/tests/api/test_setup_generation_flow.py -q`; expect current status-flag-only precheck to fail assertions.
- [ ] Connect precheck to deterministic feasibility checks and require `READY_TO_SCHEDULE` plus matching confirmed revision in `POST /schedule-runs`.
- [ ] Run the focused tests and `uv run pytest apps/api/tests/api/test_operations_contract.py apps/api/tests/security/test_security_boundaries.py -q`; expect all pass.

### Task 3: Controlled setup draft and autosave UI

**Files:**
- Create: `apps/web/lib/setup-contract.ts`
- Create: `apps/web/components/guided-setup-live.tsx`
- Modify: `apps/web/lib/api-client.ts`
- Modify: `apps/web/app/workspace/setup/page.tsx`
- Modify: `apps/web/components/guided-setup.tsx`
- Test: `apps/web/components/guided-setup-live.test.tsx`
- Test: `apps/web/lib/api-client.test.ts`

**Interfaces:**
- Consumes: `TournamentSetupView` and revision-checked save API.
- Produces: controlled `SetupDraft`, visible save state, conflict recovery, and flush-before-generation behavior.

- [ ] Write failing tests proving sample values populate controls and edits survive component remount by reloading server state.
- [ ] Run `pnpm --filter @crickops/web test -- guided-setup-live.test.tsx api-client.test.ts`; expect failures for missing live setup contract.
- [ ] Implement typed API methods, controlled fields, debounced autosave, saved/error/conflict states, and server reload.
- [ ] Remove production `defaultValue` setup data and inert Edit/reload controls.
- [ ] Run focused tests, TypeScript checking, and the existing guided-setup tests; expect all pass.

### Task 4: Explicit generation workflow and progress

**Files:**
- Create: `apps/web/components/schedule-generation-progress.tsx`
- Modify: `apps/web/components/guided-setup-live.tsx`
- Modify: `apps/web/lib/api-client.ts`
- Modify: `apps/web/components/profile-comparison-live.tsx`
- Test: `apps/web/components/schedule-generation-progress.test.tsx`
- Test: `tests/e2e/setup-generation.spec.ts`

**Interfaces:**
- Consumes: saved setup revision, confirmation API, schedule-run status/events, comparison API.
- Produces: one idempotent **Confirm and generate schedules** flow and `/workspace/options?run_id=…` navigation.

- [ ] Write failing component and browser tests for named progress stages, no double-submit, successful navigation, retry, and infeasibility states.
- [ ] Run focused Vitest and Playwright tests; expect no generation request from Setup and no progress workflow.
- [ ] Implement ordered save → precheck → confirmation → generation → validation → comparison orchestration with polling fallback.
- [ ] Make Options load the run from the URL and show honest loading/empty/failure states.
- [ ] Run the focused tests and verify Railway-facing requests contain exactly one `POST /schedule-runs` per action.

### Task 5: Backend-owned official Schedule Rail

**Files:**
- Modify: `apps/api/app/api/schedules.py`
- Modify: `apps/web/lib/api-client.ts`
- Create: `apps/web/components/official-schedule-live.tsx`
- Modify: `apps/web/app/workspace/schedule/page.tsx`
- Modify: `apps/web/components/schedule-rail.tsx`
- Test: `apps/api/tests/api/test_official_schedule_view.py`
- Test: `apps/web/components/official-schedule-live.test.tsx`

**Interfaces:**
- Produces: `GET /official-schedule` with version metadata, validation evidence, and 15 fixture views.
- Consumes: latest approved version and its source validated draft.

- [ ] Write failing backend and frontend tests proving no approval yields an empty state and approval yields the exact persisted 15 placements.
- [ ] Run focused tests; expect the current hard-coded Version 2 screen to fail.
- [ ] Implement the official-schedule read contract and live component.
- [ ] Remove default production fixtures and static version options from Schedule Rail; require explicit fixture props.
- [ ] Run focused tests plus approval, version, local-time, and schedule-rail suites; expect all pass.

### Task 6: Real journey regression and evidence

**Files:**
- Rewrite: `tests/e2e/hero.spec.ts`
- Create: `docs/evidence/2026-07-19-setup-to-schedule-recovery.md`
- Modify: `docs/evidence/requirement-matrix.md`
- Modify: `checklist.md`

**Interfaces:**
- Consumes: the complete persisted setup, generation, comparison, approval, and official-schedule workflow.
- Produces: repeatable Quality Gate 13–14 evidence without direct route-skipping.

- [ ] Rewrite the hero test to load the Pakistan sample, edit actual fields, persist across navigation and refresh, generate, compare, approve, and inspect the official backend schedule.
- [ ] Add an infeasible-capacity journey that proves no schedule is displayed.
- [ ] Run the new browser tests repeatedly against a local production build.
- [ ] Run `pnpm install --frozen-lockfile`, `pnpm lint`, `pnpm test`, `uv sync --frozen`, `uv run ruff check .`, and `uv run pytest` with fresh output.
- [ ] Deploy only after local gates pass, then repeat the exact journey on `https://crickops.vercel.app` and correlate the browser action with Railway logs.
- [ ] Record changed files, requirement IDs, tests, limitations, deployment impact, and any remaining agent-integration gap without claiming Quality Gate 19 complete.
