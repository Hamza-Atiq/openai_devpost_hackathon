"use client";

import { useEffect, useState } from "react";
import { CrickOpsApiClient, type CustomPriorities } from "@/lib/api-client";

import { ProfileComparison, type ComparisonOption } from "./profile-comparison";

const labels = {
  balanced: "Balanced",
  "weather-first": "Weather-first",
  "fairness-first": "Fairness-first",
  custom: "Custom schedule",
} as const;

type LoadedComparison = Awaited<ReturnType<CrickOpsApiClient["getScheduleComparison"]>>;

export function ProfileComparisonLive({ initialRunId }: { initialRunId?: string }) {
  const [loaded, setLoaded] = useState<LoadedComparison | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(Boolean(initialRunId));

  useEffect(() => {
    if (!initialRunId) return;
    let active = true;
    new CrickOpsApiClient().getScheduleComparison(initialRunId).then(
      (response) => { if (active) { setLoaded(response); setLoading(false); } },
      (error: unknown) => { if (active) { setLoadError(error instanceof Error ? error.message : "The generated options could not be loaded."); setLoading(false); } },
    );
    return () => { active = false; };
  }, [initialRunId]);

  function mapComparison(response: LoadedComparison) {
    const options: ComparisonOption[] = response.options.map((option) => ({
      draftId: option.draft_id,
      profile: option.profile,
      label: labels[option.profile],
      validationValid: option.validation_valid,
      metrics: {
        weatherRisk: option.metrics.weather_risk,
        weatherCoverage: option.metrics.weather_coverage,
        groupRestFairness: option.metrics.group_rest_fairness,
        potentialKnockoutRest: option.metrics.potential_knockout_rest,
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

  async function generate(priorities?: Record<string, number>) {
    const response = await new CrickOpsApiClient().generateScheduleOptions(
      priorities as CustomPriorities | undefined,
    );
    return mapComparison(response);
  }

  async function approve(draftId: string) {
    const version = await new CrickOpsApiClient().approveSchedule(draftId);
    return { versionNumber: version.version_number, approvedAt: version.approved_at };
  }

  if (loading) return <div className="operation-status" role="status">Loading validated schedule options…</div>;
  if (loadError) return <div className="operation-status operation-status-error" role="alert"><strong>Options could not be loaded</strong><p>{loadError}</p></div>;
  if (!loaded && initialRunId) return null;
  if (!loaded) return <div className="operation-status"><strong>No generated options yet</strong><p>Complete Setup and choose Confirm and generate schedules.</p></div>;

  const comparison = mapComparison(loaded);
  return <ProfileComparison options={comparison.options} identicalProfiles={comparison.identicalProfiles} onGenerate={generate} onApprove={approve} />;
}
