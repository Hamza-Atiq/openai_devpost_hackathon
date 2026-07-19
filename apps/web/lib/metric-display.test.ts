import { describe, expect, it } from "vitest";

import { metricDeltaSentence, metricLabel } from "./metric-display";

describe("metric display", () => {
  it("uses consistent human labels", () => {
    expect(metricLabel("missing_coverage_penalty")).toBe("Missing coverage penalty");
    expect(metricLabel("new_metric_name")).toBe("New metric name");
  });

  it("explains whether repair deltas improve or worsen each metric", () => {
    expect(metricDeltaSentence("weather_risk", 37.4)).toBe(
      "Weather risk worsened by 37.4 points.",
    );
    expect(metricDeltaSentence("slot_balance", -6.2)).toBe(
      "Slot balance worsened by 6.2 points.",
    );
  });
});
