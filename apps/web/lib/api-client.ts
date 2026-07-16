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

  private async request<T = unknown>(path: string, body: object): Promise<T> {
    const response = await this.fetcher(path, {
      method: "POST",
      credentials: "same-origin",
      cache: "no-store",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const payload: unknown = await response.json();
    if (!response.ok) throw new ApiProblemError(payload as ProblemDetails);
    return payload as T;
  }
}
