# CrickOps AI — Product Scope

**Status:** Approved — 2026-07-16

## Document purpose

This document defines the strategic product boundary for CrickOps AI. Detailed product behavior belongs in `prd.md`; architecture and implementation decisions belong in `spec.md`; delivery tasks belong in `checklist.md`.

## Product vision

CrickOps AI is a global cricket tournament operations copilot for amateur, academy, university, club, corporate, community, and regional organizers. It helps organizers plan tournaments, compare valid schedules, understand weather and fairness trade-offs, respond to pre-match disruptions, and approve an official schedule with confidence.

The long-term vision is a complete operating system for the tournament lifecycle. Version 1 proves the narrower differentiator: natural-language planning, mathematically valid scheduling, forecast-based risk intelligence, and explainable minimum-disruption recovery.

## Problem statement

Tournament organizers must reconcile team availability, venues, time slots, rest, weather, fairness, and audience preferences. Manual planning is slow and fragile; conversational AI alone cannot guarantee valid fixtures; conventional schedulers rarely explain trade-offs or repair an approved plan intelligently after disruption.

CrickOps combines agent-assisted interpretation and explanation with deterministic optimization and independent validation. It never treats an LLM-generated answer as proof that a schedule is valid.

## Target users and stakeholders

The primary Version 1 user is the tournament organizer. Each guest workspace has one organizer role.

Teams, players, officials, venue managers, and spectators are affected stakeholders but are not direct Version 1 users. Multiple guests may use isolated workspaces concurrently; collaboration within one tournament is deferred.

## Primary use cases

1. Configure a fixed-format tournament through guided controls and natural language.
2. Review and confirm interpreted hard and soft constraints.
3. Compare three independently validated schedule options.
4. Approve one option as the official workspace schedule.
5. Assess fixture-level forecast risk.
6. Repair an approved schedule after rain or venue unavailability while minimizing disruption.
7. Review schedule changes, trade-offs, versions, and operational audit history.

## Version 1 objectives

- Prove meaningful coordination among six narrow specialist roles.
- Generate mathematically valid schedules for the fixed competition format.
- Make optimization trade-offs understandable and measurable.
- Demonstrate live forecast guidance and reproducible demo weather.
- Preserve unaffected fixtures where possible during schedule recovery.
- Keep the organizer in control of constraints and approvals.
- Deliver a reliable, public, three-minute hackathon journey.

## Version 1 product boundary

### Competition scale

- Exactly eight teams in two groups of four.
- Single round-robin play within each group.
- Top two teams per group advance to two semifinals and one final.
- No third-place playoff; 15 matches in total.
- One tournament-wide match-format preset: T10 or T20.
- Default operational venue allocation blocks are 120 minutes for T10 and 240 minutes for T20. They include expected play, normal intervals, setup, and operational turnover and are planning defaults—not guaranteed match durations.
- Exactly two organizer-entered venues.
- Both venues in a Version 1 tournament use the same IANA timezone; multi-timezone tournaments are deferred.
- A configurable tournament window of 7–21 calendar days.
- Organizer-defined dates, slot patterns, blackout periods, and availability.
- Each organizer-listed start time represents one tournament match opportunity; the solver chooses one of the two venues and does not schedule parallel fixtures at that start.
- Schedule quality includes a coherent tournament cadence, avoiding unnecessarily packed group stages followed by long idle gaps before knockouts.
- Semifinal and final participants remain qualification placeholders; results-driven progression is deferred.

### Guided flexibility

Organizers may customize team names, group assignments, venue details, dates, time slots, blackout periods, minimum rest, rivalry or preferred slots, weather thresholds, and scheduling priorities. The setup experience guides users through required information rather than relying on one unstructured prompt.

### Schedule alternatives

The primary comparison includes Balanced, Weather-first, and Fairness-first options. These share the same confirmed hard constraints and differ only in soft priorities. A Custom priorities option is available on demand. Minimum-travel is not a visible Version 1 profile.

All alternatives must pass independent deterministic validation before display. Recommendations must be grounded in solver-produced metrics rather than unsupported model judgment.

### Weather intelligence

Version 1 includes:

- Live forecast guidance based on actual venue coordinates.
- Deterministic, reproducible demo weather.
- International dates, time zones, and locations supported where forecast data is available.
- Clear handling of unavailable, incomplete, or uncertain forecast data.

Weather is a soft scheduling factor by default. Organizers may explicitly confirm visible weather thresholds as hard constraints. CrickOps provides operational risk guidance—not radar nowcasting, hyperlocal certainty, official safety advice, or guaranteed washout prevention. Final operational decisions remain with the organizer.

### Disruption and controlled change

Version 1 supports rain and venue unavailability through the same minimum-change recovery capability. Venue unavailability must be fully testable but need not appear in the primary video.

Organizers may request controlled fixture changes and classify them as required or preferred. Changes create a validated draft; they never alter the official schedule without explicit approval. The organizer may cancel an unapproved edit and restore the latest approved schedule.

### Approval and versioning

Approval makes a schedule the current official baseline inside its workspace. Approved schedules are versioned and timestamped; replaced versions remain in audit history. External publication or distribution is not part of Version 1.

### User experience

Version 1 is a hybrid guided workspace:

- The Tournament Director conversation handles goals, clarification, recommendations, trade-offs, and recovery reasoning.
- Structured controls hold editable tournament data, constraints, priorities, and approvals.
- Dedicated visual panels present schedules, comparisons, weather risk, fairness, and repair differences.

Chat and controls share one tournament state. Important decisions cannot exist only in chat history, and approval requires an explicit action.

### Guest workspaces and samples

- No registration or authentication is required.
- Each isolated guest workspace supports one active tournament.
- Workspace state survives refreshes and short return visits.
- Inactive guest workspaces are automatically deleted after a limited retention period defined in `spec.md`.
- Reset demo, Delete workspace, Create new tournament, and Export tournament actions are included.
- At least one geographically neutral/international sample and one Pakistan-based sample are preloaded.

### Auditability and adaptive workspace memory

A human-readable activity timeline records constraint confirmation and edits, schedule requests and validation outcomes, approvals, disruptions, repairs, and rejections. Raw prompts, hidden reasoning, tokens, stack traces, and low-level diagnostics are not exposed to organizers.

Within a workspace, CrickOps retains relevant decisions, preferences, edits, structured rejection reasons, approved plans, and repair outcomes so it can avoid repeating rejected recommendations. This is workspace memory, not automatic model retraining.

Product-wide use of anonymized structured feedback requires clear disclosure and consent. Cross-tournament organizer memory is deferred.

### Agent organization

Six operational roles are required:

1. Tournament Director
2. Rules and Constraint Specialist
3. Scheduling Strategy Specialist
4. Weather Intelligence Specialist
5. Fairness and Logistics Auditor
6. Disruption and Recovery Specialist

All six roles must perform meaningful, traceable work where relevant in the hero journey; no agent should be invoked merely to satisfy an agent-count requirement. Each role must remain narrow and necessary. Specialists interpret, coordinate, audit, compare, and explain; deterministic services remain authoritative for scheduling-related calculations and validation. The Communications Specialist is deferred to Version 1.1.

### Resilience boundary

The designated OpenAI model and agent framework are the primary and demonstrated experience. Version 1 also requires a configurable secondary model-provider path and a deterministic degraded mode. If model providers are unavailable, structured setup, optimization profiles, validation, demo weather, repair, approvals, and audit history remain usable; unavailable conversational capabilities must be stated honestly.

The current operating mode and provider provenance must be visible and auditable. Fallback providers provide continuity and do not replace the designated OpenAI model in the official demonstration.

## Infeasible inputs

CrickOps must reject infeasible inputs rather than present a broken schedule as acceptable. It preserves confirmed hard constraints, explains conflicts using deterministic evidence, suggests remedies, and requires explicit editing and reconfirmation before retrying. Hard-constraint changes are recorded in audit history. No hard constraint may be silently relaxed.

## Version 1 success criteria

- Zero hard-constraint violations across the approved test suite.
- Every displayed schedule and repair passes independent validation.
- Infeasible configurations are rejected with useful guidance.
- All six roles perform meaningful, traceable work where relevant in the hero flow; none is invoked merely to satisfy an agent-count requirement.
- Weather demo scenarios and rain recovery are reproducible.
- Recovery preserves unaffected official fixtures where feasible and explains all changes.
- Concurrent guest workspaces remain isolated.
- The complete deployed hero journey works repeatedly within a three-minute presentation.
- The public application requires no judge installation, account, API key, or local setup.

Performance goals are directional rather than contractual: agent interpretation ideally completes within 10 seconds, three-profile generation and validation within 30 seconds, and disruption repair within 15 seconds. Multi-step operations always provide progress feedback. Genuine scheduling, validation, specialist participation, and repair must run during the hero flow; cached results are permitted only as an explicitly labelled emergency fallback.

## Required three-minute hero journey

1. Load a ready-made tournament.
2. Enter a short natural-language scheduling request.
3. Review and confirm interpreted constraints.
4. Generate Balanced, Weather-first, and Fairness-first schedules.
5. Show independent validation and comparative metrics.
6. Approve one option as the official workspace schedule.
7. Trigger deterministic rain disruption.
8. Generate a minimum-change repaired draft.
9. Show preserved and changed fixtures, metric differences, and recovery reasoning.
10. Approve the repair and show the new version and audit entries.

## Explicit non-goals for Version 1

- Team or player registration.
- Live scoring, scorecards, standings, or results-driven progression.
- DLS calculations or in-progress match management.
- Payments, venue booking, or match-official assignment.
- Public fixture pages, shareable links, or stakeholder notifications.
- WhatsApp, email, calendar, SMS, or push delivery.
- Automatic worldwide ground discovery.
- Country-specific cricket regulations.
- Multi-timezone tournament operation.
- More teams, groups, venues, or match formats beyond the approved T10/T20 presets.
- ODI before the Version 1 completion gate; Test and other multi-day formats remain future scope.
- Travel-first or real-distance logistics optimization.
- Multi-user collaboration, roles, organization accounts, or tournament portfolios.
- Radar nowcasting or guaranteed forecast precision.
- Automatic training on raw organizer data.

## Version 1.1 — Optional after core stability

- Communications Specialist and stakeholder delivery.
- Public fixture pages and sharing.
- Authentication, roles, and cross-tournament preferences.
- Basic scoring, standings, and results-driven knockout progression.
- Qualification scenarios and match-official assignment.
- Broader tournament scale only after the fixed-format completion gate passes.

## Post-hackathon roadmap

Later versions may add registration, mobile clients, payments, venue booking and discovery, calendar integrations, advanced standings, multi-city travel, organizer analytics, verified DLS, live and ball-by-ball scoring, radar-based weather intelligence, probabilistic nowcasting, reserve-day planning, broadcast and security constraints, and large multi-division competitions.

## Assumptions

- Organizers can provide accurate teams, venue locations, availability, and constraints.
- Forecast coverage exists for many—but not all—organizer-entered locations.
- Version 1 handles planning data and instructs users not to enter personal, confidential, financial, or payment information.
- The hackathon can provide the model, hosting, and weather-service access required for the primary demo.
- Exact provider capabilities and competition rules will be verified before implementation.

## Constraints and dependencies

- The fixed Version 1 format cannot expand until the completion gate passes.
- Mathematical scheduling correctness and independent validation must remain deterministic.
- The designated OpenAI model and agent framework are required for the primary hackathon experience.
- Scheduling and validation require a deterministic optimization foundation.
- A weather-data provider, persistent managed storage, and public hosting are external dependencies.
- The deployed solution must remain portable. Named hosting, database, solver, and provider choices belong in `spec.md`.
- Secrets must never be required from judges or exposed through the client.

## Principal risks

- Scope expansion beyond the fixed hero journey.
- Solver infeasibility or inconsistent constraint interpretation.
- External model, weather, tracing, or hosting failures.
- Forecast uncertainty being presented too confidently.
- Multi-agent roles becoming redundant or ceremonial.
- Slow generation undermining the three-minute demo.
- Guest-workspace leakage or unintended retention of user data.
- Fallback-provider capability differences.

These risks are controlled through strict scope gates, deterministic validation, reproducible demo data, degraded operation, workspace isolation, explicit approvals, observable execution, and repeatable end-to-end testing.

## Hackathon submission requirements

- A publicly accessible browser application.
- A reliable three-minute demonstration of the required hero journey.
- Clear evidence of meaningful use of the designated OpenAI model and agent framework.
- Traceable specialist activity, tool use, validation, and approval boundaries.
- Honest separation of live capabilities, deterministic demo data, and emergency fallbacks.
- Submission documentation that explains the product problem, architecture, impact, limitations, and where Codex accelerated development.

Exact current competition rules, dates, media requirements, and eligibility conditions must be verified against the official Build Week materials before submission.

## Definition of done

Version 1 is done only when:

- The four planning documents are approved and mutually consistent.
- Every required Version 1 capability works in the deployed application.
- All displayed schedules and repairs pass deterministic validation.
- Infeasible inputs, external-service failures, and concurrent guest sessions are tested.
- The six required specialist roles are operational and perform meaningful, traceable work wherever relevant.
- Both sample tournaments and both disruption types work.
- The genuine hero journey completes reliably and fits the three-minute presentation.
- No optional feature has compromised the required flow.
- Submission assets and official-rule checks are complete.

Implementation must not begin until `scope.md`, `prd.md`, `spec.md`, and `checklist.md` have each been reviewed and explicitly approved.
