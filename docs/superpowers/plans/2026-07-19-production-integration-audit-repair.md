# Production Integration Audit Repair Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace disconnected demo surfaces with real workspace, weather, recovery, and OpenAI Agents SDK flows, then prove the deployed three-minute journey with production evidence.

**Architecture:** FastAPI remains the authority for workspace state and invokes GPT-5.6 only for interpretation and explanation; OR-Tools, weather-risk services, the validator, approval service, and repair engine remain deterministic authorities. Next.js client components fetch typed API views and never fall back to fabricated domain data. Production mode is derived from validated server settings and every agent-assisted response records provider/model provenance.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, OpenAI Agents SDK 0.18.x, OR-Tools CP-SAT, PostgreSQL, Next.js 15, React 19, TypeScript, Vitest, pytest, Playwright, Railway, Vercel.

## Global Constraints

- Preserve exactly 8 teams, 2 groups of 4, 2 venues, and 15 matches.
- Never relax a confirmed hard constraint or bypass independent validation.
- Agents interpret and explain; deterministic services create, validate, and repair fixtures.
- Keep guest identity in secure same-origin cookies and all provider secrets server-side.
- Start every behavior change with a focused failing test and finish with the consolidated quality gate.
- Weather remains planning risk guidance; approval remains internal to the workspace.
- Do not add Version 1.1 or optional scope.

## Verified Finding Matrix

| Finding | Status | Evidence / root cause |
| --- | --- | --- |
| C1 OpenAI absent in production | Confirmed | `create_app()` unconditionally creates `OperationsState(mode=DETERMINISTIC)`; no request path calls `Runner.run`; Railway logs contain no agent/provider request. |
| C2 Director chat dead | Confirmed | Button has no handler and mode copy is hardcoded. |
| C3 Recovery UI fabricated | Confirmed | Recovery page passes hardcoded version; declaration and diff components use fake defaults; real APIs are called with fake slot IDs. |
| C4 Weather panel fabricated | Confirmed | Options page renders `WeatherRiskPanel` without props, selecting its fake 100% defaults. |
| H1 Sample has no repair slack | Confirmed | Both samples expand 8 dates × 2 venues × 1 start = 16 slots for 15 fixtures; Railway shows infeasible repair `422`s. |
| H2 Live weather unavailable | Confirmed, broader than report | Samples are outside the provider horizon, and `/weather/refresh` is itself a stub that always returns unavailable without calling `OpenMeteoWeatherProvider`. |
| H3 Profiles are effectively identical | Confirmed by deployed evidence; regression test required | Near-single-solution slot capacity plus zero weather signal removes meaningful objective trade-offs. |
| H4 Foreign disruption slots accepted | Confirmed | `create_disruption` stores externally supplied IDs without tournament ownership validation. |
| M1 Ledger conflicts with backend constraint state | Confirmed | Five static UI rows are labelled decisions while domain constraints remain empty/draft. |
| M2 Zero-hour minimum rest labelled hard rule | Confirmed | Default setup is zero while the static ledger states the rule is applied. |
| M3 Reset leaves no tournament | Confirmed in production; exact persistence boundary still under investigation | Railway log shows reset `200` followed by repeated tournament `404`. Current client source does use `POST`, so the test must trace reset through the PostgreSQL store/middleware lifecycle instead of assuming a client-method defect. |
| M4 Repair infeasibility lacks remedies | Confirmed | `repair_infeasible` contains one generic sentence and no structured evidence/remedies. |
| M5 Infeasible repair lacks audit outcome | Confirmed | Audit append occurs only after successful repair. |
| M6 Export lacks weather attribution | Confirmed | Export contains weather state but no provider attribution contract. |
| M7 Knockout rest not displayed | Confirmed | API metric exists; comparison UI type and rows omit it. |
| L1 Retention duration absent in UI | Confirmed | UI says only “after inactivity”; spec requires seven days. |
| L2 Native confirm dialogs | Confirmed, lower priority | Functional but weaker than the existing accessible approval-dialog pattern. |
| L3 Audit exposes raw UUIDs | Confirmed | Payload renderer displays every non-sensitive field including internal IDs. |
| L4 Venue balance 75 for aggregate 8/7 | Not proven | Metric intentionally evaluates per-team venue exposure. Add a focused optimal-distribution test before considering a formula change. |

---

### Task 1: Activate a real, resilient Tournament Director request path

**Files:**
- Modify: `apps/api/app/main.py`
- Modify: `apps/api/app/api/operations.py`
- Create: `apps/api/app/api/director.py`
- Create: `apps/api/app/agents/runtime.py`
- Modify: `apps/web/lib/api-client.ts`
- Modify: `apps/web/components/director-panel.tsx`
- Test: `apps/api/tests/api/test_director_contract.py`
- Test: `apps/web/components/director-panel.test.tsx`

**Interfaces:**
- Consumes: validated `ServerSettings`, `AgentProviderRouter`, `AgentResilienceManager`, `create_director_agent`, current workspace summary.
- Produces: `POST /api/v1/director/turn` with `{message, mode, provider, model, proposed_state_changes, specialist_evidence, ui_actions}` and a live `GET /api/v1/system/mode` view.

- [ ] Write API tests proving production settings select GPT-5.6, the endpoint invokes an injected Runner adapter, validated structured output is returned, provenance is audited, and provider failure yields an honest deterministic unavailable response.
- [ ] Run `uv run pytest apps/api/tests/api/test_director_contract.py -q` and verify failures are caused by the missing runtime/router.
- [ ] Implement a small Runner adapter using official `Runner.run(...)` and `RunConfig(model_provider=route.sdk_provider)`; keep provider invocation injectable in tests and never expose raw prompts or traces.
- [ ] Initialize runtime mode from validated settings instead of forcing deterministic mode; preserve emergency deterministic override, retries, timeouts, circuit breaker, and automatic primary recovery.
- [ ] Add client tests proving the Director panel fetches mode, opens an accessible chat surface, submits a short request, shows progress/errors, and renders deterministic unavailability honestly.
- [ ] Implement the chat surface and shared-state proposals: proposed hard-constraint edits remain review-only until the organizer confirms them through structured controls.
- [ ] Run the focused API/web tests and commit the isolated change.

### Task 2: Reject foreign disruption slots and record infeasible recovery evidence

**Files:**
- Modify: `apps/api/app/api/schedules.py`
- Modify: `apps/api/app/scheduling/precheck.py`
- Test: `apps/api/tests/api/test_schedule_recovery_contract.py`

**Interfaces:**
- Consumes: latest official schedule placements and tournament slot IDs.
- Produces: typed `invalid_disruption_slots` ProblemDetails and structured `repair_infeasible` audit evidence/remedies.

- [ ] Add a failing test that submits a valid UUID belonging to another/no tournament and expects `422 invalid_disruption_slots` before a disruption is stored.
- [ ] Add a failing test that makes repair infeasible and expects a `repair_infeasible` audit event plus conflict evidence and concrete remedy objects.
- [ ] Validate every supplied slot against the active tournament and require at least one supplied slot to affect the latest official baseline; reject a no-op instead of reporting success.
- [ ] Reuse precheck remedy vocabulary to explain capacity/chronology/rest conflicts without relaxing constraints.
- [ ] Run `uv run pytest apps/api/tests/api/test_schedule_recovery_contract.py -q` and commit.

### Task 3: Wire recovery declaration and diff pages to real official data

**Files:**
- Modify: `apps/api/app/api/schedules.py`
- Modify: `apps/web/lib/api-client.ts`
- Create: `apps/web/components/disruption-declaration-live.tsx`
- Modify: `apps/web/app/workspace/recovery/page.tsx`
- Modify: `apps/web/components/repair-review-live.tsx`
- Modify: `apps/web/components/disruption-declaration.tsx`
- Modify: `apps/web/components/schedule-diff-rail.tsx`
- Test: `apps/web/components/disruption-declaration-live.test.tsx`
- Test: `apps/web/components/repair-review-live.test.tsx`

**Interfaces:**
- Consumes: official schedule fixture `slot_id`, version number, venue-local display fields, and `GET /api/v1/schedule-diffs/{draft_id}`.
- Produces: real affected-slot choices and a real preserved/moved/added/removed/metric-delta review before approval.

- [ ] Add failing API/client tests requiring official fixture `slot_id` and typed schedule-diff retrieval.
- [ ] Remove all domain-data defaults from recovery components; empty/loading/error states must be explicit and non-approvable.
- [ ] Load the latest official schedule on the declaration page, route successful repair to `/workspace/recovery/diff?draft=<id>`, and display server ProblemDetails remedies on failure.
- [ ] Map real baseline/draft placement data to organizer-readable fixture labels and named venue timezone; pass real validation and metrics to the diff rail.
- [ ] Disable approve/reject/restore actions until required data has loaded and ensure a no-op diff is not described as a moved fixture.
- [ ] Run focused Vitest/API tests and commit.

### Task 4: Connect live and deterministic weather to schedules and options

**Files:**
- Modify: `apps/api/app/api/routes.py`
- Create: `apps/api/app/weather/service.py`
- Modify: `apps/api/app/api/workspace.py`
- Modify: `apps/web/lib/api-client.ts`
- Create: `apps/web/components/weather-risk-panel-live.tsx`
- Modify: `apps/web/app/workspace/options/page.tsx`
- Modify: `apps/web/components/weather-risk-panel.tsx`
- Test: `apps/api/tests/api/test_workspace_setup_weather_contract.py`
- Test: `apps/web/components/weather-risk-panel-live.test.tsx`

**Interfaces:**
- Consumes: `OpenMeteoWeatherProvider`, deterministic scenario loader, tournament coordinates/slots/allocation, approved or draft placements.
- Produces: persisted per-slot risk/components/coverage/fetched-at/provider/mode and a truthful options panel.

- [ ] Add failing service tests with an injected HTTP client for coordinate-specific provider requests, interval risk calculations, missing coverage, and deterministic repeatability.
- [ ] Implement weather orchestration over both venue coordinates, normalize hourly forecasts, calculate each slot’s full allocation exposure, and persist typed provenance without treating unknown as low risk.
- [ ] Add a schedule-weather view endpoint that joins real fixtures to risk/components/quality and distinguishes live, deterministic, and emergency cached data.
- [ ] Remove all fake weather defaults; render loading, zero/partial/full coverage, contributors, issued time, provider attribution, and venue-local times from the API.
- [ ] Run focused weather/API/web tests and commit.

### Task 5: Make sample tournaments forecastable, flexible, and repairable

**Files:**
- Modify: `apps/api/app/domain/samples/__init__.py`
- Modify: `apps/api/app/domain/samples/global-community-cup.json`
- Modify: `apps/api/app/domain/samples/pakistan-community-cup.json`
- Modify: `apps/api/app/weather/demo_scenarios/rain-threshold-v1.json`
- Test: `apps/api/tests/domain/test_samples.py`
- Test: `apps/api/tests/api/test_schedule_recovery_contract.py`
- Test: `apps/api/tests/scheduling/test_profiles.py`

**Interfaces:**
- Produces: rolling hero samples starting three days after load, a 10-day window, two non-overlapping T20 starts per venue per day, deterministic rain aligned to a real fixture, and enough slack for representative group/semifinal/final repairs.

- [ ] Add failing tests with an injected reference date proving the sample starts within the live forecast horizon, has at least 40 valid T20 venue slots, and remains deterministic for a given reference date.
- [ ] Parameterize sample expansion by relative dates and multiple local starts; do not hardcode a one-time July 2026 patch that expires again.
- [ ] Add tests proving all three profiles validate and that seeded weather/preferences can produce at least two distinct placement digests; identical optimal results remain honestly labelled.
- [ ] Add repair tests for a group fixture, semifinal, final, and venue unavailability, each completing within the directional target on the hero sample.
- [ ] Run focused domain/scheduling/recovery tests and commit.

### Task 6: Correct reset, constraints, metrics, export, retention, and audit presentation

**Files:**
- Modify: `apps/web/lib/api-client.ts`
- Modify: `apps/web/components/guided-setup.tsx`
- Modify: `apps/web/components/profile-comparison.tsx`
- Modify: `apps/web/components/profile-comparison-live.tsx`
- Modify: `apps/web/components/activity-timeline.tsx`
- Modify: `apps/web/components/director-panel.tsx`
- Modify: `apps/api/app/api/operations.py`
- Test: corresponding API and component test files.

**Interfaces:**
- Produces: true POST reset with loaded sample; invariant-versus-confirmed ledger language; distinct group and potential-knockout rest metrics; seven-day retention copy; weather attribution in export; human-readable audit payloads.

- [ ] Add a client contract test proving reset uses `POST`, sends `sample_id`, and returns a non-null tournament; add a backend persistence/reset test.
- [ ] Replace the static “5 decisions” claim with values derived from setup and confirmation state; show zero rest as “No additional minimum configured,” not an applied hard-rest promise.
- [ ] Extend comparison types/rows with `potential_knockout_rest` and test both rest measures display independently.
- [ ] Add `weather_attribution` and mode/provenance to export and test WEATHER-013.
- [ ] State “seven days of inactivity” in the UI and suppress raw UUID fields from organizer timeline details while retaining them internally.
- [ ] Add a venue-balance test for the best feasible per-team distribution; change the formula only if this test demonstrates the current score is wrong.
- [ ] Replace native destructive confirms with the existing accessible dialog pattern after functional defects are green.
- [ ] Run focused tests and commit.

### Task 7: Prove meaningful specialist participation without ceremonial calls

**Files:**
- Modify: `apps/api/app/agents/runtime.py`
- Modify: `apps/api/app/api/director.py`
- Modify: `apps/api/app/api/schedules.py`
- Modify: `apps/api/app/api/routes.py`
- Test: `apps/api/tests/agents/test_live_orchestration.py`
- Modify: `docs/evidence/requirement-matrix.md`

**Interfaces:**
- Consumes: deterministic precheck, profile metrics/weather evidence, and repair diff/validation evidence.
- Produces: traceable Rules work during setup, Strategy/Weather/Fairness work during generation, Weather/Recovery/Fairness work during rain recovery, and Director synthesis/approval prompts.

- [ ] Add failing orchestration tests proving each invoked role consumes role-specific deterministic evidence and that duplicate/unused invocations are rejected.
- [ ] Invoke specialists only at their relevant stage, feed their validated outputs to the Director, and record role/provider/model/tool validation provenance in internal observability and organizer-safe audit summaries.
- [ ] Ensure no specialist can create fixtures or approve schedules and all state-change suggestions remain pending organizer confirmation.
- [ ] Run agent contract/orchestration tests, one controlled GPT-5.6 smoke call, and commit.

### Task 8: Consolidated local and deployed verification

**Files:**
- Modify: `docs/evidence/2026-07-19-production-integration-audit-repair.md`
- Modify: `docs/evidence/requirement-matrix.md`

- [ ] Run fresh locked dependency syncs.
- [ ] Run `pnpm lint`, `pnpm test`, and `pnpm --filter @crickops/web build`.
- [ ] Run `uv run ruff check .` and `uv run pytest`.
- [ ] Run focused secret scans, mock-domain-data scans, and diff hygiene checks.
- [ ] Run Playwright hero flow against local same-origin proxy with real generation, validation, agent request, rain repair, approval/versioning, refresh persistence, and reset.
- [ ] Deploy Railway API/worker and Vercel web only after local gates pass.
- [ ] Verify `/health/ready`, `/api/v1/system/mode`, one real Director turn, real weather coverage, three profile metrics, foreign-slot rejection, real repair diff, audit provenance, workspace isolation, reset, and export in production.
- [ ] Record timestamps, deployment IDs, sanitized response evidence, durations, residual limitations, and confidence; do not mark completion if GPT-5.6 or live weather is not actually observed.

## Self-review

- Spec coverage: C1–C4, H1–H4, M1–M7, and L1–L4 each map to a test-first task; OpenAI authority, deterministic fixture authority, weather guidance, approval, and guest isolation boundaries are preserved.
- Placeholder scan: no implementation step defers required behavior; L4 is explicitly investigation-gated rather than assumed.
- Type consistency: official fixture `slot_id`, schedule-diff response, weather view, Director turn response, and both rest metrics are introduced once and consumed by named clients/components.
