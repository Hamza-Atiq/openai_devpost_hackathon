import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { SetupSectionNav } from "./setup-section-nav";

describe("setup section navigation", () => {
  it("links every setup stage and identifies one current location", () => {
    const markup = renderToStaticMarkup(<SetupSectionNav />);

    expect(markup).toContain('href="#format-and-teams"');
    expect(markup).toContain('href="#venues-and-location"');
    expect(markup).toContain('href="#dates-and-slots"');
    expect(markup).toContain('href="#constraints"');
    expect((markup.match(/aria-current="location"/g) ?? [])).toHaveLength(1);
  });

  it("uses distinct, descriptive accessible names for every destination", () => {
    const markup = renderToStaticMarkup(<SetupSectionNav />);

    expect(markup).toContain('aria-label="Go to Format and teams"');
    expect(markup).toContain('aria-label="Go to Venues and location"');
    expect(markup).toContain('aria-label="Go to Dates and slots"');
    expect(markup).toContain('aria-label="Go to Constraints"');
  });
});
