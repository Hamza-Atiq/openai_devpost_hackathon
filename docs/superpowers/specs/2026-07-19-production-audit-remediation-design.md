# Production Audit Remediation Design

**Status:** Approved in conversation on 2026-07-19; written review pending

## Goal

Close the confirmed production-audit gaps without weakening deterministic scheduling authority, explicit organizer approval, guest isolation, or degraded-mode continuity.

## Verified scope

The implementation covers:

- meaningful execution of the five specialist agents alongside the Tournament Director;
- complete agent provenance, evidence-consumption, tool-outcome, and validation audit records;
- server-authoritative weather mode and revision-bound weather evidence;
- synchronized weather controls and fixture-risk panels;
- explicit weather invalidation after slot-affecting tournament edits;
- an actionable branded not-found page;
- metric-grounded repair trade-off narrative;
- distinct accessible names for sample actions;
- browsable official schedule history on the Schedule page;
- consistent metric naming, casing, direction, and formatting.

The Custom priorities report is excluded because production testing generated and displayed the Custom option successfully. The international-sample report is excluded because the current sample already starts three days ahead, spans ten days, and provides expanded slot capacity.

## Architecture

### Specialist evidence orchestration

Add one application-owned specialist orchestration service shared by Director, schedule-generation, and recovery workflows. It receives immutable workspace state and deterministic results, builds the role-specific Pydantic input, runs the bounded specialist through the configured provider route, validates the structured output, and returns an application-level execution record.

An execution record contains:

- role, provider, model, and UTC timestamp;
- tournament revision and invocation reason;
- output schema version and validation status;
- deterministic tool outcomes and evidence references;
- the role-specific fields consumed by the calling workflow;
- a concise organizer-safe summary, without raw prompts or hidden reasoning.

Specialists never receive database, solver-model, validation-authority, or approval-authority access. Provider failure returns a typed unavailable result and never blocks deterministic generation, validation, repair, approval, or audit access.

### Meaningful invocation points

- Director setup interpretation invokes Rules when the request may change a constraint.
- Validated schedule generation invokes Strategy and Weather concurrently, then Fairness after validated metrics exist.
- Director comparison questions execute requested specialists and perform a second Director synthesis using their validated evidence.
- Validated rain recovery invokes Weather, then Recovery and Fairness; venue unavailability invokes Recovery and Fairness.
- No role runs when its required deterministic input is absent. Every successful invocation must have consumed role-specific evidence.

Generation and recovery remain deterministic-first. Agent conclusions are attached only after authoritative solver and validator results exist. A specialist failure is recorded and the deterministic result remains usable with an explicit explanation limitation.

### Director two-pass synthesis

The first Director pass may request specialists. The orchestrator validates those requests against the current workspace state, executes only supported relevant roles, and supplies organizer-safe specialist evidence to a second Director pass. The final response must cite consumed evidence references for metric claims or recommendations. A missing or invalid specialist result preserves the current refusal behavior.

### Audit persistence

Director and specialist events use the existing organizer audit boundary and internal observability boundary:

- organizer audit stores role, provider, model, timestamp, invocation reason, evidence kinds, tool outcome status, validation status, and concise summary;
- internal observability stores correlation metadata and latency without exposing raw prompts or hidden reasoning;
- every generation or recovery response retains deterministic validation independently of agent status.

## Weather consistency

Weather state gains the tournament revision and a canonical digest of current venue-slot identifiers. Weather evidence is usable only when both match current tournament state.

Saving any slot-affecting setup change clears slot risks and details while retaining only the organizer-selected mode. The state becomes `refresh_required`, coverage becomes zero, and `GET /weather` returns a visible invalidation reason. It must never report stale-slot coverage as current.

The options page uses a single client weather coordinator that:

- loads the active server mode on mount;
- supplies that mode to the controls;
- refreshes fixture evidence after a successful toggle;
- shows refresh-required and provider-unavailable states;
- warns that existing schedule-comparison metrics use their original snapshot and require regeneration after weather changes.

Switching mode does not silently rewrite already-generated schedule metrics.

## Judge-facing interface completion

### Not-found recovery

Create an application-branded not-found page with actions to return home or reopen Setup. It contains no technical diagnostics.

### Repair explanation

Use one deterministic metric-display registry with labels, direction, and sentence templates. The repair view identifies every materially worsened metric before approval, including increased weather risk or change cost and decreased fairness, coverage, balance, or preference satisfaction. Numeric deltas remain visible alongside the prose.

### Accessibility

Each sample action exposes the sample name, for example `Load Global Community Cricket Cup sample`. Visible button copy may remain concise.

### Schedule history

Add a workspace-owned historical schedule-version read endpoint that resolves the approved draft, verifies it remains independently valid, and returns the same fixture-view contract as the current official schedule. The Schedule page lists versions newest-first, loads a selected historical version without making it official, clearly labels current versus superseded state, and keeps restoration as an explicit separate action.

### Metric presentation

One shared frontend registry defines labels and improvement direction for weather risk, weather coverage, missing coverage penalty, rest fairness, potential knockout rest, venue balance, slot balance, preference satisfaction, and change cost. Comparison and recovery components consume the same registry.

## Failure behavior

- Invalid specialist schema or fabricated evidence is rejected and audited; deterministic output remains available.
- Provider outage uses the existing fallback sequence, then deterministic mode.
- Stale weather evidence is never scored or displayed as current.
- A missing historical version returns an ownership-safe not-found response.
- An invalid historical draft is suppressed rather than rendered.
- UI mutations retain current state and show an actionable retry message on failure.

## Testing and deployment acceptance

Each behavior follows red-green TDD. Required focused coverage includes:

- all six agent factories reaching bounded runtime execution where relevant;
- Director comparison synthesis citing actual validated schedule metrics;
- rejection of ceremonial, unsupported, invalid, or unconsumed specialist work;
- complete audit provenance and tool outcomes;
- weather mode restoration after reload and synchronized panel refresh;
- weather invalidation after T10/T20, date, venue, or slot changes;
- branded 404 actions and distinct sample accessible names;
- trade-off prose derived from representative positive and negative deltas;
- historical version ownership, validation, browsing, and non-restoring selection;
- shared metric-label coverage for every API metric.

Before deployment, run `pnpm lint`, `pnpm test`, the production Next.js build, `uv run ruff check .`, and `uv run pytest`. Final acceptance runs on `https://crickops.vercel.app` and must demonstrate:

1. a comparison question answered from solver-produced metrics with specialist provenance;
2. mode and risk-panel synchronization before and after reload;
3. weather invalidation and refresh guidance after a preset change;
4. historical schedule browsing without changing the current official version;
5. a repair explanation that names actual degraded metrics;
6. branded recovery from a nonexistent route.

## Non-goals

- Agents do not create, mutate, validate, repair, approve, or restore fixtures.
- No specialist is called merely to increase an agent count.
- No optional Version 1.1 communication, authentication, scoring, publishing, or cross-tournament memory work is introduced.
- Custom generation and the current international sample are not redesigned without new failing evidence.
