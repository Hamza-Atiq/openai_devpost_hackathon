import type { TournamentSetupSaveInput, TournamentSetupView } from "./setup-contract";

export type ProblemDetails = {
  type: string;
  title: string;
  status: number;
  code: string;
  detail: string;
  correlation_id: string;
  retryable: boolean;
  evidence?: Array<Record<string, unknown>> | null;
  remedies?: Array<{ code?: string; description?: string } & Record<string, unknown>> | null;
};

export type WorkspaceView = {
  workspace_id: string;
  tournament: { name: string; revision?: number } | null;
  weather?: WeatherStatus;
};

export type WeatherStatus = {
  mode: "live" | "deterministic";
  quality: string;
  scenario_id?: string | null;
  guidance?: string;
};

export type ScheduleWeatherResponse = {
  draft_id: string;
  mode: "live" | "deterministic";
  provider: string | null;
  issued_at: string | null;
  fetched_at: string | null;
  quality: string;
  coverage: number;
  allocation_minutes: number;
  attribution: string | null;
  fixtures: Array<{
    id: string;
    label: string;
    venue: string;
    starts_at: string;
    timezone: string;
    risk: number | null;
    components: Record<string, number | null>;
    quality: string;
  }>;
};

export type ConfirmSetupInput = {
  confirmation: true;
  expected_revision: number;
  selection: {
    match_format_preset: "T10" | "T20";
    allocation_minutes: number;
  };
};

export type SetupPrecheck = { ready: boolean; violations: string[] };

export type CustomPriorities = {
  weather_coverage: number;
  rest: number;
  venue_balance: number;
  slot_balance: number;
  organizer_preferences: number;
  audience_timing: number;
};

export type ScheduleOptionResponse = {
  draft_id: string;
  profile: "balanced" | "weather-first" | "fairness-first" | "custom";
  validation_valid: boolean;
  metrics: {
    weather_risk: number | null;
    weather_coverage: number;
    group_rest_fairness: number;
    potential_knockout_rest: number;
    venue_balance: number;
    slot_balance: number;
    preference_satisfaction: number;
    soft_violations: string[];
  };
};

export type ScheduleComparisonResponse = {
  run_id: string;
  metric_version: string;
  options: ScheduleOptionResponse[];
  identical_solution_groups: string[][];
};

export type OfficialScheduleVersion = {
  version_id: string;
  version_number: number;
  approved_draft_id: string;
  approved_at: string;
};

export type OfficialFixtureResponse = {
  id: string;
  slot_id: string;
  code: string;
  stage: "group" | "semifinal" | "final";
  home: string;
  away: string;
  venue: string;
  starts_at: string;
  ends_at: string;
  timezone: string;
  validation: "valid";
};

export type ScheduleDiffPlacement = {
  slot_id: string;
  venue: string;
  starts_at: string;
  ends_at: string;
  timezone: string;
};

export type ScheduleDiffResponse = {
  baseline_version_id: string;
  draft_id: string;
  unchanged: string[];
  moved: string[];
  added: string[];
  removed: string[];
  metric_deltas: Record<string, number>;
  validation_valid: boolean;
  fixture_views: Array<{
    id: string;
    code: string;
    fixture: string;
    change: "unchanged" | "moved" | "added" | "removed";
    before: ScheduleDiffPlacement | null;
    after: ScheduleDiffPlacement | null;
  }>;
};

export type OfficialScheduleResponse = OfficialScheduleVersion & {
  validation_valid: true;
  fixtures: OfficialFixtureResponse[];
};

export type AuditEventResponse = {
  id: string;
  actor_type: string;
  event_type: string;
  summary: string;
  structured_payload?: Record<string, unknown>;
  occurred_at: string;
};

export type SystemModeResponse = {
  mode: "gpt-5.6" | "fallback-model" | "deterministic";
  label: string;
  provider: string | null;
  model: string | null;
  conversational_available: boolean;
  deterministic_services_available: boolean;
  fabricated_agent_response: false;
  emergency_cached_results: boolean;
};

export type DirectorTurnResponse = {
  message: string | null;
  mode: SystemModeResponse["mode"];
  provider: string | null;
  model: string | null;
  proposed_state_changes: Array<{
    field: string;
    proposed_value: string | number | boolean;
    requires_confirmation: boolean;
  }>;
  specialist_requests: Array<Record<string, unknown>>;
  evidence_refs: Array<Record<string, unknown>>;
  ui_actions: Array<{
    action: string;
    target_id: string | null;
    label: string;
  }>;
  attempt_count: number;
  transitions: string[];
  unavailable_reason: string | null;
  fabricated_agent_response: false;
};

export type FeedbackReason =
  | "weather_preference"
  | "unfair_rest_distribution"
  | "venue_preference"
  | "unsuitable_time_slot"
  | "rivalry_requirement"
  | "travel_concern"
  | "other";

const CSRF_COOKIE = "__Host-crickops_csrf";

function csrfHeaders(): Record<string, string> {
  if (typeof document === "undefined") return {};
  const token = document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(`${CSRF_COOKIE}=`))
    ?.slice(CSRF_COOKIE.length + 1);
  return token ? { "X-CSRF-Token": decodeURIComponent(token) } : {};
}

export class ApiProblemError extends Error {
  readonly code: string;
  readonly status: number;
  readonly correlationId: string;
  readonly retryable: boolean;
  readonly remedies: ProblemDetails["remedies"];

  constructor(problem: ProblemDetails) {
    super(problem.detail);
    this.name = "ApiProblemError";
    this.code = problem.code;
    this.status = problem.status;
    this.correlationId = problem.correlation_id;
    this.retryable = problem.retryable;
    this.remedies = problem.remedies;
  }
}

export class CrickOpsApiClient {
  private readonly fetcher: typeof fetch;

  constructor(fetcher?: typeof fetch) {
    this.fetcher = fetcher ?? globalThis.fetch.bind(globalThis);
  }

  async createWorkspace(sampleId?: string): Promise<WorkspaceView> {
    const response = await this.fetcher("/api/v1/workspaces", {
      method: "POST",
      credentials: "same-origin",
      cache: "no-store",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sample_id: sampleId ?? null }),
    });
    const payload: unknown = await response.json();
    if (!response.ok) {
      throw new ApiProblemError(payload as ProblemDetails);
    }
    return payload as WorkspaceView;
  }

  async getWorkspace(): Promise<WorkspaceView> {
    return this.get<WorkspaceView>("/api/v1/workspace");
  }

  async resetWorkspace(sampleId = "global-community-cup"): Promise<WorkspaceView> {
    return this.request<WorkspaceView>("/api/v1/workspace/reset", { sample_id: sampleId });
  }

  async deleteWorkspace(): Promise<void> {
    await this.request("/api/v1/workspace", { confirmation: true }, {}, "DELETE");
  }

  async confirmSetup(input: ConfirmSetupInput): Promise<SetupPrecheck> {
    const confirmed = await this.request<{ revision: number }>(
      "/api/v1/constraints/confirm",
      input,
    );
    return this.request<SetupPrecheck>("/api/v1/tournament/precheck", {
      expected_revision: confirmed.revision,
    });
  }

  async getTournamentSetup(): Promise<TournamentSetupView> {
    return this.get<TournamentSetupView>("/api/v1/tournament");
  }

  async saveTournamentSetup(
    input: TournamentSetupSaveInput,
  ): Promise<TournamentSetupView> {
    return this.request<TournamentSetupView>(
      "/api/v1/tournament",
      input,
      { "Idempotency-Key": crypto.randomUUID() },
      "PUT",
    );
  }

  async generateScheduleOptions(
    customPriorities?: CustomPriorities,
  ): Promise<ScheduleComparisonResponse> {
    const accepted = await this.createScheduleRun(customPriorities);
    return this.getScheduleComparison(accepted.run_id);
  }

  async createScheduleRun(
    customPriorities?: CustomPriorities,
  ): Promise<{ run_id: string }> {
    const profiles = ["balanced", "weather_first", "fairness_first"];
    if (customPriorities) profiles.push("custom");
    return this.request<{ run_id: string }>(
      "/api/v1/schedule-runs",
      { profiles, custom_priorities: customPriorities ?? null },
      { "Idempotency-Key": crypto.randomUUID() },
    );
  }

  async getScheduleComparison(runId: string): Promise<ScheduleComparisonResponse> {
    return this.get<ScheduleComparisonResponse>(
      `/api/v1/schedule-comparisons?run_id=${encodeURIComponent(runId)}`,
    );
  }

  async approveSchedule(draftId: string): Promise<OfficialScheduleVersion> {
    return this.request<OfficialScheduleVersion>(
      `/api/v1/schedule-drafts/${encodeURIComponent(draftId)}/approve`,
      { confirmation: true },
      { "Idempotency-Key": crypto.randomUUID() },
    );
  }

  async refreshWeather(mode: "live" | "deterministic"): Promise<WeatherStatus> {
    return this.request<WeatherStatus>("/api/v1/weather/refresh", { mode });
  }

  async activateRainDemo(): Promise<WeatherStatus> {
    return this.request<WeatherStatus>(
      "/api/v1/weather/demo-scenarios/rain-threshold-v1/activate",
      { confirmation: true },
    );
  }

  async proposeWeatherThreshold(metric: string, value: number) {
    return this.request<{ status: "proposed"; threshold: { metric: string; value: number } }>(
      "/api/v1/weather/thresholds",
      { metric, value },
    );
  }

  async confirmWeatherThreshold(metric: string, value: number): Promise<number> {
    const workspace = await this.getWorkspace();
    if (workspace.tournament?.revision === undefined) throw new Error("Tournament revision is unavailable.");
    const confirmed = await this.request<{ revision: number }>("/api/v1/constraints/confirm", {
      confirmation: true,
      expected_revision: workspace.tournament.revision,
      selection: { weather_threshold: { metric, value } },
    });
    return confirmed.revision;
  }

  async declareAndRepairDisruption(
    type: "rain" | "venue_unavailability",
    unavailableSlotIds: string[],
  ): Promise<{ disruption_id: string; draft_id: string; status: string }> {
    const disruption = await this.request<{ disruption_id: string }>("/api/v1/disruptions", {
      type,
      unavailable_slot_ids: unavailableSlotIds,
    });
    return this.request(`/api/v1/disruptions/${encodeURIComponent(disruption.disruption_id)}/repair-runs`, {});
  }

  async rejectSchedule(draftId: string): Promise<void> {
    const response = await this.fetcher(
      `/api/v1/schedule-drafts/${encodeURIComponent(draftId)}/reject`,
      {
        method: "POST",
        credentials: "same-origin",
        cache: "no-store",
        headers: csrfHeaders(),
      },
    );
    if (!response.ok) throw new ApiProblemError((await response.json()) as ProblemDetails);
  }

  async restoreScheduleVersion(versionId: string): Promise<OfficialScheduleVersion> {
    return this.request<OfficialScheduleVersion>(
      `/api/v1/schedule-versions/${encodeURIComponent(versionId)}/restore`,
      { confirmation: true },
      { "Idempotency-Key": crypto.randomUUID() },
    );
  }

  async getScheduleVersions(): Promise<OfficialScheduleVersion[]> {
    const response = await this.get<{ items: OfficialScheduleVersion[] }>("/api/v1/schedule-versions");
    return response.items;
  }

  async getOfficialSchedule(): Promise<OfficialScheduleResponse | null> {
    const response = await this.get<{ official: OfficialScheduleResponse | null }>(
      "/api/v1/official-schedule",
    );
    return response.official;
  }

  async getScheduleDiff(draftId: string): Promise<ScheduleDiffResponse> {
    return this.get<ScheduleDiffResponse>(
      `/api/v1/schedule-diffs/${encodeURIComponent(draftId)}`,
    );
  }

  async getScheduleWeather(draftId: string): Promise<ScheduleWeatherResponse> {
    return this.get<ScheduleWeatherResponse>(
      `/api/v1/weather/schedule?draft_id=${encodeURIComponent(draftId)}`,
    );
  }

  async getAuditEvents(): Promise<{ items: AuditEventResponse[]; next_cursor: string | null; has_more: boolean }> {
    return this.get("/api/v1/audit-events");
  }

  async getSystemMode(): Promise<SystemModeResponse> {
    return this.get<SystemModeResponse>("/api/v1/system/mode");
  }

  async sendDirectorTurn(message: string): Promise<DirectorTurnResponse> {
    return this.request<DirectorTurnResponse>("/api/v1/director/turn", { message });
  }

  async recordScheduleFeedback(
    draftId: string,
    reason: FeedbackReason,
    note?: string,
  ): Promise<void> {
    await this.request(`/api/v1/schedule-drafts/${encodeURIComponent(draftId)}/feedback`, {
      reason,
      note: note ?? null,
    });
  }

  private async request<T = unknown>(
    path: string,
    body: object,
    headers: Record<string, string> = {},
    method = "POST",
  ): Promise<T> {
    const response = await this.fetcher(path, {
      method,
      credentials: "same-origin",
      cache: "no-store",
      headers: { "Content-Type": "application/json", ...csrfHeaders(), ...headers },
      body: JSON.stringify(body),
    });
    const payload: unknown = await response.json();
    if (!response.ok) throw new ApiProblemError(payload as ProblemDetails);
    return payload as T;
  }

  private async get<T>(path: string): Promise<T> {
    const response = await this.fetcher(path, {
      method: "GET",
      credentials: "same-origin",
      cache: "no-store",
    });
    const payload: unknown = await response.json();
    if (!response.ok) throw new ApiProblemError(payload as ProblemDetails);
    return payload as T;
  }
}
