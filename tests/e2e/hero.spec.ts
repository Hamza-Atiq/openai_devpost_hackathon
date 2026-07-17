import { expect, test } from "@playwright/test";

test("judge can review the complete hero journey within three minutes", async ({ page }) => {
  test.setTimeout(180_000);
  const startedAt = Date.now();

  await page.goto("/");
  await expect(page.getByText("CrickOps AI", { exact: true }).first()).toBeVisible();
  await page.getByRole("button", { name: "Load sample" }).first().click();
  await expect(page.getByRole("heading", { name: /confirm the playing field/i })).toBeVisible();

  await page.goto("/workspace/options");
  await expect(page.getByText("Balanced", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Weather-first", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Fairness-first", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Independent validation passed").first()).toBeVisible();

  await page.goto("/workspace/schedule");
  await expect(page.getByText(/official workspace schedule/i).first()).toBeVisible();
  await expect(page.getByText(/independently validated/i).first()).toBeVisible();

  await page.goto("/workspace/recovery");
  await expect(page.getByRole("heading", { name: /declare an operational disruption/i })).toBeVisible();
  await expect(page.getByText(/minimum-change workflow/i)).toBeVisible();

  await page.goto("/workspace/recovery/diff");
  await expect(page.getByRole("heading", { name: /what changed—and what did not/i })).toBeVisible();
  await expect(page.getByText(/one fixture moved; the rest stay anchored/i)).toBeVisible();
  await expect(page.getByRole("button", { name: /approve repaired schedule/i })).toBeVisible();

  await page.goto("/workspace/activity");
  await expect(page.getByText(/organizer audit timeline/i)).toBeVisible();

  expect(Date.now() - startedAt).toBeLessThan(180_000);
});
