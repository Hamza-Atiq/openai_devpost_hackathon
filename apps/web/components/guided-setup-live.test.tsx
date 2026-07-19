import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { TournamentSetupView } from "@/lib/setup-contract";

import { GuidedSetup } from "./guided-setup";

const pakistanSetup: TournamentSetupView = {
  id: "tournament-1",
  name: "Pakistan Community Cricket Cup",
  revision: 3,
  status: "awaiting_constraint_confirmation",
  match_format_preset: "T20",
  allocation_minutes: 240,
  start_date: "2026-09-01",
  end_date: "2026-09-10",
  venues: [
    {
      display_name: "Canal Community Ground",
      city: "Lahore",
      country_code: "PK",
      latitude: 31.5204,
      longitude: 74.3587,
      iana_time_zone: "Asia/Karachi",
    },
    {
      display_name: "Garden Sports Ground",
      city: "Lahore",
      country_code: "PK",
      latitude: 31.5,
      longitude: 74.32,
      iana_time_zone: "Asia/Karachi",
    },
  ],
  priorities: {
    minimize_weather_risk: true,
    maximize_fair_rest: true,
    balance_venue_allocation: true,
    prefer_selected_time_slots: true,
    minimize_schedule_changes: true,
  },
  setup_draft: {
    weekday_start_times: ["10:00:00"],
    weekend_start_times: ["10:00:00"],
    blackout_dates: [],
    minimum_rest_minutes: 0,
    save_state: "saved",
  },
};

describe("server-backed guided setup", () => {
  it("renders authoritative Pakistan sample values instead of generic defaults", () => {
    const markup = renderToStaticMarkup(
      <GuidedSetup initialSetup={pakistanSetup} saveState="saved" />,
    );

    expect(markup).toContain('value="Canal Community Ground"');
    expect(markup).toContain('value="Garden Sports Ground"');
    expect(markup).toContain('value="Lahore"');
    expect(markup).toContain('value="Asia/Karachi"');
    expect(markup).toContain('value="2026-09-01"');
    expect(markup).toContain('value="2026-09-10"');
    expect(markup).toContain("All changes saved");
    expect(markup).toContain("Confirm and generate schedules");
    expect(markup).not.toContain('value="Pacific/Auckland"');
  });
});
