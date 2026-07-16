export type ProbeSession = {
  session_id: string;
  csrf_token: string;
  environment: string;
  mutation_count: number;
};

type Fetcher = typeof fetch;

async function probeJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new Error(`Session probe failed (${response.status})`);
  }
  return (await response.json()) as T;
}

export async function loadProbeSession(fetcher: Fetcher = fetch): Promise<ProbeSession> {
  const response = await fetcher("/api/v1/spike/session", {
    cache: "no-store",
    credentials: "same-origin",
  });
  return probeJson<ProbeSession>(response);
}

export async function mutateProbeSession(
  csrfToken: string,
  value: string,
  fetcher: Fetcher = fetch,
): Promise<{ session_id: string; mutation_count: number; accepted_value: string }> {
  const response = await fetcher("/api/v1/spike/session/mutations", {
    method: "POST",
    cache: "no-store",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    body: JSON.stringify({ value }),
  });
  return probeJson(response);
}
