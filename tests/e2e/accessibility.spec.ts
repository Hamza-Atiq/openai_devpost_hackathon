import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const heroRoutes = [
  "/",
  "/workspace/setup",
  "/workspace/options",
  "/workspace/schedule",
  "/workspace/recovery",
  "/workspace/recovery/diff",
  "/workspace/activity",
] as const;

for (const route of heroRoutes) {
  test(`${route} has no serious or critical WCAG A/AA violations`, async ({ page }) => {
    await page.goto(route);
    await page.waitForLoadState("networkidle");

    const result = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
      .analyze();
    const materialViolations = result.violations.filter(
      (violation) => violation.impact === "serious" || violation.impact === "critical",
    );

    expect(materialViolations, JSON.stringify(materialViolations, null, 2)).toEqual([]);
  });
}

test("workspace skip navigation and focus indicator work from the keyboard", async ({ page }) => {
  await page.goto("/workspace/setup");

  await page.keyboard.press("Tab");
  const skipLink = page.getByRole("link", { name: "Skip to workspace" });
  await expect(skipLink).toBeFocused();
  await expect(skipLink).toBeVisible();
  await page.keyboard.press("Enter");
  await expect(page.locator("#main-content")).toBeFocused();

  await page.keyboard.press("Tab");
  const focused = page.locator(":focus");
  await expect(focused).toBeVisible();
  const focusStyle = await focused.evaluate((element) => {
    const style = getComputedStyle(element);
    return { width: style.outlineWidth, style: style.outlineStyle };
  });
  expect(focusStyle.style).not.toBe("none");
  expect(focusStyle.width).not.toBe("0px");
});

test("comparison and recovery states use semantic text rather than color alone", async ({ page }) => {
  await page.goto("/workspace/options");
  await expect(
    page.getByRole("heading", { name: "Compare the trade-offs, fixture by fixture." }),
  ).toBeVisible();
  await expect(page.getByText("Independent validation passed").first()).toBeVisible();
  await expect(page.getByText("Weather coverage").first()).toBeVisible();

  await page.goto("/workspace/recovery/diff");
  await expect(page.getByText(/preserved/i).first()).toBeVisible();
  await expect(page.getByText(/changed/i).first()).toBeVisible();
  await expect(page.getByRole("button", { name: /approve repaired schedule/i })).toBeVisible();
});
