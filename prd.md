# CrickOps AI — Product Requirements Document

**Status:** Approved — 2026-07-16

## 1. Document purpose

This PRD defines what CrickOps AI must do and why. It is subordinate to the approved `scope.md`. Technical architecture, provider selection, schemas, algorithms, storage design, and deployment configuration belong in `spec.md`.

Requirement status labels:

- **V1** — required for Version 1 completion.
- **Optional** — may begin only after the Version 1 completion gate passes.
- **Future** — explicitly outside the hackathon build.

## 2. Executive summary

CrickOps AI helps cricket tournament organizers turn goals and operational constraints into valid schedule alternatives, compare weather and fairness trade-offs, approve an official workspace schedule, and repair it after rain or venue unavailability.

The product combines a guided organizer workspace with a Tournament Director conversation. Agents interpret, coordinate, audit, compare, and explain. Deterministic services remain authoritative for tournament generation, scheduling, weather-risk calculation, validation, comparison, and repair.

Version 1 supports exactly eight teams, two groups, two venues, a 7–21-day tournament window, 15 matches, and one tournament-wide T10 or T20 preset. It is a globally usable, guest-accessible planning and pre-match recovery product—not a live tournament-management system.

## 3. User problems

| ID | User problem |
|---|---|
| PROB-001 | Organizers struggle to turn informal requirements into a complete, consistent constraint set. |
| PROB-002 | Manual fixture planning is slow and can violate capacity, rest, blackout, or knockout rules. |
| PROB-003 | A valid schedule can still distribute weather risk, rest, venues, or time slots unfairly. |
| PROB-004 | Organizers cannot easily compare alternative scheduling priorities using consistent evidence. |
| PROB-005 | Rain or venue loss causes cascading manual changes and avoidable disruption. |
| PROB-006 | AI-generated recommendations can be opaque, inconsistent, or mathematically invalid. |
| PROB-007 | Important decisions are lost in chat history and cannot be audited later. |
| PROB-008 | Hackathon judges need a fast, reliable experience without setup or credentials. |
| PROB-009 | External AI and weather services may be slow, incomplete, or unavailable. |
| PROB-010 | Guest data can leak between users or persist longer than expected. |

## 4. Personas

### PERSONA-001 — Community tournament organizer

Runs a local or community tournament, has limited scheduling software experience, and needs guided setup, clear errors, and a dependable fixture plan.

### PERSONA-002 — Academy, university, club, or corporate organizer

Manages competing preferences across teams and venues and needs measurable fairness, weather awareness, and easy schedule comparison.

### PERSONA-003 — Regional operations lead

Needs an auditable planning process, explicit approvals, reproducible decisions, and minimum-change recovery after disruption.

### PERSONA-004 — Hackathon judge

Needs immediate access to representative data and a complete, credible demonstration within three minutes.

Teams, players, officials, venue managers, and spectators are stakeholders but not direct Version 1 users.

## 5. Jobs to be done

| ID | Job |
|---|---|
| JTBD-001 | When planning a tournament, help me capture all required inputs and resolve contradictions before scheduling. |
| JTBD-002 | When choosing a schedule, show me multiple valid options and explain their measurable trade-offs. |
| JTBD-003 | When weather threatens a match, help me understand risk without overstating forecast certainty. |
| JTBD-004 | When a slot becomes unavailable, repair the schedule while protecting the approved plan as much as possible. |
| JTBD-005 | When I change a requirement, show the operational consequence and require confirmation before it becomes official. |
| JTBD-006 | When I return to my workspace, restore my approved plan, decisions, and feedback. |
| JTBD-007 | When an external service fails, preserve the deterministic planning workflow and state the limitation honestly. |

## 6. Primary user journeys

### JOURNEY-001 — Guided tournament setup

1. The organizer starts from a blank workspace or sample tournament.
2. Structured controls collect teams, groups, venues, dates, slots, availability, constraints, and priorities.
3. The organizer adds a natural-language goal or preference.
4. CrickOps interprets the request, asks one targeted clarification at a time when necessary, and updates a reviewable draft.
5. The organizer edits and explicitly confirms hard constraints before scheduling.

### JOURNEY-002 — Generate, compare, and approve

1. The organizer requests schedule generation.
2. CrickOps produces Balanced, Weather-first, and Fairness-first alternatives from identical hard constraints.
3. Each alternative is independently validated before display.
4. The organizer compares weather, rest, venue, slot, and preference metrics plus soft-constraint violations.
5. CrickOps explains trade-offs using those metrics.
6. The organizer approves one option as the official workspace schedule.

### JOURNEY-003 — Controlled schedule change

1. The organizer asks to move, pin, or block a fixture.
2. The organizer marks the request required or preferred.
3. CrickOps produces a validated draft and compares it with the latest official schedule.
4. The organizer approves the draft or cancels it and restores the official schedule.

### JOURNEY-004 — Disruption recovery

1. Rain crosses a confirmed threshold or the organizer marks a venue-time slot unavailable.
2. CrickOps identifies affected fixtures and starts recovery from the latest official schedule.
3. A minimum-change draft is generated and validated.
4. The organizer reviews preserved fixtures, changed fixtures, metric deltas, and recovery reasoning.
5. Approval creates a new official version; rejection preserves the existing version.

### JOURNEY-005 — Degraded operation

1. CrickOps detects that the primary agent provider is unavailable.
2. It retries within defined limits, then uses a configured fallback when capable.
3. If agent providers remain unavailable, the product enters deterministic mode.
4. Structured setup, generation, validation, comparison, demo weather, repair, approvals, and audit history remain usable.
5. Unavailable conversational features and the current operating mode are clearly shown.

## 7. Functional requirements

| ID | Release | Problem | Requirement |
|---|---|---|---|
| FR-001 | V1 | PROB-008 | A visitor shall enter an isolated guest workspace without registration, installation, or user-supplied API keys. |
| FR-002 | V1 | PROB-008 | A guest workspace shall support one active tournament and provide Create new tournament, Reset demo, Delete workspace, and Export tournament actions. |
| FR-003 | V1 | PROB-008 | The product shall provide at least one geographically neutral/international sample and one Pakistan-based sample. |
| FR-004 | V1 | PROB-001 | The product shall guide the organizer through every input required to create a schedulable tournament. |
| FR-005 | V1 | PROB-001 | Natural-language input and structured controls shall read from and update the same tournament state. |
| FR-006 | V1 | PROB-001 | Important constraints and decisions shall remain reviewable outside chat history. |
| FR-007 | V1 | PROB-001 | The organizer shall review, edit, and explicitly confirm hard constraints before schedule generation. |
| FR-008 | V1 | PROB-002 | Version 1 shall enforce the approved fixed competition format and reject unsupported scale or formats. |
| FR-009 | V1 | PROB-004 | One generation request shall produce Balanced, Weather-first, and Fairness-first alternatives from the same confirmed hard constraints. |
| FR-010 | V1 | PROB-004 | The organizer may request a Custom priorities alternative without forcing an unnecessary solver run during the default flow. |
| FR-011 | V1 | PROB-002 | No schedule or repair may be displayed as acceptable until it passes independent deterministic validation. |
| FR-012 | V1 | PROB-004 | The comparison experience shall show consistent metrics and known soft-constraint violations for every alternative. |
| FR-013 | V1 | PROB-006 | Any agent recommendation or ranking shall cite the validated metrics and constraints supporting it. |
| FR-014 | V1 | PROB-005 | The organizer shall explicitly approve a draft before it becomes the official workspace schedule. |
| FR-015 | V1 | PROB-005 | Every official schedule shall have a version and timestamp, and superseded versions shall remain in audit history. |
| FR-016 | V1 | PROB-005 | Version 1 shall support rain and venue-unavailability disruptions before match start. |
| FR-017 | V1 | PROB-005 | Recovery shall begin from the latest official schedule and produce a draft that attempts to minimize changes. |
| FR-018 | V1 | PROB-005 | The organizer shall see preserved fixtures, changed fixtures, metric differences, and new trade-offs before approving a repair. |
| FR-019 | V1 | PROB-005 | Rejecting or cancelling a draft shall leave the latest official schedule unchanged. |
| FR-020 | V1 | PROB-005 | Organizers may move, pin, or block a fixture and classify the request as required or preferred. |
| FR-021 | V1 | PROB-002 | A required edit shall require explicit confirmation as a hard constraint; a preferred edit shall remain a soft priority. |
| FR-022 | V1 | PROB-002 | An infeasible request shall produce no acceptable schedule and shall preserve all confirmed hard constraints. |
| FR-023 | V1 | PROB-002 | For infeasibility, CrickOps shall explain likely conflicts, suggest concrete remedies, and require explicit reconfirmation of any changed hard constraint. |
| FR-024 | V1 | PROB-007 | A human-readable activity timeline shall record material interpretations, confirmations, edits, requests, validation outcomes, approvals, disruptions, repairs, and rejections. |
| FR-025 | V1 | PROB-007 | The workspace shall retain approved decisions, custom priorities, edits, structured feedback, and repair outcomes across refreshes and short return visits. |
| FR-026 | V1 | PROB-007 | When rejecting or changing a recommendation, the organizer may provide an optional structured reason and optional free-text context. |
| FR-027 | V1 | PROB-007 | Agents shall use relevant workspace decisions to avoid repeating rejected recommendations during the same tournament. |
| FR-028 | V1 | PROB-009 | The product shall show whether it is operating in primary agent, fallback-model, or deterministic mode. |
| FR-029 | V1 | PROB-009 | Deterministic mode shall preserve structured setup, schedule generation, validation, profile comparison, demo weather, recovery, approval, export, and audit access. |
| FR-030 | V1 | PROB-009 | The product shall not fabricate conversational output when an agent capability is unavailable. |
| FR-031 | V1 | PROB-010 | The organizer shall be warned not to enter personal, confidential, financial, or payment information. |
| FR-032 | V1 | PROB-010 | Inactive guest workspaces shall be automatically deleted after the documented limited retention period. |
| FR-033 | V1 | PROB-010 | Delete workspace and Reset demo shall clearly state their effect and require confirmation when data loss would occur. |
| FR-034 | V1 | PROB-008 | The complete hero journey shall be executable in the public application without manual backend intervention. |
| FR-035 | V1 | PROB-006 | The product shall distinguish live results, deterministic demo data, and explicitly labelled emergency cached results. |
| FR-036 | Optional | PROB-007 | With separate consent, anonymized structured feedback may be retained for product evaluation beyond workspace expiration. |
| FR-037 | Future | PROB-007 | Authenticated organizers may retain preferences across tournaments. |

## 8. Tournament and scheduling requirements

| ID | Release | Problem | Requirement |
|---|---|---|---|
| SCHED-001 | V1 | PROB-002 | A tournament shall contain exactly eight uniquely identified teams assigned to exactly two groups of four. |
| SCHED-002 | V1 | PROB-002 | The group stage shall be a single round-robin within each group, producing 12 group matches. |
| SCHED-003 | V1 | PROB-002 | The knockout stage shall contain two semifinals and one final using qualification placeholders, producing 15 total matches. |
| SCHED-004 | V1 | PROB-002 | Semifinal pairings shall be Group A Winner versus Group B Runner-up and Group B Winner versus Group A Runner-up. |
| SCHED-005 | V1 | PROB-002 | A tournament shall contain exactly two venues with name, city, country, time zone, and a resolvable geographic location. |
| SCHED-006 | V1 | PROB-002 | The tournament window shall be between 7 and 21 calendar days inclusive. |
| SCHED-007 | V1 | PROB-001 | Organizers shall define available venue-date-time slots and may use different slot patterns by date or day type. |
| SCHED-008 | V1 | PROB-001 | Supported organizer constraints shall include team and venue blackouts, minimum rest, fixture pins, slot exclusions, rivalry preferences, and preferred time slots. |
| SCHED-009 | V1 | PROB-002 | Hard constraints shall include format integrity, one placement per match, no team overlap, venue-slot capacity, confirmed blackouts, confirmed rest requirements, knockout dependencies, and confirmed required edits. |
| SCHED-010 | V1 | PROB-004 | Soft priorities shall include weather risk, rest fairness, venue balance, slot balance, organizer preferences, audience timing, and change minimization where applicable. |
| SCHED-011 | V1 | PROB-004 | Balanced, Weather-first, and Fairness-first shall be distinct configurable priority presets rather than different hard-rule sets. |
| SCHED-012 | V1 | PROB-004 | Custom priorities shall allow simple adjustment of weather, rest, venue, slot, and replan-stability priorities. |
| SCHED-013 | V1 | PROB-004 | Comparison metrics shall use the same definitions and scale across all alternatives in one comparison. |
| SCHED-014 | V1 | PROB-002 | If capacity, rest, dependencies, blackouts, or other confirmed hard constraints make the tournament infeasible, the product shall return no valid schedule. |
| SCHED-015 | V1 | PROB-002 | A remedy proposal shall not alter a hard constraint until the organizer edits and reconfirms it. |
| SCHED-016 | V1 | PROB-003 | Slot scoring shall consider local time and venue conditions; it shall not apply universal seasonal assumptions. |
| SCHED-017 | V1 | PROB-003 | Rest assessment shall include the transition from group matches to knockout placeholders. |
| SCHED-018 | Future | PROB-002 | Additional teams, groups, venues, tournament windows, and knockout structures may be supported in future releases. Match formats are governed separately by SCHED-022–SCHED-025. |
| SCHED-019 | Future | PROB-003 | Travel-first optimization may use real distance, travel-time, accommodation, and multi-city data. |
| SCHED-020 | V1 | PROB-002 | No team shall play more than once within the same venue-local calendar day, even when its available match slots do not overlap. |
| SCHED-021 | V1 | PROB-002 | All 12 group-stage matches shall complete before either semifinal begins, and both semifinals shall complete before the final begins. |
| SCHED-022 | V1 | PROB-002 | The organizer shall select one tournament-wide match-format preset: T10 or T20. The official sample and hero demonstration shall use T20. |
| SCHED-023 | V1 | PROB-002 | T10 shall use a 120-minute operational venue allocation block and T20 a 240-minute block for every fixture. These planning defaults include expected play, normal intervals, setup, and turnover and shall not be represented as guaranteed match durations. |
| SCHED-024 | V1 | PROB-002 | Slot eligibility, overlap, capacity, rest, weather exposure, and recovery shall use the selected preset’s allocation block. Organizers may define start times but shall not customize individual fixture duration. |
| SCHED-025 | Optional | PROB-002 | ODI may be added only after the Version 1 completion gate passes. Test and other multi-day formats remain future scope. |
| SCHED-026 | V1 | PROB-002 | Both tournament venues shall use the same confirmed IANA timezone. The tournament’s one-match-per-local-day, chronology, rest, weather, and display behavior shall use that shared timezone. |
| SCHED-027 | Future | PROB-002 | Multi-timezone tournaments are deferred until travel and cross-timezone operating rules are supported. |
| SCHED-028 | V1 | PROB-001 | The organizer shall enter the venue display name separately. Location search shall use city, country, administrative area, or postal code and shall not claim automatic cricket-ground discovery. The organizer shall confirm a returned coordinate and IANA timezone; manual coordinates remain available as fallback. |
| SCHED-029 | V1 | PROB-002 | Selected fixture allocation intervals at the same venue shall never overlap, even when represented by different slot IDs. The complete T10 or T20 operational allocation block shall fit within venue availability. |
| SCHED-030 | V1 | PROB-002 | Knockout placeholders shall preserve qualification-role exclusivity: A1 and A2 are different teams, B1 and B2 are different teams, no team can occupy both semifinals, every possible group-to-semifinal rest path is protected, and final rest is protected through either semifinal-winner path. |

## 9. Weather-intelligence requirements

| ID | Release | Problem | Requirement |
|---|---|---|---|
| WEATHER-001 | V1 | PROB-003 | Live mode shall calculate fixture risk from the scheduled venue’s geographic coordinates and local match time. |
| WEATHER-002 | V1 | PROB-008 | Deterministic demo mode shall provide fixed, reproducible conditions for testing and demonstration. |
| WEATHER-003 | V1 | PROB-003 | Each scheduled fixture shall show a risk level, relevant contributing conditions, forecast time, and an uncertainty or data-quality indication. |
| WEATHER-004 | V1 | PROB-003 | Weather shall influence scheduling as a soft factor by default. |
| WEATHER-005 | V1 | PROB-003 | The product may flag severe rain, heat, wind, lightning, or other potentially unsafe conditions without claiming official safety authority. |
| WEATHER-006 | V1 | PROB-001 | An organizer may define visible precipitation, temperature, or wind thresholds and explicitly confirm them as hard constraints. |
| WEATHER-007 | V1 | PROB-005 | When a forecast crosses a confirmed hard threshold, the affected venue-time slot shall be treated as unavailable and recovery shall be offered. |
| WEATHER-008 | V1 | PROB-009 | Missing, stale, incomplete, or unavailable forecast data shall be clearly labelled and shall not be converted into a misleading low-risk score. |
| WEATHER-009 | V1 | PROB-003 | The product shall state that weather information is planning guidance and cannot guarantee safety, forecast precision, or washout prevention. |
| WEATHER-010 | V1 | PROB-003 | Version 1 shall not claim radar nowcasting, hyperlocal certainty, or equal forecast precision in every location. |
| WEATHER-011 | Future | PROB-003 | Radar, satellite, sensor, and probabilistic nowcasting capabilities may augment forecast guidance. |
| WEATHER-012 | V1 | PROB-003 | Comparisons shall report weather coverage separately from weather risk. Uncovered fixtures shall retain unknown risk, and a Weather-first option with incomplete coverage shall not appear safer without a prominent coverage warning. |
| WEATHER-013 | V1 | PROB-003 | The product interface, tournament export, and README shall attribute the active weather-data provider. |

## 10. Agent-related requirements

| ID | Release | Problem | Requirement |
|---|---|---|---|
| AGENT-001 | V1 | PROB-006 | The Tournament Director shall own the organizer conversation, coordinate relevant specialists, present evidence-backed options, and request explicit approval. |
| AGENT-002 | V1 | PROB-001 | The Rules and Constraint Specialist shall convert organizer input into reviewable structured constraints, identify ambiguity, and surface contradictions. |
| AGENT-003 | V1 | PROB-004 | The Scheduling Strategy Specialist shall map confirmed organizer priorities to schedule-generation requests and compare strategy-level outcomes. |
| AGENT-004 | V1 | PROB-003 | The Weather Intelligence Specialist shall explain fixture risk, uncertainty, and weather-driven disruption scenarios using deterministic weather results. |
| AGENT-005 | V1 | PROB-003 | The Fairness and Logistics Auditor shall independently assess rest, venue distribution, slot allocation, and preference satisfaction. |
| AGENT-006 | V1 | PROB-005 | The Disruption and Recovery Specialist shall identify affected fixtures and explain validated minimum-change repair options. |
| AGENT-007 | V1 | PROB-006 | No agent shall create, mutate, validate, or repair fixtures without invoking the authoritative deterministic capability. |
| AGENT-008 | V1 | PROB-006 | Every agent-assisted application decision shall record the role, provider, model, timestamp, relevant tool outcome, and validation status. |
| AGENT-009 | V1 | PROB-006 | All six roles shall be operational and perform meaningful, traceable work where relevant; no role shall be invoked merely to satisfy an agent-count requirement. |
| AGENT-010 | V1 | PROB-006 | Specialists shall not merely paraphrase another specialist’s output and shall have bounded responsibilities and prohibited actions. |
| AGENT-011 | V1 | PROB-006 | Agents shall ask targeted clarification rather than inventing missing hard constraints. |
| AGENT-012 | V1 | PROB-009 | Primary and fallback providers may produce different recommendations, but they shall use the same application-level schemas, equivalent validation and approval protections, the same hard-constraint safety guarantees, and outputs accepted by the same deterministic checks. |
| AGENT-013 | V1 | PROB-009 | A fallback response shall never bypass validation, approval, or hard-constraint protections. |
| AGENT-014 | V1 | PROB-006 | Raw hidden reasoning shall never be requested for or exposed to organizers. |
| AGENT-015 | Optional | PROB-006 | The Communications Specialist may generate stakeholder-specific messages only after the Version 1 completion gate. |

## 11. Recovery requirements

| ID | Release | Problem | Requirement |
|---|---|---|---|
| RECOVERY-001 | V1 | PROB-005 | Rain and venue-unavailability events shall be expressible as unavailable venue-time slots. |
| RECOVERY-002 | V1 | PROB-005 | Recovery shall use the latest approved schedule as its immutable baseline. |
| RECOVERY-003 | V1 | PROB-005 | The primary recovery objective shall minimize disruption while preserving every confirmed hard constraint. |
| RECOVERY-004 | V1 | PROB-005 | Unaffected official fixtures shall be preserved whenever feasible. |
| RECOVERY-005 | V1 | PROB-005 | If no valid repair exists, the product shall preserve the official schedule and follow the infeasibility workflow. |
| RECOVERY-006 | V1 | PROB-005 | A repaired schedule shall remain a draft until independently validated and explicitly approved. |
| RECOVERY-007 | V1 | PROB-005 | Repair comparison shall identify added, removed, moved, and unchanged fixture placements plus metric deltas. |
| RECOVERY-008 | V1 | PROB-005 | Approving a repair shall create a new official version without deleting the prior version. |
| RECOVERY-009 | V1 | PROB-005 | Venue unavailability shall be fully testable even when omitted from the primary demo video. |
| RECOVERY-010 | Future | PROB-005 | Team withdrawal, security incidents, lighting failure, transport disruption, unavailable officials, and in-progress match delays may be supported later. |

## 12. Fairness and logistics requirements

| ID | Release | Problem | Requirement |
|---|---|---|---|
| FAIR-001 | V1 | PROB-003 | Every displayed schedule shall receive an independent fairness assessment after deterministic validation. |
| FAIR-002 | V1 | PROB-003 | The assessment shall cover minimum and distribution of rest, venue allocation, time-slot allocation, and organizer-preference satisfaction. |
| FAIR-003 | V1 | PROB-003 | The assessment shall compare team treatment and identify material outliers without claiming that one subjective definition of fairness is universal. |
| FAIR-004 | V1 | PROB-006 | Fairness explanations shall use schedule-derived evidence and distinguish hard violations from soft trade-offs. |
| FAIR-005 | V1 | PROB-006 | The fairness auditor shall not alter fixtures directly. |
| FAIR-006 | Future | PROB-003 | Travel burden and home/away balance may be added when relevant data and formats are supported. |

## 13. Approval requirements

| ID | Release | Problem | Requirement |
|---|---|---|---|
| APPROVAL-001 | V1 | PROB-006 | Explicit organizer confirmation is required before hard constraints become authoritative. |
| APPROVAL-002 | V1 | PROB-005 | Explicit organizer approval is required before a draft becomes the official workspace schedule. |
| APPROVAL-003 | V1 | PROB-005 | Conversational agreement alone shall not approve a schedule or repair. |
| APPROVAL-004 | V1 | PROB-005 | Approval controls shall identify the draft version and summarize the effect of the action. |
| APPROVAL-005 | V1 | PROB-005 | A new approval shall supersede but not delete the previous official version. |
| APPROVAL-006 | V1 | PROB-006 | Changing a confirmed hard constraint shall require explicit reconfirmation and an audit entry. |
| APPROVAL-007 | V1 | PROB-005 | Version 1 terminology shall use Approve schedule or Set as official workspace schedule and shall not imply external publication. |
| APPROVAL-008 | Future | PROB-005 | External publication, sharing, and stakeholder notification require separate approval workflows. |

## 14. Frontend experience requirements

| ID | Release | Problem | Requirement |
|---|---|---|---|
| UX-001 | V1 | PROB-001 | The workspace shall combine Tournament Director chat, structured tournament controls, and dedicated result panels. |
| UX-002 | V1 | PROB-001 | The organizer shall always be able to locate and edit current teams, venues, dates, slots, constraints, and priorities. |
| UX-003 | V1 | PROB-004 | Profile alternatives shall be comparable side by side without requiring interpretation of raw solver output. |
| UX-004 | V1 | PROB-003 | Weather indicators shall expose risk, contributing factors, data freshness, and uncertainty in accessible text as well as visual treatment. |
| UX-005 | V1 | PROB-005 | Before-and-after repair differences shall distinguish preserved and changed fixtures. |
| UX-006 | V1 | PROB-009 | Multi-step operations shall show current stage, progress, and actionable failure or retry states. |
| UX-007 | V1 | PROB-009 | The current operating mode shall be visible without distracting from the primary workflow. |
| UX-008 | V1 | PROB-008 | Sample tournaments shall allow the hero flow to begin immediately while retaining access to guided setup. |
| UX-009 | V1 | PROB-006 | Validation status shall be visible for every schedule and repair. |
| UX-010 | V1 | PROB-008 | The interface shall support international venue names, local dates, local times, and explicit time zones. |
| UX-011 | V1 | PROB-001 | Empty, loading, success, degraded, infeasible, unavailable-data, and unexpected-error states shall provide a clear next action. |
| UX-012 | V1 | PROB-010 | Destructive workspace actions shall use clear labels and confirmation. |

## 15. Accessibility requirements

| ID | Release | Requirement |
|---|---|---|
| ACCESS-001 | V1 | Core setup, comparison, approval, disruption, and recovery workflows shall be keyboard operable. |
| ACCESS-002 | V1 | Controls shall have programmatically determinable labels, instructions, errors, and status messages. |
| ACCESS-003 | V1 | Weather, validation, fairness, and difference states shall not rely on color alone. |
| ACCESS-004 | V1 | Text and essential interface elements shall meet WCAG 2.2 AA contrast expectations. |
| ACCESS-005 | V1 | Focus order and focus visibility shall remain clear through dialogs and dynamic updates. |
| ACCESS-006 | V1 | Tables and comparisons shall provide understandable headings and accessible summaries. |

## 16. Non-functional requirements

| ID | Release | Problem | Requirement |
|---|---|---|---|
| NFR-001 | V1 | PROB-002 | Deterministic generation and repair shall produce repeatable validity outcomes for identical confirmed inputs. |
| NFR-002 | V1 | PROB-008 | Agent interpretation should ideally complete within 10 seconds under expected demo conditions. |
| NFR-003 | V1 | PROB-008 | Three-profile generation and validation should ideally complete within 30 seconds under expected demo conditions. |
| NFR-004 | V1 | PROB-008 | Disruption repair should ideally complete within 15 seconds under expected demo conditions. |
| NFR-005 | V1 | PROB-009 | Operations shall use bounded retries and timeouts and shall fail into an explicit recoverable or degraded state. |
| NFR-006 | V1 | PROB-010 | Concurrent guest workspaces shall remain logically isolated. |
| NFR-007 | V1 | PROB-007 | Approved state and audit records shall survive refreshes and short return visits during the retention period. |
| NFR-008 | V1 | PROB-008 | The hero journey shall run repeatedly without manual data repair or administrative intervention. |
| NFR-009 | V1 | PROB-009 | The application shall expose clear health and dependency status suitable for operation and diagnosis. |
| NFR-010 | V1 | PROB-008 | The deployed product shall remain portable across equivalent hosting environments. |
| NFR-011 | V1 | PROB-006 | Every authoritative schedule result shall be traceable to confirmed inputs, deterministic output, validation, and approval state. |
| NFR-012 | V1 | PROB-010 | Guest data deletion and expiration shall be reliable and auditable without exposing deleted content. |
| NFR-013 | V1 | PROB-008 | Public-demo usage shall be protected by explicit per-workspace, per-IP, provider-budget, agent-turn, and solver-concurrency limits with a deterministic-mode emergency switch. |

Performance values are evaluation targets, not contractual guarantees.

## 17. Security and privacy requirements

| ID | Release | Problem | Requirement |
|---|---|---|---|
| SEC-001 | V1 | PROB-010 | No guest shall be able to read or mutate another guest workspace by guessing or modifying an identifier. |
| SEC-002 | V1 | PROB-010 | Secrets and provider credentials shall never be delivered to the client or required from judges. |
| SEC-003 | V1 | PROB-010 | All externally supplied data shall be validated before use by agents or deterministic capabilities. |
| SEC-004 | V1 | PROB-006 | Agent content shall not have authority to bypass deterministic validation, approvals, or workspace isolation. |
| SEC-005 | V1 | PROB-010 | Raw prompts, hidden reasoning, tokens, stack traces, and low-level diagnostics shall not appear in the organizer interface or export. |
| SEC-006 | V1 | PROB-010 | Guest retention duration and automatic deletion behavior shall be disclosed. |
| SEC-007 | V1 | PROB-010 | Product-wide retention of anonymized structured feedback shall require separate, informed consent. |
| SEC-008 | V1 | PROB-010 | Withdrawal of optional feedback consent shall not prevent use of the core guest workspace. |
| SEC-009 | V1 | PROB-010 | Reset demo shall remove current tournament state; Delete workspace shall remove the guest workspace and its non-consented data. |

## 18. Data requirements

| ID | Release | Requirement |
|---|---|---|
| DATA-001 | V1 | The product shall retain the current tournament configuration, constraints, generated options, metrics, validation results, official versions, drafts, disruptions, repairs, feedback, and audit events needed by the approved journeys. |
| DATA-002 | V1 | A guest workspace shall have exactly one active tournament while retaining the version history of that tournament. |
| DATA-003 | V1 | Every official schedule and draft shall be distinguishable and associated with its originating confirmed constraints. |
| DATA-004 | V1 | Venue data shall include sufficient location and time-zone information for fixture-local weather assessment. |
| DATA-005 | V1 | Every agent-assisted decision shall retain provider and model provenance without storing hidden reasoning. |
| DATA-006 | V1 | Structured feedback reasons shall include weather preference, unfair rest distribution, venue preference, unsuitable time slot, rivalry requirement, travel concern, and other. |
| DATA-007 | V1 | Export shall contain organizer-useful tournament state and history without secrets or internal diagnostics. |
| DATA-008 | V1 | Guest workspace data shall expire automatically after the limited inactive period defined in `spec.md`. |
| DATA-009 | V1 | Optional product-improvement feedback shall remain logically separate from expiring guest-workspace data and retain its consent record. |
| DATA-010 | Future | Cross-tournament organizer preferences may be stored only when a reliable returning-user identity exists. |

## 19. Observability and explainability requirements

| ID | Release | Problem | Requirement |
|---|---|---|---|
| OBS-001 | V1 | PROB-006 | Internal observability shall capture agent runs, tool interactions, provider metadata, validation outcomes, errors, latency, and approval events needed for debugging and hackathon evidence. |
| OBS-002 | V1 | PROB-006 | Organizer explanations shall identify the confirmed constraints and validated metrics relevant to the conclusion. |
| OBS-003 | V1 | PROB-009 | When central agent tracing is unavailable, local application observability shall continue to record operational evidence. |
| OBS-004 | V1 | PROB-009 | Dependency failures, fallback transitions, and recovery to the primary mode shall be observable. |
| OBS-005 | V1 | PROB-006 | Internal traces shall be access-controlled and shall not be exposed through organizer-facing error messages. |
| OBS-006 | V1 | PROB-008 | The team shall be able to demonstrate genuine agent participation separately from any labelled emergency cache. |

## 20. Failure states and required behavior

| ID | Failure state | Required Version 1 behavior |
|---|---|---|
| FAIL-001 | Missing or ambiguous required input | Identify the missing decision and ask one targeted clarification at a time. |
| FAIL-002 | Unsupported format or scale | Explain the fixed Version 1 boundary and prevent scheduling. |
| FAIL-003 | Deterministically infeasible constraints | Return no acceptable schedule; explain evidence and remedies; preserve hard constraints. |
| FAIL-004 | Solver timeout or internal generation failure | Keep confirmed state, show failure, permit a safe retry, and never display a partial schedule as valid. |
| FAIL-005 | Independent validation failure | Suppress the option from approval, record the failure internally, and offer retry or correction. |
| FAIL-006 | Live forecast unavailable or incomplete | Label weather as unavailable or partial and offer deterministic demo mode; do not assign misleading low risk. |
| FAIL-007 | Primary model unavailable | Apply limited retries, then use a compatible configured fallback and visibly change mode. |
| FAIL-008 | All model providers unavailable | Enter deterministic mode and clearly disable conversational interpretation and narrative explanation. |
| FAIL-009 | Repair infeasible | Preserve the official schedule, explain the conflict, and offer constraint or capacity remedies. |
| FAIL-010 | Guest workspace expired | Explain expiration and offer a new blank or sample workspace without revealing prior data. |
| FAIL-011 | Session or workspace mismatch | Deny access and create or recover only the requesting guest’s workspace. |
| FAIL-012 | Export failure | Preserve workspace state, report the failure, and permit retry. |
| FAIL-013 | Unexpected application error | Show a safe, non-technical error with recovery action and retain diagnostic context internally. |

## 21. Edge cases

Version 1 verification must cover at least:

- Duplicate team or venue names.
- Teams missing a group or groups with the wrong size.
- Invalid, reversed, or out-of-range dates.
- Time slots outside the tournament window or with invalid local times.
- Daylight-saving or time-zone boundary behavior where applicable.
- Venue coordinates that cannot be resolved or conflict with entered location text.
- Fewer than 15 usable venue slots.
- Adequate raw capacity that becomes infeasible after rest, knockout, or blackout constraints.
- A team or venue assigned to overlapping matches.
- Minimum rest spanning midnight or group-to-knockout boundaries.
- Identical or near-identical profile outcomes.
- A Custom priorities request that conflicts with confirmed hard constraints.
- Live weather missing for one venue but available for the other.
- Forecast changes after approval without crossing a confirmed threshold.
- Forecast changes that cross a confirmed hard threshold.
- A disruption affecting one fixture, multiple fixtures, or a knockout placeholder.
- A repair request when no official schedule exists.
- Multiple unapproved drafts and cancellation back to the official baseline.
- Expired guest data, manual deletion, reset, and concurrent judge sessions.
- Provider fallback that lacks a required capability or returns invalid structured output.
- T10 and T20 runs using identical available start times, including their capacity, overlap, weather-window, rest, and repair differences.

## 22. Acceptance criteria

| ID | Requirement links | Acceptance criterion |
|---|---|---|
| AC-001 | SCHED-001–SCHED-004, SCHED-021 | A valid tournament produces exactly 12 unique group matches, two correct semifinal placeholders, and one final placeholder; every group match completes before either semifinal begins, and both semifinals complete before the final begins. |
| AC-002 | FR-009–FR-013 | One request displays three validated profile options with consistent comparison metrics and evidence-grounded explanations. |
| AC-003 | FR-011, SCHED-009 | Seeded hard-rule violations are detected, and the affected schedule cannot be approved. |
| AC-004 | FR-022–FR-023 | An infeasible test case produces no acceptable schedule, identifies conflicts, proposes remedies, and preserves hard constraints until reconfirmed. |
| AC-005 | WEATHER-001–WEATHER-003 | A live-mode fixture shows coordinate- and time-specific weather risk, forecast time, contributors, and uncertainty/data quality. |
| AC-006 | WEATHER-002 | Re-running the same deterministic demo scenario produces the same weather inputs and risk results. |
| AC-007 | WEATHER-006–WEATHER-007 | A visible organizer-confirmed weather threshold becomes a hard constraint and crossing it offers recovery for the affected slot. |
| AC-008 | RECOVERY-001–RECOVERY-008 | A rain disruption produces a valid draft, preserves unaffected fixtures where feasible, shows a complete difference, and creates a new official version only after approval. |
| AC-009 | RECOVERY-009 | A venue-unavailability test completes the same validated recovery and approval workflow. |
| AC-010 | FR-020–FR-021 | Required and preferred controlled edits affect hard and soft behavior respectively and never bypass validation. |
| AC-011 | APPROVAL-001–APPROVAL-007 | No conversational message alone can confirm a hard constraint or replace the official schedule. |
| AC-012 | FR-024–FR-027 | Material actions appear in the activity timeline, and a rejected recommendation with structured feedback is not repeated without new evidence. |
| AC-013 | AGENT-001–AGENT-010 | Trace evidence shows relevant, non-redundant specialist work and deterministic tool authority throughout the hero flow. |
| AC-014 | FR-028–FR-030 | Simulated provider outages visibly transition through fallback and deterministic modes without fabricated agent responses. |
| AC-015 | FR-001–FR-003, NFR-006 | Two concurrent guests can complete independent flows without viewing or changing each other’s data. |
| AC-016 | FR-025, DATA-001–DATA-003 | Refreshing or returning within the retention period restores the active tournament, official version, drafts, and audit history. |
| AC-017 | FR-032–FR-033, DATA-008 | Expired or deleted guest workspaces cannot be recovered through the organizer interface. |
| AC-018 | ACCESS-001–ACCESS-006 | The hero workflow is keyboard operable, labelled, focus-safe, and understandable without color-only cues. |
| AC-019 | FR-034–FR-035 | The public hero journey completes using genuine generation, validation, agent participation, and repair; any cache is visibly labelled emergency fallback. |
| AC-020 | UX-010 | Fixtures and weather are shown in the venue’s correct local date, time, and named time zone. |
| AC-021 | SCHED-020 | Across every displayed schedule and repair, each team appears in at most one match on any venue-local calendar day, including when candidate slots do not overlap. |
| AC-022 | SCHED-022–SCHED-024 | The same valid tournament can be generated under T10 and T20 presets; every T10 placement uses a 120-minute operational block and every T20 placement a 240-minute block, with no individual-duration control exposed. |
| AC-023 | SCHED-023–SCHED-024 | For identical available start times, switching from T10 to T20 changes capacity and overlap eligibility consistently, and weather exposure, rest, validation, and repair use the selected block without describing it as a guaranteed match duration. |
| AC-024 | SCHED-026–SCHED-028 | Venue setup stores the display name separately, searches only location text, requires confirmed coordinates and a shared IANA timezone, supports manual-coordinate fallback, and rejects a different-timezone pair with a clear Version 1 boundary message. |
| AC-025 | WEATHER-012 | A comparison reports weather risk only across covered fixtures and reports coverage independently; uncovered fixture risk is null, and incomplete coverage produces a visible warning and missing-coverage optimization penalty. |
| AC-026 | SCHED-023–SCHED-024, SCHED-029 | The solver and independent validator reject partial same-venue overlap, identical intervals under different slot IDs, and allocation blocks extending beyond venue availability for both T10 and T20. |
| AC-027 | SCHED-021, SCHED-030 | Qualification-role exclusivity and every possible knockout rest path are validated, while both semifinals may be scheduled on the same local day when venue intervals and rest rules permit it. |

## 23. Evaluation metrics

| ID | Metric | Version 1 target |
|---|---|---|
| METRIC-001 | Hard-constraint validity | 100% of displayed schedules and repairs pass independent validation. |
| METRIC-002 | Infeasibility safety | 100% of seeded infeasible cases are blocked from approval. |
| METRIC-003 | Format completeness | 100% of valid runs contain the correct 15-match structure without duplicates or omissions. |
| METRIC-004 | Recovery stability | Unaffected fixtures are preserved whenever a valid repair permits; changes are fully reported. |
| METRIC-005 | Demo reproducibility | Deterministic rain scenario produces repeatable inputs and a valid recovery across repeated runs. |
| METRIC-006 | Workspace isolation | Zero cross-workspace access in concurrency and identifier-manipulation tests. |
| METRIC-007 | Traceability | Every official version traces to confirmed constraints, generation, validation, and explicit approval. |
| METRIC-008 | Agent meaningfulness | Every invoked specialist contributes role-specific evidence or a decision used by the flow; no ceremonial calls. |
| METRIC-009 | Hero reliability | The full hero journey succeeds repeatedly in the deployed environment without manual repair. |
| METRIC-010 | Hero duration | The demonstrated journey fits within three minutes using preloaded data and a short prompt. |
| METRIC-011 | Accessibility | No critical accessibility failure in the required hero workflow. |
| METRIC-012 | Performance | Interpretation, three-profile generation, and repair are monitored against the directional 10/30/15-second targets. |

## 24. Demo requirements

The required primary demonstration shall:

1. Load a ready-made tournament.
2. Submit one short natural-language scheduling request.
3. Review and confirm interpreted constraints.
4. Generate Balanced, Weather-first, and Fairness-first schedules.
5. Show all three passing independent validation.
6. Compare weather risk, rest fairness, venue balance, slot balance, and preference satisfaction.
7. Approve one option as the official workspace schedule.
8. Trigger deterministic rain disruption.
9. Generate a minimum-change repaired draft.
10. Show preserved and changed fixtures, metric differences, and recovery reasoning.
11. Approve the repaired schedule.
12. Show the new version and audit entries.

The official flow shall use the designated OpenAI model whenever available. Schedule generation, validation, specialist participation, and repair must execute genuinely. Deterministic weather is permitted; emergency cached results must be explicitly labelled and cannot substitute for the main demonstration.

## 25. Deployment requirements

| ID | Release | Requirement |
|---|---|---|
| DEPLOY-001 | V1 | Judges shall access a public web application without installation, registration, user-supplied keys, or local setup. |
| DEPLOY-002 | V1 | The public environment shall support concurrent isolated guest workspaces and persistent state across refreshes. |
| DEPLOY-003 | V1 | Production secrets shall remain server-side and frontend access shall be restricted to approved backend origins. |
| DEPLOY-004 | V1 | The environment shall expose clear application and dependency health states. |
| DEPLOY-005 | V1 | A local development path shall exist but shall not be required for judging. |
| DEPLOY-006 | V1 | The solution shall remain portable if the preferred hosting environment becomes unsuitable. |
| DEPLOY-007 | V1 | Deterministic demo mode shall remain available when live weather or an external agent provider fails. |
| DEPLOY-008 | V1 | Browser workspace requests shall preserve secure guest-session continuity across the deployed frontend and backend, resist cross-site mutation, prevent shared/intermediary caching of private workspace responses, and keep preview environments isolated from production data. |

Named hosting services, environment topology, database selection, CORS policy details, and secret-management mechanisms belong in `spec.md`.

## 26. Future requirements

### Version 1.1 — Optional only after Version 1 stability

- Communications Specialist.
- Public fixture pages and shareable links.
- Stakeholder messages and WhatsApp, email, calendar, SMS, or push delivery.
- Authentication, roles, and cross-tournament organizer preferences.
- Basic scoring, standings, qualification scenarios, and results-driven knockout progression.
- Match-official assignment.
- Broader formats only if the fixed hero journey remains reliable.

### Post-hackathon

- Team and player registration.
- Mobile clients, payments, venue booking, and automatic venue discovery.
- Multi-city travel, accommodation, and Travel-first optimization.
- Advanced standings, verified DLS, live scoring, and ball-by-ball integrations.
- Radar, sensors, satellite data, and probabilistic nowcasting.
- Reserve days, broadcast, security, transport, official availability, and large multi-division competitions.

## 27. Version 1 completion gate

Version 1 cannot be declared complete until:

- All V1 acceptance criteria pass with evidence.
- No displayed schedule or repair has a hard violation.
- Infeasible inputs and provider failures are handled safely.
- Both sample tournaments and both disruption types are verified.
- The six specialist roles are operational and perform meaningful, traceable work where relevant.
- The deployed hero journey is repeatable and fits the presentation.
- Guest isolation, retention, deletion, export, and recovery behavior are verified.
- Optional features have not compromised the required flow.

## 28. Scope traceability and conflicts

This PRD implements the approved strategic boundary in `scope.md`. It intentionally does not select endpoint shapes, data schemas, solver variables, model adapters, tracing processors, storage mechanisms, retention duration, deployment topology, or framework structure; those decisions belong in `spec.md`.

No approved scope conflict is intentionally resolved or expanded by this PRD. Any later conflict must be raised and approved before either document changes.
