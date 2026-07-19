export type MatchFormatPreset = "T10" | "T20";
export type SetupSaveState = "saved" | "dirty" | "saving" | "error";

export type SetupVenueValue = {
  display_name: string;
  city: string;
  country_code: string;
  latitude: number;
  longitude: number;
  iana_time_zone: string;
};

export type SetupPriorities = {
  minimize_weather_risk: boolean;
  maximize_fair_rest: boolean;
  balance_venue_allocation: boolean;
  prefer_selected_time_slots: boolean;
  minimize_schedule_changes: boolean;
};

export type TournamentSetupSaveInput = {
  expected_revision: number;
  match_format_preset: MatchFormatPreset;
  start_date: string;
  end_date: string;
  venues: [SetupVenueValue, SetupVenueValue];
  weekday_start_times: string[];
  weekend_start_times: string[];
  blackout_dates: string[];
  minimum_rest_minutes: number;
  priorities: SetupPriorities;
};

export type TournamentSetupView = {
  id: string;
  name: string;
  revision: number;
  status: string;
  match_format_preset: MatchFormatPreset;
  allocation_minutes: number;
  start_date: string;
  end_date: string;
  venues: [SetupVenueValue, SetupVenueValue];
  priorities: SetupPriorities;
  setup_draft: {
    weekday_start_times: string[];
    weekend_start_times: string[];
    blackout_dates: string[];
    minimum_rest_minutes: number;
    save_state: "saved";
  };
};

export function shortTime(value: string): string {
  return value.slice(0, 5);
}

export function draftFromSetup(setup: TournamentSetupView): TournamentSetupSaveInput {
  return {
    expected_revision: setup.revision,
    match_format_preset: setup.match_format_preset,
    start_date: setup.start_date,
    end_date: setup.end_date,
    venues: setup.venues.map((venue) => ({
      display_name: venue.display_name,
      city: venue.city,
      country_code: venue.country_code,
      latitude: venue.latitude,
      longitude: venue.longitude,
      iana_time_zone: venue.iana_time_zone,
    })) as [
      SetupVenueValue,
      SetupVenueValue,
    ],
    weekday_start_times: setup.setup_draft.weekday_start_times.map(shortTime),
    weekend_start_times: setup.setup_draft.weekend_start_times.map(shortTime),
    blackout_dates: [...setup.setup_draft.blackout_dates],
    minimum_rest_minutes: setup.setup_draft.minimum_rest_minutes,
    priorities: { ...setup.priorities },
  };
}
