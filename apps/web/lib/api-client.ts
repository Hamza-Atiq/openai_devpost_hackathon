export type ProblemDetails = {
  type: string;
  title: string;
  status: number;
  code: string;
  detail: string;
  correlation_id: string;
  retryable: boolean;
};

export type WorkspaceView = {
  workspace_id: string;
  tournament: { name: string } | null;
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

export class ApiProblemError extends Error {
  readonly code: string;
  readonly status: number;
  readonly correlationId: string;
  readonly retryable: boolean;

  constructor(problem: ProblemDetails) {
    super(problem.detail);
    this.name = "ApiProblemError";
    this.code = problem.code;
    this.status = problem.status;
    this.correlationId = problem.correlation_id;
    this.retryable = problem.retryable;
  }
}

export class CrickOpsApiClient {
  constructor(private readonly fetcher: typeof fetch = fetch) {}

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

  async confirmSetup(input: ConfirmSetupInput): Promise<SetupPrecheck> {
    await this.request("/api/v1/constraints/confirm", input);
    return this.request<SetupPrecheck>("/api/v1/tournament/precheck", {});
  }

  async generateScheduleOptions(
    customPriorities?: CustomPriorities,
  ): Promise<ScheduleComparisonResponse> {
    const profiles = ["balanced", "weather_first", "fairness_first"];
    if (customPriorities) profiles.push("custom");
    const accepted = await this.request<{ run_id: string }>(
      "/api/v1/schedule-runs",
      { profiles, custom_priorities: customPriorities ?? null },
      { "Idempotency-Key": crypto.randomUUID() },
    );
    return this.get<ScheduleComparisonResponse>(
      `/api/v1/schedule-comparisons?run_id=${encodeURIComponent(accepted.run_id)}`,
    );
  }

  private async request<T = unknown>(
    path: string,
    body: object,
    headers: Record<string, string> = {},
  ): Promise<T> {
    const response = await this.fetcher(path, {
      method: "POST",
      credentials: "same-origin",
      cache: "no-store",
      headers: { "Content-Type": "application/json", ...headers },
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
