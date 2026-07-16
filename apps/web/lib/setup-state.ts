export type MatchFormatPreset = "T10" | "T20";

export type SetupVenue = {
  id: string;
  name: string;
  locationQuery: string;
  latitude: number | null;
  longitude: number | null;
  timezone: string;
  locationConfirmed: boolean;
  blackoutDates: string[];
};

type ManualLocationInput = {
  locationQuery: string;
  latitude: number;
  longitude: number;
  timezone: string;
};

export function allocationMinutes(preset: MatchFormatPreset): number {
  return preset === "T10" ? 120 : 240;
}

export function buildVenueLocation(input: ManualLocationInput) {
  return { ...input, locationConfirmed: true as const };
}

export function validateSharedTimezone(venues: SetupVenue[]) {
  const timezones = new Set(venues.map((venue) => venue.timezone).filter(Boolean));
  if (timezones.size > 1) {
    return {
      valid: false as const,
      message: "Version 1 requires both venues to use the same IANA timezone.",
    };
  }
  return { valid: true as const, message: null };
}
