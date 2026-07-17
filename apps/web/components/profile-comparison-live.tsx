"use client";

import { CrickOpsApiClient, type CustomPriorities } from "@/lib/api-client";

import { ProfileComparison, type ComparisonOption } from "./profile-comparison";

const labels = {
  balanced: "Balanced",
  "weather-first": "Weather-first",
  "fairness-first": "Fairness-first",
  custom: "Custom schedule",
} as const;

export function ProfileComparisonLive() {
  async function generate(priorities?: Record<string, number>) {
    const response = await new CrickOpsApiClient().generateScheduleOptions(
      priorities as CustomPriorities | undefined,
    );
    const options: ComparisonOption[] = response.options.map((option) => ({
      profile: option.profile,
      label: labels[option.profile],
      validationValid: option.validation_valid,
      metrics: {
        weatherRisk: option.metrics.weather_risk,
        weatherCoverage: option.metrics.weather_coverage,
        groupRestFairness: option.metrics.group_rest_fairness,
        venueBalance: option.metrics.venue_balance,
        slotBalance: option.metrics.slot_balance,
        preferenceSatisfaction: option.metrics.preference_satisfaction,
      },
      softViolations: option.metrics.soft_violations,
    }));
    const identicalProfiles = response.identical_solution_groups.flatMap((group) =>
      group.map((profile) => labels[profile as keyof typeof labels]),
    );
    return { options, identicalProfiles };
  }

  return <ProfileComparison onGenerate={generate} />;
}
