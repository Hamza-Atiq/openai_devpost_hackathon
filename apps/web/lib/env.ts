export type PublicEnv = Readonly<{
  apiBaseUrl: string;
  buildSha?: string;
}>;

const PUBLIC_KEYS = new Set([
  "NEXT_PUBLIC_API_BASE_URL",
  "NEXT_PUBLIC_BUILD_SHA",
]);
const BUILD_SHA = /^[0-9a-f]{7,64}$/i;

function validApiBaseUrl(value: string): boolean {
  if (value.startsWith("/") && !value.startsWith("//")) {
    return true;
  }
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:";
  } catch {
    return false;
  }
}

export function parsePublicEnv(
  input: Readonly<Record<string, string | undefined>>,
): PublicEnv {
  for (const name of Object.keys(input)) {
    if (!PUBLIC_KEYS.has(name)) {
      throw new Error(`Unknown public environment variable: ${name}`);
    }
  }

  const apiBaseUrl = input.NEXT_PUBLIC_API_BASE_URL?.trim() || "/api/v1";
  const buildSha = input.NEXT_PUBLIC_BUILD_SHA?.trim() || undefined;
  if (!validApiBaseUrl(apiBaseUrl)) {
    throw new Error("Invalid public environment: API base URL is malformed");
  }
  if (buildSha && !BUILD_SHA.test(buildSha)) {
    throw new Error("Invalid public environment: build SHA is malformed");
  }

  return Object.freeze({
    apiBaseUrl,
    ...(buildSha ? { buildSha } : {}),
  });
}

export function loadPublicEnv(): PublicEnv {
  return parsePublicEnv({
    NEXT_PUBLIC_API_BASE_URL: process.env.NEXT_PUBLIC_API_BASE_URL,
    NEXT_PUBLIC_BUILD_SHA: process.env.NEXT_PUBLIC_BUILD_SHA,
  });
}

export function serializePublicEnv(environment: PublicEnv): string {
  return JSON.stringify(environment);
}
