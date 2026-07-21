export type CoordinateKind = "latitude" | "longitude";

export function parseCoordinateInput(
  text: string,
  kind: CoordinateKind,
): { value: number } | { error: string } {
  const limit = kind === "latitude" ? 90 : 180;
  const label = kind === "latitude" ? "Latitude" : "Longitude";
  if (!/^[+-]?(?:\d+|\d+\.\d+|\.\d+)$/.test(text.trim())) {
    return { error: `${label} must be a complete decimal from -${limit} to ${limit}.` };
  }
  const value = Number(text);
  if (!Number.isFinite(value) || value < -limit || value > limit) {
    return { error: `${label} must be from -${limit} to ${limit}.` };
  }
  return { value };
}
