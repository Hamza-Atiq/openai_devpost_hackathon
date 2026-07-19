export const metricDisplay = {
  weather_risk: { label: "Weather risk", better: "lower" },
  weather_coverage: { label: "Weather coverage", better: "higher" },
  missing_coverage_penalty: { label: "Missing coverage penalty", better: "lower" },
  group_rest_fairness: { label: "Rest fairness", better: "higher" },
  potential_knockout_rest: { label: "Potential knockout rest", better: "higher" },
  venue_balance: { label: "Venue balance", better: "higher" },
  slot_balance: { label: "Slot balance", better: "higher" },
  preference_satisfaction: { label: "Preference satisfaction", better: "higher" },
  change_cost: { label: "Change cost", better: "lower" },
} as const;

export function metricLabel(key: string): string {
  return key in metricDisplay
    ? metricDisplay[key as keyof typeof metricDisplay].label
    : key.replaceAll("_", " ").replace(/^./, (letter) => letter.toUpperCase());
}

export function metricDeltaSentence(key: string, delta: number): string {
  const config = metricDisplay[key as keyof typeof metricDisplay];
  const label = metricLabel(key);
  if (delta === 0) return `${label} is unchanged.`;
  const improved = config?.better === "lower" ? delta < 0 : delta > 0;
  return `${label} ${improved ? "improved" : "worsened"} by ${Math.abs(delta).toFixed(1)} points.`;
}
