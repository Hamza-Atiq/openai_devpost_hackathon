import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

import { DirectorPanel } from "./director-panel";
import { SampleChooser } from "./sample-chooser";
import { WorkspaceShell } from "./workspace-shell";

describe("accessible workspace entry", () => {
  it("renders a skip link, labelled navigation, and Director landmark", () => {
    const markup = renderToStaticMarkup(
      <WorkspaceShell director={<DirectorPanel />}>
        <p>Workspace</p>
      </WorkspaceShell>,
    );

    expect(markup).toContain('href="#main-content"');
    expect(markup).toContain('aria-label="Workspace navigation"');
    expect(markup).toContain('aria-label="Tournament Director"');
    expect(markup).toContain('id="main-content"');
  });

  it("offers both samples, a blank workspace, and the privacy boundary", () => {
    const markup = renderToStaticMarkup(<SampleChooser />);

    expect(markup).toContain("Global Community Cricket Cup");
    expect(markup).toContain("Pakistan Community Cricket Cup");
    expect(markup).toContain("Create a blank tournament");
    expect(markup).toContain("Do not enter personal, confidential, financial, or payment information");
    expect((markup.match(/<button/g) ?? []).length).toBe(3);
  });
});
