import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { ScheduleApprovalDialog } from "./schedule-approval-dialog";

describe("Schedule approval dialog", () => {
  it("uses explicit internal approval language and never implies external publication", () => {
    const markup = renderToStaticMarkup(<ScheduleApprovalDialog profileLabel="Balanced" onCancel={vi.fn()} onApprove={vi.fn()} />);

    expect(markup).toContain("Approve the Balanced schedule?");
    expect(markup).toContain("timestamped official version");
    expect(markup).toContain("does not publish or distribute fixtures externally");
    expect(markup).toContain("Set as official workspace schedule");
    expect(markup).toContain("disabled");
    expect(markup).not.toContain("Publish externally");
  });
});
