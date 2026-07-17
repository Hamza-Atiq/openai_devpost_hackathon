import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ActivityTimeline } from "./activity-timeline";

describe("Organizer activity timeline", () => {
  it("shows the hero-flow decisions as a human-readable operational record", () => {
    const markup = renderToStaticMarkup(
      <ActivityTimeline
        events={[
          {
            id: "event-2",
            event_type: "schedule_approved",
            actor_type: "organizer",
            summary: "Version 2 approved as the official workspace schedule.",
            occurred_at: "2026-07-16T08:30:00+00:00",
            structured_payload: { version_number: 2 },
          },
          {
            id: "event-1",
            event_type: "repair_generated",
            actor_type: "system",
            summary: "Generated and validated a minimum-change repair draft.",
            occurred_at: "2026-07-16T08:28:00+00:00",
            structured_payload: { moved_count: 1 },
          },
        ]}
        feedbackTarget={{ draftId: "draft-2", label: "Weather-first repair draft" }}
      />,
    );

    expect(markup).toContain("Operational history");
    expect(markup).toContain("Official schedule approved");
    expect(markup).toContain("Repair option generated");
    expect(markup).toContain("Version 2 approved");
    expect(markup).toContain("Optional decision feedback");
    expect(markup).toContain("Unfair rest distribution");
    expect(markup).toContain("Travel concern");
    expect(markup).not.toContain("raw_prompt");
    expect(markup).not.toContain("stack_trace");
    expect(markup).not.toContain("hidden_reasoning");
  });

  it("shows a clear empty state without inventing activity", () => {
    const markup = renderToStaticMarkup(<ActivityTimeline events={[]} />);
    expect(markup).toContain("No material decisions recorded yet");
    expect(markup).not.toContain("Official schedule approved");
  });
});
