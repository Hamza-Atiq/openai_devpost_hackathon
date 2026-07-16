# CrickOps AI Version 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Status:** Approved for implementation planning — 2026-07-16

**Goal:** Deliver the public, three-minute CrickOps AI hero journey with deterministic scheduling and repair, six meaningful specialist roles, weather intelligence, isolated guest workspaces, and explicit organizer approval.

**Architecture:** A Next.js TypeScript frontend uses a same-origin proxy to a FastAPI backend. PostgreSQL stores guest workspaces and versions; OR-Tools CP-SAT owns scheduling and repair; OpenAI Agents SDK coordinates GPT-5.6 and bounded specialist tools; Open-Meteo supplies live/geocoded weather while deterministic fixtures protect the demo.

**Tech stack:** Next.js, TypeScript, React, FastAPI, Python, Pydantic, OpenAI Agents SDK, GPT-5.6 Sol, OR-Tools CP-SAT, PostgreSQL, Open-Meteo, Vercel, Railway, pytest, Vitest, Playwright.

## Global constraints

- Read approved `scope.md`, `prd.md`, `spec.md`, and this checklist before every task.
- Implement Version 1 required work only; optional and future items remain blocked until the completion gate passes.
- Use T10 120-minute or T20 240-minute operational allocation blocks; the hero demo uses T20.
- Both venues share one IANA timezone.
- No team plays twice on one tournament-local calendar day.
- All group matches precede semifinals; both semifinals precede the final.
- Same-venue fixture intervals never overlap, even across different slot IDs.
- Agents never create, validate, approve, or repair schedules directly.
- No draft is selectable until the independent validator passes it.
- No official schedule changes without explicit backend-owned approval.
- Test-first cycle for every behavior: failing test → minimal implementation → passing focused test → relevant suite → evidence → checklist update.
- Never mark a task complete without recording its validation evidence.
- Commit after each independently validated task using a focused conventional-commit message.

## Planned repository map

```text
apps/
  api/
    app/
      api/ agents/ approvals/ audit/ domain/ fairness/ persistence/
      scheduling/ validation/ weather/ workspaces/ observability/
    migrations/ tests/ pyproject.toml Dockerfile railway.toml
  web/
    app/ components/ features/ lib/ tests/ package.json next.config.ts
config/optimization/v1.yaml
evals/cases/ evals/expected/
tests/e2e/
docs/decisions/ docs/evidence/ docs/demo/
vercel.json pnpm-workspace.yaml README.md AGENTS.md
```

## Milestone 1 — Repository and development environment

- [x] **TASK-001 — Scaffold the monorepo and quality commands**
  - **Release:** V1 required
  - **Dependencies:** None
  - **Requirements:** NFR-001, NFR-008, DEPLOY-005
  - **Files:** Create root workspace files, `apps/api/pyproject.toml`, `apps/web/package.json`, formatter/linter/test configuration.
  - **Expected output:** `pnpm lint`, `pnpm test`, `uv run ruff check .`, and `uv run pytest` are defined and initially pass.
  - **Validation:** Run all four commands; expect exit code 0. Commit `chore: scaffold crickops monorepo`.

- [x] **TASK-002 — Add configuration and secret boundaries**
  - **Release:** V1 required
  - **Dependencies:** TASK-001
  - **Requirements:** SEC-002, DEPLOY-003, DEPLOY-006
  - **Files:** Create `apps/api/app/settings.py`, `apps/web/lib/env.ts`, `.env.example`, secret-scanning config.
  - **Expected output:** Server-only keys fail closed when absent; client build exposes only approved public values.
  - **Validation:** Run settings unit tests and scan built frontend assets for key-name/value fixtures; expect no secret leakage.

- [x] **TASK-003 — Spike GPT-5.6 Sol and Agents SDK compatibility**
  - **Release:** V1 required, blocking
  - **Dependencies:** TASK-002
  - **Requirements:** AGENT-001–AGENT-014, OBS-001, NFR-002
  - **Files:** Create `apps/api/spikes/openai_capabilities.py`, `docs/evidence/openai-capability-spike.md`.
  - **Expected output:** Evidence for target-account access to `gpt-5.6-sol`, tool calls, Pydantic structured output, tracing, sessions, and bounded latency.
  - **Validation:** Execute the spike against the production-intended account; record model ID, SDK version, trace ID, schema result, tool result, latency, and limitations. Stop if any required capability fails.

- [x] **TASK-004 — Spike fallback-provider compatibility**
  - **Release:** V1 required, blocking
  - **Dependencies:** TASK-003
  - **Requirements:** AGENT-012–AGENT-013, FR-028–FR-030, FAIL-007–FAIL-008
  - **Files:** Create `apps/api/spikes/fallback_provider.py`, `docs/evidence/fallback-capability-spike.md`.
  - **Expected output:** Configured provider either passes the same application schemas, tool safety, deterministic checks, and approval protections or is explicitly disabled in favor of deterministic mode.
  - **Validation:** Run valid, invalid-schema, unsupported-tool, timeout, and hard-constraint-override cases; record evidence.

- [x] **TASK-005 — Spike hosted session, cookie, proxy, and cache behavior**
  - **Release:** V1 required, blocking
  - **Dependencies:** TASK-002
  - **Requirements:** DEPLOY-008, SEC-001–SEC-003, NFR-006
  - **Files:** Create minimal `vercel.json`, FastAPI probe route, cookie test page, `docs/evidence/vercel-railway-session-spike.md`.
  - **Expected output:** Vercel rewrite reaches Railway; `__Host-` cookie persists; mutation CSRF works; `x-vercel-enable-rewrite-caching: 0` prevents private caching; preview cannot access production.
  - **Validation:** Use Playwright against preview and production-like environments; record headers and isolation results.

**QUALITY-GATE-01:** TASK-003, TASK-004, and TASK-005 must pass or produce an approved document amendment before domain implementation begins.

Approved amendment (2026-07-16): production proxy/cookie/cache/CSRF behavior was
verified live; preview-to-production isolation is accepted here via deterministic
environment-bound cookie tests and will be repeated on live preview in TASK-056.

## Milestone 2 — Domain models and sample tournament

- [x] **TASK-006 — Implement immutable domain contracts**
  - **Release:** V1 required
  - **Dependencies:** QUALITY-GATE-01
  - **Requirements:** DATA-001–DATA-005, SCHED-001–SCHED-009, SCHED-022–SCHED-030
  - **Files:** Create focused modules under `apps/api/app/domain/` for tournament, team/group, venue/slot, constraint, match, schedule, weather, and audit types.
  - **Expected output:** Strict Pydantic models reject unknown fields, invalid cardinalities, unsupported presets, timezone mismatch, and individual-duration overrides.
  - **Validation:** `uv run pytest apps/api/tests/domain -q`; expect all boundary tests pass.

- [x] **TASK-007 — Create international and Pakistan sample fixtures**
  - **Release:** V1 required
  - **Dependencies:** TASK-006
  - **Requirements:** FR-003, FR-034, UX-008, SCHED-022
  - **Files:** Create `apps/api/app/domain/samples/*.json` and golden-schema tests.
  - **Expected output:** Two neutral, non-infringing samples load as T20, contain eight teams/two venues, and are immediately schedulable.
  - **Validation:** Run sample validation and branding scan; expect zero schema, capacity, trademark, or unauthorized-team-brand failures.

- [x] **TASK-008 — Implement tournament revision and state transitions**
  - **Release:** V1 required
  - **Dependencies:** TASK-006
  - **Requirements:** DATA-002–DATA-003, APPROVAL-001–APPROVAL-007, NFR-011
  - **Files:** Create `apps/api/app/domain/states.py`, `apps/api/tests/domain/test_state_transitions.py`.
  - **Expected output:** Only approved transitions are possible; stale revision and direct draft-to-official mutation fail.
  - **Validation:** Run exhaustive transition-table tests; expect forbidden transitions to raise typed domain errors.

**QUALITY-GATE-02:** Both samples and all domain/state tests pass before pairing or solver work.

## Milestone 3 — Tournament-format and pairing engine

- [x] **TASK-009 — Generate the fixed 15-match graph**
  - **Release:** V1 required
  - **Dependencies:** TASK-006
  - **Requirements:** SCHED-001–SCHED-004, AC-001
  - **Files:** Create `apps/api/app/scheduling/pairings.py`, `apps/api/tests/scheduling/test_pairings.py`.
  - **Expected output:** Twelve unique group pairings, A1–B2 and B1–A2 semifinals, and final dependency with stable IDs.
  - **Validation:** Property tests over renamed teams/groups; expect exactly 15 unique matches and correct dependency graph.

- [x] **TASK-010 — Model exclusive knockout roles and paths**
  - **Release:** V1 required
  - **Dependencies:** TASK-009
  - **Requirements:** SCHED-021, SCHED-030, AC-027
  - **Files:** Create `apps/api/app/scheduling/qualification_paths.py`, path regression tests.
  - **Expected output:** A1/A2 and B1/B2 are mutually exclusive roles; a team occupies at most one semifinal; all group-to-semifinal and semifinal-to-final paths enumerate correctly.
  - **Validation:** Run path matrix tests including same-local-day semifinals; expect exclusivity and complete path coverage.

**QUALITY-GATE-03:** Pairing and qualification-path property tests pass with no missing or fabricated match.

## Milestone 4 — CP-SAT scheduling engine

- [x] **TASK-011 — Build the hard-feasible CP-SAT model shell**
  - **Release:** V1 required
  - **Dependencies:** TASK-009, TASK-010
  - **Requirements:** SCHED-009, SCHED-014, NFR-001
  - **Files:** Create `apps/api/app/scheduling/model.py`, `solver_result.py`, model tests.
  - **Expected output:** Exactly-one placement, slot eligibility, fixed graph, blackouts, pins, and typed feasible/infeasible results.
  - **Validation:** Run minimal feasible and seeded infeasible tests; expect deterministic validity status.

- [x] **TASK-012 — Enforce allocation intervals and venue NoOverlap**
  - **Release:** V1 required
  - **Dependencies:** TASK-011
  - **Requirements:** SCHED-023–SCHED-024, SCHED-029, AC-022–AC-023, AC-026
  - **Files:** Create `apps/api/app/scheduling/intervals.py`; tests for partial overlap, duplicate interval IDs, containment, T10/T20 capacity.
  - **Expected output:** Optional fixed-duration intervals use per-venue `NoOverlap`; complete blocks fit availability.
  - **Validation:** Run focused solver tests; every overlapping/overflow case is infeasible and valid separated intervals pass.

- [x] **TASK-013 — Enforce team/day, rest, and stage chronology**
  - **Release:** V1 required
  - **Dependencies:** TASK-011, TASK-012
  - **Requirements:** SCHED-020–SCHED-021, SCHED-026–SCHED-027, AC-001, AC-021, AC-027
  - **Files:** Create `apps/api/app/scheduling/chronology.py`, local-day/rest regression tests.
  - **Expected output:** One match per team/local day, all groups before semifinals, both semifinals before final, every possible qualifier rest path protected.
  - **Validation:** Run midnight, DST, non-overlapping-same-day, and same-day-semifinal cases; expect specified outcomes.

- [x] **TASK-014 — Implement pre-solver feasibility evidence**
  - **Release:** V1 required
  - **Dependencies:** TASK-013
  - **Requirements:** FR-022–FR-023, SCHED-014–SCHED-015, FAIL-003
  - **Files:** Create `apps/api/app/scheduling/precheck.py`, remedy evidence tests.
  - **Expected output:** Capacity, blackout, rest, chronology, pin, preset, and timezone contradictions return typed evidence without modifying constraints.
  - **Validation:** Run infeasibility fixtures; expect stable evidence codes and no schedule output.

**QUALITY-GATE-04:** Solver cannot proceed to profiles until every hard-constraint and infeasibility test passes.

## Milestone 5 — Independent schedule validator

- [x] **TASK-015 — Implement the independent validator and digests**
  - **Release:** V1 required
  - **Dependencies:** TASK-013
  - **Requirements:** FR-011, AGENT-007, AC-003, METRIC-001–METRIC-003
  - **Files:** Create `apps/api/app/validation/validator.py`, `digests.py`, `violations.py` without importing solver-model construction.
  - **Expected output:** Deterministic report with input digest, placement digest, validator version, checks, violations, and timestamp.
  - **Validation:** Dependency test proves validator does not import `scheduling.model`; valid golden schedule passes.

- [x] **TASK-016 — Add validator mutation suite**
  - **Release:** V1 required
  - **Dependencies:** TASK-015
  - **Requirements:** SCHED-009, SCHED-020–SCHED-021, SCHED-029–SCHED-030, AC-026–AC-027
  - **Files:** Create `apps/api/tests/validation/test_mutations.py`.
  - **Expected output:** Independent rejection of omissions, duplication, overlaps, duplicate slot intervals, overflow, blackouts, team/day, rest, chronology, and qualifier-role violations.
  - **Validation:** Mutation suite must kill every seeded invalid schedule; record validator coverage evidence.

**QUALITY-GATE-05:** Zero seeded invalid schedule may reach `valid=true`; agents and API remain disconnected until this gate passes.

## Milestone 6 — Schedule profiles and scoring

- [x] **TASK-017 — Encode optimization configuration v1**
  - **Release:** V1 required
  - **Dependencies:** TASK-011
  - **Requirements:** SCHED-010–SCHED-013, WEATHER-012, FAIR-001–FAIR-004
  - **Files:** Create `config/optimization/v1.yaml`, typed loader, checksum tests.
  - **Expected output:** Exact profile weights, risk thresholds, slot categories, missing-coverage penalties, normalization, and rounding match spec Section 17.
  - **Validation:** Golden checksum and configuration-schema tests pass; all weights and ranges are bounded.

- [x] **TASK-018 — Implement deterministic schedule metrics**
  - **Release:** V1 required
  - **Dependencies:** TASK-015, TASK-017
  - **Requirements:** FR-012–FR-013, FAIR-001–FAIR-005, WEATHER-012, AC-025
  - **Files:** Create focused modules under `apps/api/app/fairness/` and golden metric fixtures.
  - **Expected output:** Weather risk/coverage, group rest, potential knockout rest, final rest, venue/slot balance, and preference satisfaction are separate and reproducible.
  - **Validation:** Golden-vector tests match exact expected decimal values and rounding.

- [x] **TASK-019 — Generate and compare three profiles plus Custom**
  - **Release:** V1 required
  - **Dependencies:** TASK-014, TASK-016, TASK-018
  - **Requirements:** FR-009–FR-013, SCHED-011–SCHED-013, AC-002
  - **Files:** Create `apps/api/app/scheduling/profiles.py`, `comparison.py`, concurrent-run tests.
  - **Expected output:** Balanced, Weather-first, and Fairness-first use identical hard inputs; Custom runs only on request; identical solutions are reported honestly.
  - **Validation:** Run three-profile integration test; expect three valid reports, one metric version, and no unvalidated option.

**QUALITY-GATE-06:** All profile metrics are deterministic, comparable, independently validated, and satisfy directional performance budget in local evaluation.

## Milestone 7 — Schedule-repair engine

- [x] **TASK-020 — Implement sequential lexicographic repair**
  - **Release:** V1 required
  - **Dependencies:** TASK-016, TASK-018
  - **Requirements:** RECOVERY-001–RECOVERY-008, SCHED-029–SCHED-030, AC-008
  - **Files:** Create `apps/api/app/scheduling/repair.py`, `repair_objectives.py`, pass-optimum tests.
  - **Expected output:** Sequential passes fix changed-count optimum, then movement/venue optimum, then quality; prior optima never weaken.
  - **Validation:** Golden repair cases verify pass optima, full validation, and 15-second budget behavior.

- [x] **TASK-021 — Implement schedule differences and infeasible repair**
  - **Release:** V1 required
  - **Dependencies:** TASK-020
  - **Requirements:** FR-017–FR-019, RECOVERY-004–RECOVERY-009, FAIL-009
  - **Files:** Create `apps/api/app/scheduling/diff.py`, repair diff/infeasibility tests.
  - **Expected output:** Unchanged/moved/added/removed placements and metric deltas compare to immutable official baseline; infeasible repair preserves baseline.
  - **Validation:** Rain and venue-outage golden cases pass; rejected/failed repair cannot mutate official state.

**QUALITY-GATE-07:** Rain and venue-unavailability repairs pass every hard rule and preserve unaffected fixtures whenever feasible.

## Milestone 8 — Weather service and demo mode

- [x] **TASK-022 — Verify Open-Meteo usage rights and attribution**
  - **Release:** V1 required, blocking live deployment
  - **Dependencies:** TASK-002
  - **Requirements:** WEATHER-013, SEC-006, DEPLOY-007
  - **Files:** Create `docs/evidence/open-meteo-rights.md`, attribution copy fixture.
  - **Expected output:** Dated evidence for evaluation/prototyping use, call limits, required attribution, and commercial follow-up.
  - **Validation:** Human review against current official pricing/licensing pages; record reviewer/date/source links.

- [x] **TASK-023 — Implement geocoding and shared-timezone confirmation**
  - **Release:** V1 required
  - **Dependencies:** TASK-006, TASK-022
  - **Requirements:** SCHED-026–SCHED-028, AC-024
  - **Files:** Create `apps/api/app/weather/geocoding.py`, candidate/manual-coordinate tests.
  - **Expected output:** Venue name is separate; city/country/admin/postal search returns bounded candidates; organizer confirms coordinates/timezone; mismatch is rejected.
  - **Validation:** Mock API tests cover candidates, no result, manual fallback, and cross-timezone rejection.

- [x] **TASK-024 — Implement normalized live weather and risk/coverage**
  - **Release:** V1 required
  - **Dependencies:** TASK-017, TASK-023
  - **Requirements:** WEATHER-001, WEATHER-003–WEATHER-010, WEATHER-012, AC-005, AC-025
  - **Files:** Create `apps/api/app/weather/provider.py`, `normalize.py`, `risk.py`, `cache.py`.
  - **Expected output:** Coordinate/time/preset-window risk, null unknown risk, coverage percentage, stale/unavailable states, attribution metadata.
  - **Validation:** Golden hourly vectors and 16-day/21-day coverage cases match spec formulas exactly.

- [x] **TASK-025 — Implement deterministic demo weather**
  - **Release:** V1 required
  - **Dependencies:** TASK-024
  - **Requirements:** WEATHER-002, WEATHER-006–WEATHER-007, AC-006–AC-007, METRIC-005
  - **Files:** Create versioned `apps/api/app/weather/demo_scenarios/*.json` and scenario tests.
  - **Expected output:** Reproducible rain threshold crossing converts one official slot to unavailable and supports repair.
  - **Validation:** Repeat scenario at least 20 times; inputs, risk, threshold event, and affected slot digest remain identical.

**QUALITY-GATE-08:** Weather mode never labels unknown data safe; attribution and deterministic rain are verified.

## Milestone 9 — Agents SDK foundation

- [x] **TASK-026 — Implement provider, session, and guarded tool infrastructure**
  - **Release:** V1 required
  - **Dependencies:** TASK-003, TASK-004, TASK-015
  - **Requirements:** AGENT-007–AGENT-014, DATA-005, OBS-001
  - **Files:** Create `apps/api/app/agents/provider.py`, `sessions.py`, `guarded_tool.py`, `schemas.py`.
  - **Expected output:** GPT-5.6 primary, compatible fallback, SQLAlchemySession, Pydantic outputs, guarded `function_tool` wrappers, deterministic-mode result.
  - **Validation:** Provider/schema/tool-authorization tests pass for primary, fallback, invalid output, and outage.

- [x] **TASK-027 — Implement mode health, retries, and circuit breakers**
  - **Release:** V1 required
  - **Dependencies:** TASK-026
  - **Requirements:** FR-028–FR-030, NFR-005, FAIL-007–FAIL-008, OBS-004
  - **Files:** Create `apps/api/app/agents/resilience.py`, `apps/api/app/observability/dependency_health.py`.
  - **Expected output:** Bounded retry, fallback, deterministic mode, half-open recovery, and visible provenance.
  - **Validation:** Fault-injection tests verify transition order and no fabricated response.

- [x] **TASK-028 — Implement source hierarchy and prompt contract tests**
  - **Release:** V1 required
  - **Dependencies:** TASK-026
  - **Requirements:** AGENT-010–AGENT-014, SEC-004–SEC-005
  - **Files:** Create `apps/api/app/agents/instructions.py`, prompt contract/evaluation tests.
  - **Expected output:** Shared hierarchy, uncertainty language, tool rules, forbidden claims, turn/output budgets, escalation, and role examples match spec.
  - **Validation:** Adversarial evals reject invented fixtures/metrics, hidden reasoning, silent hard-rule changes, and unsupported weather claims.

**QUALITY-GATE-09:** Agents cannot connect to organizer flows until guarded tools, schemas, deterministic authority, and degraded behavior pass.

## Milestone 10 — Specialist agents

- [x] **TASK-029 — Implement Director, Rules, and Strategy specialists**
  - **Release:** V1 required
  - **Dependencies:** TASK-019, TASK-028
  - **Requirements:** AGENT-001–AGENT-003, AGENT-009–AGENT-011
  - **Files:** Create three agent modules and focused eval cases under `apps/api/app/agents/` and `evals/cases/agents/`.
  - **Expected output:** Director owns conversation; Rules proposes/clarifies; Strategy requests profiles and recommends only from validated metrics.
  - **Validation:** Golden and adversarial evals pass; every specialist output contains consumed role-specific evidence.

- [x] **TASK-030 — Implement Weather and Fairness specialists**
  - **Release:** V1 required
  - **Dependencies:** TASK-018, TASK-025, TASK-028
  - **Requirements:** AGENT-004–AGENT-005, FAIR-001–FAIR-005, WEATHER-009–WEATHER-010
  - **Files:** Create weather/fairness agent modules and eval cases.
  - **Expected output:** Weather explains coverage/uncertainty; Fairness separates group and potential-knockout metrics and never edits fixtures.
  - **Validation:** Evals reject safety guarantees, radar claims, placeholder overcounting, and fabricated metrics.

- [x] **TASK-031 — Implement Recovery specialist and meaningful orchestration**
  - **Release:** V1 required
  - **Dependencies:** TASK-021, TASK-029, TASK-030
  - **Requirements:** AGENT-006, AGENT-009–AGENT-010, RECOVERY-001–RECOVERY-009, METRIC-008
  - **Files:** Create `recovery.py`, `orchestration.py`, sequence/evidence tests.
  - **Expected output:** All six roles run only where relevant; no ceremonial or duplicate calls; recovery explanations use validated diff evidence.
  - **Validation:** Execute the three spec sequence tests; fail any invocation with no consumed role-specific evidence.

**QUALITY-GATE-10:** The six roles must participate meaningfully where relevant in the hero flow; deterministic tools remain authoritative.

## Milestone 11 — FastAPI application

- [x] **TASK-032 — Implement workspace/setup/weather endpoints and error contract**
  - **Release:** V1 required
  - **Dependencies:** TASK-008, TASK-023–TASK-027
  - **Requirements:** FR-001–FR-008, FAIL-001–FAIL-003, FAIL-006, DEPLOY-008
  - **Files:** Create versioned routers under `apps/api/app/api/`, ProblemDetails mapping, OpenAPI tests.
  - **Expected output:** Guest, sample, tournament, constraint, location, and weather routes match spec request/response and authorization behavior.
  - **Validation:** API contract tests and generated OpenAPI snapshot pass.

- [x] **TASK-033 — Implement generation, comparison, edit, and recovery endpoints**
  - **Release:** V1 required
  - **Dependencies:** TASK-019–TASK-021, TASK-032
  - **Requirements:** FR-009–FR-023, RECOVERY-001–RECOVERY-009, FAIL-004–FAIL-005, FAIL-009
  - **Files:** Create schedule-run, draft, comparison, edit, disruption, diff routers and progress events.
  - **Expected output:** Idempotent asynchronous solve/repair operations with synchronous reads and typed failures.
  - **Validation:** API integration tests cover happy, infeasible, stale, retry, and cancellation paths.

- [x] **TASK-034 — Implement synchronous export, audit, health, and mode endpoints**
  - **Release:** V1 required
  - **Dependencies:** TASK-032
  - **Requirements:** FR-002, FR-024–FR-035, DATA-007, OBS-001–OBS-005, DEPLOY-004
  - **Files:** Create export/audit/health/mode routers.
  - **Expected output:** Small workspace export returns synchronously without secrets; audit pagination and coarse health/mode status work.
  - **Validation:** Contract tests verify no export job exists, export redaction, pagination, and degraded readiness.

**QUALITY-GATE-11:** OpenAPI snapshot, ownership tests, and all API failure contracts pass before frontend integration.

## Milestone 12 — Database and persistence

- [x] **TASK-035 — Implement PostgreSQL schema and migrations**
  - **Release:** V1 required
  - **Dependencies:** TASK-006
  - **Requirements:** DATA-001–DATA-009, NFR-007, NFR-011
  - **Files:** Create persistence models/repositories and migrations for every spec entity.
  - **Expected output:** Immutable revisions/versions, one active tournament, audit events, jobs, sessions, idempotency, and feedback constraints.
  - **Validation:** Migrate empty database up/down/up; run repository integration tests.

- [x] **TASK-036 — Implement transactional approval service**
  - **Release:** V1 required
  - **Dependencies:** TASK-015, TASK-035
  - **Requirements:** FR-014–FR-015, APPROVAL-001–APPROVAL-007, AC-011
  - **Files:** Create `apps/api/app/approvals/service.py`, concurrency tests.
  - **Expected output:** Ownership, expected revision, ready/valid status, repair baseline, idempotency, and freshness verified in one transaction with audit event.
  - **Validation:** Concurrent approval tests produce one official version; stale/invalid/direct UI mutations fail.

- [x] **TASK-037 — Implement guest retention, reset, deletion, and isolation**
  - **Release:** V1 required
  - **Dependencies:** TASK-035
  - **Requirements:** FR-025, FR-031–FR-033, SEC-001, SEC-006–SEC-009, AC-015–AC-017
  - **Files:** Create workspace service, cleanup job, retention tests.
  - **Expected output:** Seven-day inactivity expiration, delete/reset semantics, hard deletion deadlines, and strict concurrent isolation.
  - **Validation:** Time-travel, identifier manipulation, two-guest concurrency, and deletion tests pass.

**QUALITY-GATE-12:** Persistence, approval, isolation, expiration, and migration suites pass on PostgreSQL.

## Milestone 13 — Next.js user interface

- [x] **TASK-038 — Build the accessible workspace shell and samples entry**
  - **Release:** V1 required
  - **Dependencies:** TASK-032, TASK-035
  - **Requirements:** UX-001–UX-002, UX-008, ACCESS-001–ACCESS-006
  - **Files:** Create app routes, layout, typed API client, query cache, sample chooser, Director panel shell.
  - **Expected output:** Responsive control-room shell with keyboard/focus support and clear guest/privacy entry.
  - **Validation:** Vitest component tests, axe scan, keyboard Playwright entry test.

- [ ] **TASK-039 — Build guided setup, location, slots, and Constraint Ledger**
  - **Release:** V1 required
  - **Dependencies:** TASK-038
  - **Requirements:** FR-004–FR-008, SCHED-005–SCHED-009, SCHED-022–SCHED-029, UX-010–UX-012
  - **Files:** Create setup features/components and revision-conflict handling.
  - **Expected output:** T10/T20 control, separate venue/location confirmation, shared timezone, slot patterns, hard/soft review, explicit confirmation.
  - **Validation:** Component and E2E tests cover both presets, manual coordinates, mismatch, blackout, and stale edit.

- [ ] **TASK-040 — Build Schedule Rail and official schedule view**
  - **Release:** V1 required
  - **Dependencies:** TASK-038, TASK-036
  - **Requirements:** UX-003, UX-005, UX-009–UX-010, APPROVAL-007
  - **Files:** Create Schedule Rail, fixture cards, validation badge, version selector.
  - **Expected output:** Chronological local-time schedule with stage gates and official/draft distinction.
  - **Validation:** Visual/component tests plus keyboard navigation and no-color-only state checks.

**QUALITY-GATE-13:** Setup-to-ready flow is accessible and never stores authoritative decisions only in chat.

## Milestone 14 — Schedule comparison

- [ ] **TASK-041 — Build profile controls and comparison panels**
  - **Release:** V1 required
  - **Dependencies:** TASK-019, TASK-040
  - **Requirements:** FR-009–FR-013, UX-003, AC-002
  - **Files:** Create profile selector, custom priorities, metric comparison, soft-violation list.
  - **Expected output:** Three aligned validated options; Custom only on request; identical schedules and coverage differences explained.
  - **Validation:** UI tests verify metric consistency, validation gating, and no unsupported ranking.

- [ ] **TASK-042 — Integrate explicit original-schedule approval**
  - **Release:** V1 required
  - **Dependencies:** TASK-036, TASK-041
  - **Requirements:** FR-014–FR-015, APPROVAL-002–APPROVAL-007
  - **Files:** Create approval dialog/action and audit refresh behavior.
  - **Expected output:** UI calls Approval API; backend creates timestamped version/audit event; stale result remains draft.
  - **Validation:** Playwright approval and concurrent-stale tests; verify no UI-to-UI state shortcut.

**QUALITY-GATE-14:** Three-profile generation, comparison, and explicit official approval work end to end.

## Milestone 15 — Weather-risk visualization

- [ ] **TASK-043 — Build risk, coverage, freshness, and attribution UI**
  - **Release:** V1 required
  - **Dependencies:** TASK-024, TASK-041
  - **Requirements:** WEATHER-003, WEATHER-008–WEATHER-013, UX-004, AC-005, AC-025
  - **Files:** Create risk badge/detail, coverage banner, attribution footer/export rendering.
  - **Expected output:** Null risk remains unknown; coverage and issue time are visible; color is not sole signal.
  - **Validation:** Component tests cover full/partial/zero/stale coverage and attribution.

- [ ] **TASK-044 — Build deterministic/live mode controls and threshold confirmation**
  - **Release:** V1 required
  - **Dependencies:** TASK-025, TASK-043
  - **Requirements:** WEATHER-002, WEATHER-004–WEATHER-007, APPROVAL-006
  - **Files:** Create mode switch, threshold proposal/confirmation UI, provider failure state.
  - **Expected output:** Mode is explicit; thresholds become hard only after confirmation; deterministic substitution is never silent.
  - **Validation:** E2E tests activate rain scenario, confirm threshold, and observe unavailable slot/audit event.

## Milestone 16 — Disruption and recovery flow

- [ ] **TASK-045 — Build rain and venue-unavailability declaration flow**
  - **Release:** V1 required
  - **Dependencies:** TASK-021, TASK-044
  - **Requirements:** FR-016, RECOVERY-001–RECOVERY-002, RECOVERY-009
  - **Files:** Create recovery route, disruption form, affected-fixture view.
  - **Expected output:** Rain threshold event and manual venue outage use one unavailable-slot workflow against official baseline.
  - **Validation:** E2E tests for both disruption types; unsupported events remain unavailable.

- [ ] **TASK-046 — Build repair difference and recovery explanation UI**
  - **Release:** V1 required
  - **Dependencies:** TASK-031, TASK-045
  - **Requirements:** FR-017–FR-019, RECOVERY-003–RECOVERY-008, UX-005
  - **Files:** Create ScheduleDiffRail, metric deltas, reasoning/evidence panel.
  - **Expected output:** Preserved, moved, added, removed, and trade-offs are accessible and grounded in valid diff.
  - **Validation:** Component and E2E golden diff tests; invalid repair never displays as approvable.

## Milestone 17 — Human approval and official versions

- [ ] **TASK-047 — Integrate repair approval/rejection and restoration**
  - **Release:** V1 required
  - **Dependencies:** TASK-036, TASK-046
  - **Requirements:** FR-018–FR-021, APPROVAL-002–APPROVAL-007, AC-008–AC-011
  - **Files:** Extend approval UI/service integration and version history.
  - **Expected output:** Approval verifies current baseline and creates new version; rejection/cancel preserves previous official schedule.
  - **Validation:** Rain, venue, stale-baseline, double-click/idempotency, rejection, and restore E2E tests pass.

- [ ] **TASK-048 — Complete organizer audit timeline and workspace feedback**
  - **Release:** V1 required
  - **Dependencies:** TASK-034, TASK-047
  - **Requirements:** FR-024–FR-027, DATA-006, AC-012
  - **Files:** Create activity route/components and structured feedback form.
  - **Expected output:** Human-readable events and optional reason codes persist; raw prompts/diagnostics remain absent.
  - **Validation:** Timeline sequence matches hero flow; rejected recommendation is not repeated without new evidence.

**QUALITY-GATE-17:** Full setup → comparison → approval → rain repair → approval → audit flow passes locally with real solver/validator.

## Milestone 18 — Tracing and observability

- [ ] **TASK-049 — Implement trace correlation, redaction, logs, and metrics**
  - **Release:** V1 required
  - **Dependencies:** TASK-026, TASK-034
  - **Requirements:** OBS-001–OBS-006, SEC-005, NFR-009, NFR-011
  - **Files:** Create observability modules, redaction tests, dashboards/runbook definitions.
  - **Expected output:** Correlation ID spans HTTP/agent/tool/solver/validator/weather/DB/audit; sensitive content excluded.
  - **Validation:** One hero run resolves end to end by correlation ID; redaction fixtures do not appear in logs/traces.

- [ ] **TASK-050 — Implement public-demo limits and emergency deterministic mode**
  - **Release:** V1 required
  - **Dependencies:** TASK-027, TASK-049
  - **Requirements:** NFR-013, FR-028–FR-030
  - **Files:** Create quota/budget service, counters, emergency switch, abuse-log tests.
  - **Expected output:** Numeric workspace/IP/provider/solver limits and 75%/100% budget behavior match spec without raw prompt logging.
  - **Validation:** Load/fault tests hit each threshold and verify reset time, state preservation, and deterministic continuity.

## Milestone 19 — Automated tests and evaluation

- [ ] **TASK-051 — Assemble deterministic evaluation corpus**
  - **Release:** V1 required
  - **Dependencies:** QUALITY-GATE-17
  - **Requirements:** AC-001–AC-027, METRIC-001–METRIC-008
  - **Files:** Populate `evals/cases/`, `evals/expected/`, evaluation runner.
  - **Expected output:** Feasible, infeasible, format, overlap, knockout, weather, repair, provider, and feedback cases have versioned expected results.
  - **Validation:** Evaluation runner reports 100% hard-valid displayed results and 100% seeded infeasible blocking.

- [ ] **TASK-052 — Complete accessibility and security test suites**
  - **Release:** V1 required
  - **Dependencies:** TASK-048, TASK-050
  - **Requirements:** ACCESS-001–ACCESS-006, SEC-001–SEC-009, METRIC-006, METRIC-011
  - **Files:** Add axe/keyboard/CSRF/ownership/rate-limit/export-redaction E2E suites.
  - **Expected output:** No critical accessibility issue or cross-workspace/security escape in hero flow.
  - **Validation:** Run full security/accessibility jobs; archive reports in `docs/evidence/`.

- [ ] **TASK-053 — Repeat hero flow and performance tests**
  - **Release:** V1 required
  - **Dependencies:** TASK-051, TASK-052
  - **Requirements:** NFR-002–NFR-004, NFR-008, METRIC-009–METRIC-012
  - **Files:** Create `tests/e2e/hero.spec.ts`, load/performance harness, evidence report.
  - **Expected output:** Repeated genuine GPT-5.6, solver, validator, six-role, rain-repair flow fits three minutes; directional 10/30/15 targets measured.
  - **Validation:** Minimum 20 consecutive deployed-like runs with success/latency report; investigate any failure before gate.

- [ ] **TASK-054 — Run complete regression and requirement evidence matrix**
  - **Release:** V1 required
  - **Dependencies:** TASK-053
  - **Requirements:** All V1 PRD identifiers
  - **Files:** Create `docs/evidence/requirement-matrix.md` linking each ID to test/evidence.
  - **Expected output:** Zero untested V1 requirement, duplicate ID, missing reference, or undocumented exception.
  - **Validation:** Run automated ID/range audit plus all backend/frontend/E2E/eval suites; expect all pass.

**QUALITY-GATE-19 — VERSION 1 COMPLETION GATE:** No optional task may start until TASK-054 passes and the deployed hero flow is reliable.

## Milestone 20 — Deployment

- [ ] **TASK-055 — Containerize and deploy Railway backend/database/worker**
  - **Release:** V1 required
  - **Dependencies:** TASK-050, TASK-054
  - **Requirements:** DEPLOY-002–DEPLOY-007, NFR-009–NFR-010
  - **Files:** Finalize API Dockerfile, Railway config, migrations/release command, health checks.
  - **Expected output:** Production API/worker/PostgreSQL deploy with migrations, readiness, logs, retention job, secrets.
  - **Validation:** Railway status/health/log verification and database migration smoke test.

- [ ] **TASK-056 — Deploy Vercel frontend and same-origin proxy**
  - **Release:** V1 required
  - **Dependencies:** TASK-005, TASK-055
  - **Requirements:** DEPLOY-001, DEPLOY-008, SEC-001–SEC-003
  - **Files:** Finalize `vercel.json`, production/preview variables and headers.
  - **Expected output:** Public application proxies `/api/v1/*`, preserves host cookie, disables rewrite caching, and isolates preview.
  - **Validation:** Repeat TASK-005 tests on real production and preview URLs.

- [ ] **TASK-057 — Validate deployed concurrency, fallback, and recovery**
  - **Release:** V1 required
  - **Dependencies:** TASK-056
  - **Requirements:** NFR-005–NFR-009, AC-014–AC-017
  - **Files:** Add deployment evidence report.
  - **Expected output:** Multiple judges remain isolated; refresh/return, fallback, deterministic mode, deletion, export, weather, and repair work publicly.
  - **Validation:** Concurrent Playwright/load run plus manual judge smoke checklist.

- [ ] **TASK-058 — Maintain public availability through judging**
  - **Release:** V1 required, operational
  - **Dependencies:** TASK-057
  - **Requirements:** DEPLOY-001–DEPLOY-004, METRIC-009
  - **Files:** Create `docs/demo/judging-availability-runbook.md`, uptime monitor configuration.
  - **Expected output:** Public app, health checks, budget alerts, deterministic switch, and incident contacts remain active throughout the judging period.
  - **Validation:** Monitor from submission through announced judging end; record uptime/incidents and daily hero smoke result.

**QUALITY-GATE-20:** Production hero flow, isolation, security headers, cookie, cache, health, and deterministic fallback all pass.

## Milestone 21 — README and Codex collaboration documentation

- [ ] **TASK-059 — Write repository setup, architecture, testing, and operation docs**
  - **Release:** V1 required
  - **Dependencies:** TASK-057
  - **Requirements:** DEPLOY-005–DEPLOY-007, OBS-006
  - **Files:** Complete `README.md`, `AGENTS.md`, local setup, test commands, deployment/health instructions, weather attribution.
  - **Expected output:** A reviewer can access or clone the repository, run tests, start locally, understand modes, and reproduce the demo.
  - **Validation:** Fresh-machine documentation walkthrough; every documented command succeeds.

- [ ] **TASK-060 — Document Codex acceleration and human decisions**
  - **Release:** V1 required
  - **Dependencies:** TASK-059
  - **Requirements:** Hackathon documentation requirement
  - **Files:** Create `docs/decisions/codex-collaboration.md`, update README.
  - **Expected output:** Dated record of Codex contributions, human approvals/overrides, architecture decisions, limitations, and evidence links.
  - **Validation:** Cross-check against commit history, planning documents, and `/feedback` Session ID; remove unsupported claims.

## Milestone 22 — Devpost submission and three-minute demonstration

- [ ] **TASK-061 — Produce the public three-minute video**
  - **Release:** V1 required
  - **Dependencies:** QUALITY-GATE-20
  - **Requirements:** Demo requirements, METRIC-010
  - **Files:** Create `docs/demo/script.md`, shot list, timing sheet, final public YouTube link.
  - **Expected output:** English video under three minutes with audible narration demonstrating short prompt, three profiles, validation, approval, rain repair, new version, Codex, and GPT-5.6.
  - **Validation:** Verify public/unlisted accessibility, duration <3:00, audio, captions, and full hero evidence.

- [ ] **TASK-062 — Complete Devpost submission materials**
  - **Release:** V1 required
  - **Dependencies:** TASK-060, TASK-061
  - **Requirements:** Hackathon submission requirements
  - **Files:** Create `docs/demo/devpost-submission.md` and asset inventory.
  - **Expected output:** English problem, solution, impact, architecture, limitations, GPT-5.6/Agents SDK/Codex use, public app, repository, video, and testing instructions.
  - **Validation:** Compare every field with current official rules; verify all links in a signed-out browser.

- [ ] **TASK-063 — Submit Codex feedback Session ID and compliance evidence**
  - **Release:** V1 required
  - **Dependencies:** TASK-062
  - **Requirements:** `/feedback` Codex Session ID and submission compliance
  - **Files:** Record Session ID and submission receipt in private-safe `docs/evidence/submission-record.md` without secrets.
  - **Expected output:** Required Codex Session ID, repository access, app URL, video URL, and submission receipt are recorded.
  - **Validation:** Second-person review confirms values match the submitted entry.

- [ ] **TASK-064 — Run final legal, branding, and availability review**
  - **Release:** V1 required
  - **Dependencies:** TASK-063
  - **Requirements:** Submission compliance
  - **Files:** Complete `docs/demo/final-compliance-check.md`.
  - **Expected output:** No unauthorized music, trademarks, logos, or sample-team branding; all materials are English; attribution is present; app/video/repo are accessible.
  - **Validation:** Two-person final review in signed-out sessions; record timestamped pass before deadline.

**QUALITY-GATE-22 — SUBMISSION READY:** TASK-058 and TASK-061–TASK-064 pass; public availability monitoring continues through judging.

## Deferred work registry

- [ ] **OPTIONAL-001 — ODI preset** — **Blocked until QUALITY-GATE-19.** Requirements: SCHED-025. Requires a separately approved specification amendment and evaluation suite.
- [ ] **OPTIONAL-002 — Communications Specialist and external delivery** — **Blocked until QUALITY-GATE-19.** Requirements: AGENT-015 and Version 1.1 scope.
- [ ] **OPTIONAL-003 — Product-wide anonymized feedback retention** — **Blocked until QUALITY-GATE-19 and consent/revocation review.** Requirement: FR-036.
- [ ] **DEFERRED-001 — Multi-timezone, travel, venue discovery, larger formats, Test/multi-day, scoring, DLS, public publishing, authentication, and cross-tournament memory** — **Post-hackathon/future; not authorized by this checklist.**

## Checklist maintenance rules

1. Update `[ ]` to `[x]` only after the listed validation passes and evidence is recorded.
2. If a task exposes a requirements conflict, stop that task, document the conflict, and request approval before changing `scope.md`, `prd.md`, or `spec.md`.
3. Preserve task IDs; add new IDs rather than renumbering completed or referenced tasks.
4. Record significant architecture decisions in `docs/decisions/` and link the affected requirement/task.
5. Optional and deferred entries never count toward Version 1 completion.
