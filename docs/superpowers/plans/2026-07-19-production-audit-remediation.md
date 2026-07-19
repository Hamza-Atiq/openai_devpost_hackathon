# Production Audit Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the confirmed production audit gaps and prove the complete agent, weather, recovery, history, accessibility, and failure-state experience on the deployed application.

**Architecture:** A shared backend specialist runtime executes bounded role-specific agents only after their deterministic evidence exists, then records consumed evidence and provenance. Weather evidence is revision-bound and coordinated through one frontend state owner; remaining judge-facing gaps use focused API and presentation components without changing scheduling authority.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, OpenAI Agents SDK, pytest, Next.js 15, React 19, TypeScript, Vitest, Vercel, Railway.

## Global Constraints

- Preserve exactly eight teams, two groups, two venues, and fifteen matches.
- Agents never create, mutate, validate, repair, approve, or restore fixtures.
- Deterministic solver, validator, metric, approval, and ownership services remain authoritative.
- Invoke a specialist only when its role-specific evidence is available and consumed.
- Provider failure must preserve deterministic generation, repair, approval, and audit access.
- Weather is risk guidance and unknown coverage is never converted to a safe score.
- Approval remains workspace-internal and requires an explicit organizer action.
- Every behavior uses failing-test, minimal-fix, focused-pass, relevant-suite, and deployment verification.

---

### Task 1: Execute specialists from validated application evidence

**Requirements:** AGENT-002–AGENT-010, DATA-005, OBS-001, AC-013, METRIC-008

**Files:**
- Create: `apps/api/app/agents/specialist_runtime.py`
- Create: `apps/api/app/agents/evidence_builders.py`
- Create: `apps/api/tests/agents/test_specialist_runtime.py`
- Modify: `apps/api/app/agents/schemas.py`

**Interfaces:**
- Consumes: `AgentProviderRouter`, `ProviderRoute`, `GuestWorkspace`, validated schedule metrics/diffs, existing `create_*_agent` factories.
- Produces: `SpecialistExecutionRecord`, `SpecialistRuntime.run(role, workspace, reason)`, and role-specific immutable input builders.

- [ ] **Step 1: Write the failing specialist execution test**

```python
@pytest.mark.anyio
async def test_runtime_executes_requested_specialist_and_records_consumed_evidence():
    runner = StubRunner(output=strategy_output_with_validated_comparison())
    runtime = SpecialistRuntime(provider_router=healthy_router(), runner=runner)
    result = await runtime.run(
        role=AgentRole.SCHEDULING_STRATEGY,
        workspace=workspace_with_validated_options(),
        invocation_reason="Compare validated schedule options",
    )
    assert runner.agent_names == ["Scheduling Strategy Specialist"]
    assert result.role is AgentRole.SCHEDULING_STRATEGY
    assert result.validation_status is ValidationStatus.VALID
    assert result.tool_outcomes[0].deterministic_authority is True
    assert result.consumed_fields == ("validated_metrics", "validation_valid")
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `uv run pytest apps/api/tests/agents/test_specialist_runtime.py -q`

Expected: import failure for `SpecialistRuntime`.

- [ ] **Step 3: Implement execution records and role registry**

```python
class SpecialistExecutionRecord(DomainModel):
    role: AgentRole
    provider: str
    model: str
    occurred_at: UtcDateTime
    tournament_revision: int
    invocation_reason: str
    validation_status: ValidationStatus
    evidence_refs: tuple[EvidenceRef, ...]
    tool_outcomes: tuple[ToolOutcome, ...]
    consumed_fields: tuple[str, ...]
    organizer_summary: str

class SpecialistRuntime:
    async def run(
        self,
        *,
        role: AgentRole,
        workspace: GuestWorkspace,
        invocation_reason: str,
    ) -> SpecialistExecutionRecord:
        request = build_specialist_request(role, workspace)
        route = self._provider_router.select_primary_or_fallback()
        result = await self._runner(
            create_specialist_agent(role, model=route.model),
            request.payload.model_dump_json(),
            max_turns=request.max_turns,
            run_config=RunConfig(model_provider=route.sdk_provider),
        )
        output = request.output_type.model_validate(result.final_output)
        request.validate(output)
        return request.to_execution_record(route, output)
```

- [ ] **Step 4: Add all-role and prohibited-evidence tests**

```python
@pytest.mark.parametrize("role", tuple(role for role in AgentRole if role != AgentRole.TOURNAMENT_DIRECTOR))
@pytest.mark.anyio
async def test_every_specialist_factory_reaches_runner(role):
    result = await runtime_for(role).run(role=role, workspace=workspace_for(role), invocation_reason="required")
    assert result.role is role
    assert result.evidence_refs

@pytest.mark.anyio
async def test_runtime_rejects_unconsumed_or_fabricated_evidence():
    with pytest.raises(ValueError, match="consumed role-specific evidence"):
        await invalid_runtime.run(role=AgentRole.WEATHER_INTELLIGENCE, workspace=workspace, invocation_reason="compare risk")
```

- [ ] **Step 5: Run focused agent suites and commit**

Run: `uv run pytest apps/api/tests/agents -q`

Commit: `feat: execute specialists from validated evidence`

---

### Task 2: Ground Director answers and persist complete agent audit evidence

**Requirements:** AGENT-001, AGENT-008–AGENT-011, FR-013, DATA-005, OBS-002, AC-013

**Files:**
- Modify: `apps/api/app/agents/director.py`
- Modify: `apps/api/app/agents/runtime.py`
- Modify: `apps/api/app/api/director.py`
- Modify: `apps/api/app/api/audit.py`
- Modify: `apps/api/tests/agents/test_agent_runtime.py`
- Modify: `apps/api/tests/api/test_director_contract.py`

**Interfaces:**
- Consumes: `SpecialistRuntime`, `SpecialistExecutionRecord`.
- Produces: `DirectorTurnInput.specialist_evidence`, `DirectorRuntimeResult.specialist_evidence`, and complete organizer-safe audit provenance.

- [ ] **Step 1: Write a failing two-pass Director test**

```python
@pytest.mark.anyio
async def test_director_executes_requested_weather_specialist_then_answers_from_metrics():
    runtime = director_runtime(first_pass=requests_weather(), second_pass=grounded_answer(), specialist=weather_runtime())
    result = await runtime.run_turn(workspace=workspace_with_validated_options(), user_message="Which has the lowest weather risk and why?")
    assert result.message == "Weather-first has the lowest validated risk at 34.9%."
    assert result.specialist_evidence[0].role is AgentRole.WEATHER_INTELLIGENCE
    assert result.specialist_evidence[0].consumed_fields
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest apps/api/tests/agents/test_agent_runtime.py -q`

Expected: `DirectorRuntimeResult` has no `specialist_evidence`.

- [ ] **Step 3: Implement bounded two-pass synthesis**

```python
class DirectorTurnInput(DomainModel):
    workspace_summary: Mapping[str, object]
    tournament_revision: int
    user_message: str
    pending_actions: tuple[str, ...] = ()
    mode: AgentMode
    specialist_evidence: tuple[Mapping[str, object], ...] = ()

requested = validate_requested_roles(first_output.specialist_requests, workspace)
specialist_records = await self._specialists.run_many(requested, workspace=workspace)
final_output = await invoke_director(route, workspace, user_message, specialist_records)
```

- [ ] **Step 4: Write and satisfy complete audit assertions**

```python
event = audit_items[0]
assert event["agent_provenance"]["role"] == "tournament_director"
assert event["agent_provenance"]["provider"] == "openai"
assert event["agent_provenance"]["model"] == "gpt-5.6"
assert event["structured_payload"]["specialists"][0]["role"] == "weather_intelligence"
assert event["structured_payload"]["specialists"][0]["tool_outcomes"][0]["status"] == "validated"
assert event["structured_payload"]["specialists"][0]["validation_status"] == "valid"
```

- [ ] **Step 5: Run agent/API suites and commit**

Run: `uv run pytest apps/api/tests/agents apps/api/tests/api/test_director_contract.py -q`

Commit: `feat: ground Director answers in specialist evidence`

---

### Task 3: Attach meaningful specialist work to generation and recovery

**Requirements:** AGENT-003–AGENT-006, AGENT-009, RECOVERY-003–RECOVERY-008, AC-013, AC-019

**Files:**
- Create: `apps/api/app/agents/workflow_orchestrator.py`
- Modify: `apps/api/app/api/schedules.py`
- Modify: `apps/api/app/main.py`
- Create: `apps/api/tests/api/test_specialist_workflow_contract.py`

**Interfaces:**
- Consumes: `SpecialistRuntime`, validated generation batch, validated repair diff.
- Produces: `WorkflowAgentEvidence` attached to run/repair state and organizer audit events.

- [ ] **Step 1: Write failing workflow-sequence tests**

```python
def test_generation_records_strategy_weather_then_fairness(client):
    run = generate_confirmed_sample(client)
    assert [item["role"] for item in run["specialist_evidence"]] == [
        "scheduling_strategy", "weather_intelligence", "fairness_logistics"
    ]

def test_rain_repair_records_weather_recovery_and_fairness(client):
    repair = create_valid_rain_repair(client)
    assert [item["role"] for item in repair["specialist_evidence"]] == [
        "weather_intelligence", "disruption_recovery", "fairness_logistics"
    ]
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest apps/api/tests/api/test_specialist_workflow_contract.py -q`

Expected: response/state lacks `specialist_evidence`.

- [ ] **Step 3: Implement deterministic-first orchestration**

```python
async def after_generation(self, workspace: GuestWorkspace, run: dict[str, object]) -> tuple[SpecialistExecutionRecord, ...]:
    prepared = await asyncio.gather(
        self._runtime.run(role=AgentRole.SCHEDULING_STRATEGY, workspace=workspace, invocation_reason="Map confirmed priorities"),
        self._runtime.run(role=AgentRole.WEATHER_INTELLIGENCE, workspace=workspace, invocation_reason="Explain validated risk and coverage"),
    )
    fairness = await self._runtime.run(role=AgentRole.FAIRNESS_LOGISTICS, workspace=workspace, invocation_reason="Audit validated alternatives")
    return (*prepared, fairness)
```

Convert affected route handlers to `async def`; never remove or delay persistence of valid deterministic results when agent work is unavailable.

- [ ] **Step 4: Test provider outage continuity and no ceremonial calls**

```python
def test_agent_outage_keeps_valid_generation_available(client):
    response = generate_with_unavailable_provider(client)
    assert response.status_code == 202
    assert all(item["validation_valid"] for item in comparison(client, response)["options"])
    assert response.json()["agent_status"] == "unavailable"
```

- [ ] **Step 5: Run API/agent/recovery suites and commit**

Run: `uv run pytest apps/api/tests/agents apps/api/tests/api apps/api/tests/scheduling/test_repair.py -q`

Commit: `feat: orchestrate specialists across hero workflows`

---

### Task 4: Make weather state revision-safe and synchronized

**Requirements:** FR-035, WEATHER-008, WEATHER-012–WEATHER-013, UX-004, UX-007, UX-011, AC-025

**Files:**
- Create: `apps/api/app/weather/state.py`
- Modify: `apps/api/app/api/routes.py`
- Modify: `apps/api/app/api/schedules.py`
- Modify: `apps/web/app/workspace/options/page.tsx`
- Create: `apps/web/components/weather-workspace-live.tsx`
- Modify: `apps/web/components/weather-mode-controls.tsx`
- Modify: `apps/web/components/weather-risk-panel-live.tsx`
- Create: `apps/api/tests/api/test_weather_revision_contract.py`
- Create: `apps/web/components/weather-workspace-live.test.tsx`

**Interfaces:**
- Produces: `weather_slot_digest(tournament)`, `invalidate_weather(weather, tournament)`, and `WeatherWorkspaceLive`.

- [ ] **Step 1: Write failing backend invalidation tests**

```python
def test_slot_affecting_setup_change_invalidates_weather(client):
    workspace = load_sample_and_refresh_weather(client)
    saved = change_preset_and_save(client, workspace, "T10")
    weather = client.get("/api/v1/weather").json()
    assert weather["quality"] == "refresh_required"
    assert weather["coverage"] == 0
    assert weather["slot_risks"] == {}
    assert weather["tournament_revision"] == saved["revision"]
```

- [ ] **Step 2: Verify RED, then implement revision/digest validation**

```python
def invalidate_weather(previous: Mapping[str, object], tournament: TournamentConfig) -> dict[str, object]:
    return {
        "mode": previous.get("mode", "deterministic"),
        "quality": "refresh_required",
        "coverage": 0.0,
        "slot_risks": {},
        "slot_details": {},
        "tournament_revision": tournament.revision,
        "slot_digest": weather_slot_digest(tournament),
        "invalidation_reason": "Tournament dates, format, venues, or available slots changed. Refresh weather before relying on risk guidance.",
    }
```

Run: `uv run pytest apps/api/tests/api/test_weather_revision_contract.py -q`

- [ ] **Step 3: Write failing frontend synchronization test**

```tsx
it("loads server mode and refreshes the risk panel after a mode change", async () => {
  const view = renderWeatherWorkspace({initialMode: "live"});
  expect(view).toContain("Live forecast mode");
  await switchToDeterministic();
  expect(fetchScheduleWeather).toHaveBeenCalledTimes(2);
  expect(screen.getByRole("status")).toHaveTextContent("Regenerate schedules to update comparison metrics");
});
```

- [ ] **Step 4: Implement one client coordinator**

```tsx
export function WeatherWorkspaceLive({runId}: {runId?: string}) {
  const [status, setStatus] = useState<WeatherStatus | null>(null);
  const [refreshVersion, setRefreshVersion] = useState(0);
  return <>
    <WeatherRiskPanelLive runId={runId} refreshVersion={refreshVersion} />
    <WeatherModeControls initialStatus={status} onModeChanged={(next) => {setStatus(next); setRefreshVersion(v => v + 1);}} />
  </>;
}
```

- [ ] **Step 5: Run weather/API/frontend suites and commit**

Run: `uv run pytest apps/api/tests/weather apps/api/tests/api/test_weather_revision_contract.py -q`

Run: `pnpm --filter @crickops/web test -- weather`

Commit: `fix: synchronize revision-bound weather evidence`

---

### Task 5: Complete failure, accessibility, metric, and repair presentation

**Requirements:** FR-018, UX-005, UX-011, ACCESS-002

**Files:**
- Create: `apps/web/app/not-found.tsx`
- Create: `apps/web/lib/metric-display.ts`
- Create: `apps/web/lib/metric-display.test.ts`
- Modify: `apps/web/components/schedule-diff-rail.tsx`
- Modify: `apps/web/components/profile-comparison.tsx`
- Modify: `apps/web/components/sample-chooser.tsx`
- Modify: `apps/web/components/sample-chooser.test.tsx` or `workspace-shell.test.tsx`
- Modify: `apps/web/components/schedule-diff-rail.test.tsx`

- [ ] **Step 1: Write failing presentation tests**

```tsx
expect(renderNotFound()).toContain("Return to CrickOps home");
expect(sampleMarkup).toContain('aria-label="Load Pakistan Community Cricket Cup sample"');
expect(diffMarkup).toContain("Weather risk worsened by 37.4 points");
expect(diffMarkup).toContain("Slot balance worsened by 6.2 points");
expect(metricLabel("missing_coverage_penalty")).toBe("Missing coverage penalty");
```

- [ ] **Step 2: Verify RED**

Run: `pnpm --filter @crickops/web test -- schedule-diff-rail workspace-shell metric-display`

- [ ] **Step 3: Implement shared metric metadata and trade-off sentences**

```ts
export const metricDisplay = {
  weather_risk: {label: "Weather risk", better: "lower"},
  weather_coverage: {label: "Weather coverage", better: "higher"},
  missing_coverage_penalty: {label: "Missing coverage penalty", better: "lower"},
  group_rest_fairness: {label: "Rest fairness", better: "higher"},
  potential_knockout_rest: {label: "Potential knockout rest", better: "higher"},
  venue_balance: {label: "Venue balance", better: "higher"},
  slot_balance: {label: "Slot balance", better: "higher"},
  preference_satisfaction: {label: "Preference satisfaction", better: "higher"},
  change_cost: {label: "Change cost", better: "lower"},
} as const;
```

- [ ] **Step 4: Add branded not-found actions and distinct sample labels**

```tsx
<Link href="/">Return to CrickOps home</Link>
<Link href="/workspace/setup">Open tournament setup</Link>
<button aria-label={`Load ${sample.name} sample`}>Load sample</button>
```

- [ ] **Step 5: Run full frontend suite/build and commit**

Run: `pnpm lint && pnpm test && pnpm --filter @crickops/web build`

Commit: `fix: complete judge-facing recovery states`

---

### Task 6: Add safe historical schedule browsing

**Requirements:** FR-015, UX-009, TASK-040 expected version selector

**Files:**
- Modify: `apps/api/app/api/schedules.py`
- Modify: `apps/api/tests/api/test_official_schedule_view.py`
- Modify: `apps/web/lib/api-client.ts`
- Modify: `apps/web/components/official-schedule-live.tsx`
- Modify: `apps/web/components/schedule-rail.tsx`
- Create: `apps/web/components/schedule-version-browser.tsx`
- Modify: `apps/web/components/official-schedule-live.test.tsx`

- [ ] **Step 1: Write failing API history tests**

```python
def test_owner_can_read_superseded_version_without_restoring_it(client):
    first, current = approve_two_versions(client)
    response = client.get(f"/api/v1/schedule-versions/{first['version_id']}")
    assert response.status_code == 200
    assert response.json()["version_number"] == 1
    assert response.json()["current_official"] is False
    assert client.get("/api/v1/official-schedule").json()["official"]["version_number"] == current["version_number"]
```

- [ ] **Step 2: Verify RED, then extract one fixture-view builder**

```python
def schedule_version_view(workspace: GuestWorkspace, version: Mapping[str, object]) -> dict[str, object]:
    option = require_valid_approved_draft(workspace, str(version["approved_draft_id"]))
    return {**version, "current_official": version is workspace.official_versions[-1], "validation_valid": True, "fixtures": fixture_views(workspace.tournament, option)}
```

Run: `uv run pytest apps/api/tests/api/test_official_schedule_view.py -q`

- [ ] **Step 3: Write failing browser-component test**

```tsx
expect(markup).toContain("Browse official history");
expect(markup).toContain("Version 1 · superseded");
expect(markup).toContain("Version 2 · current official");
```

- [ ] **Step 4: Implement selection without restoration**

```tsx
<ScheduleVersionBrowser versions={versions} selectedId={schedule.version_id} onSelect={loadVersion} />
<ScheduleRail status={schedule.current_official ? "official" : "historical"} version={schedule.version_number} fixtures={fixtures} />
```

- [ ] **Step 5: Run focused/full suites and commit**

Run: `uv run pytest apps/api/tests/api/test_official_schedule_view.py -q`

Run: `pnpm lint && pnpm test && pnpm --filter @crickops/web build`

Commit: `feat: browse official schedule history safely`

---

### Task 7: Consolidated quality gate, deploy, and production acceptance

**Requirements:** AC-013, AC-019, NFR-008, METRIC-008–METRIC-012, DEPLOY-001–DEPLOY-008

**Files:**
- Create: `docs/evidence/production-audit-remediation.md`
- Modify: `checklist.md` only with fresh evidence references; preserve task IDs.

- [ ] **Step 1: Run consolidated local gates**

Run:

```powershell
pnpm.cmd install --frozen-lockfile
pnpm.cmd lint
pnpm.cmd test
pnpm.cmd --filter @crickops/web build
uv sync --frozen
uv run ruff check .
uv run pytest
```

Expected: every command exits 0; the PostgreSQL-only test may remain explicitly skipped when no integration URL is supplied.

- [ ] **Step 2: Push main and wait for healthy Vercel/Railway deployments**

Confirm deployed commit identity, Vercel page availability, Railway readiness, and GPT-5.6 mode.

- [ ] **Step 3: Run deployed browser acceptance**

Verify on `https://crickops.vercel.app`:

1. Load Pakistan sample and generate three validated options.
2. Ask which option has lowest weather risk; response cites actual metrics and specialist provenance.
3. Switch weather mode, observe synchronized attribution/risk, reload, and retain server mode.
4. Change T20 to T10 and observe refresh-required weather state with zero current coverage.
5. Approve, repair, and verify prose names actual worsened metrics.
6. Browse a superseded version without changing the current official version.
7. Open a nonexistent URL and recover through branded actions.
8. Verify sample actions have unique accessible names.

- [ ] **Step 4: Record evidence, update checklist, and commit**

Commit: `docs: record production audit remediation evidence`
