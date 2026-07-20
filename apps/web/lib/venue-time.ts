const VENUE_LOCALE = "en-GB";

function venueFormatter(
  timeZone: string,
  options: Intl.DateTimeFormatOptions,
): Intl.DateTimeFormat {
  return new Intl.DateTimeFormat(VENUE_LOCALE, {
    ...options,
    hour12: false,
    timeZone,
  });
}

export function formatVenueDateTime(instant: string, timeZone: string): string {
  return venueFormatter(timeZone, {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(instant));
}

export function formatVenueTime(instant: string, timeZone: string): string {
  return venueFormatter(timeZone, {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(instant));
}

export function formatVenueDate(instant: string, timeZone: string): string {
  return venueFormatter(timeZone, {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(instant));
}
