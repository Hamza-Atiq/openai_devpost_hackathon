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
}

