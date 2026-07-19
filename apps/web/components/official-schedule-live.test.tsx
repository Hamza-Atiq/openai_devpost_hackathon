import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { OfficialScheduleLive } from "./official-schedule-live";

describe("official schedule live view", () => {
  it("shows an honest empty state before approval", () => {
    const markup = renderToStaticMarkup(<OfficialScheduleLive initialSchedule={null} />);

    expect(markup).toContain("No official schedule yet");
    expect(markup).not.toContain("Version 2");
  });

  it("renders only the backend fixture and version supplied", () => {
    const markup = renderToStaticMarkup(
      <OfficialScheduleLive
        initialSchedule={{
          version_id: "version-1",
          version_number: 1,
          approved_draft_id: "draft-1",
          approved_at: "2026-09-01T10:00:00Z",
          validation_valid: true,
          fixtures: [{
            id: "match-1",
            code: "G01",
            stage: "group",
            home: "Canal Kings",
            away: "Garden XI",
            venue: "Canal Community Ground",
            starts_at: "2026-09-01T10:00:00+05:00",
            ends_at: "2026-09-01T14:00:00+05:00",
            timezone: "Asia/Karachi",
            validation: "valid",
          }],
        }}
      />,
    );

    expect(markup).toContain("Official workspace schedule");
    expect(markup).toContain("Version 1");
    expect(markup).toContain("Canal Kings");
    expect(markup).not.toContain("Falcons");
  });
});
