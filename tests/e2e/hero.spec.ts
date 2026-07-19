import { expect, test } from "@playwright/test";

test("organizer setup persists and produces the approved backend schedule", async ({ page }) => {
  test.setTimeout(180_000);
  const scheduleRunRequests: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().includes("/api/v1/schedule-runs")) {
      scheduleRunRequests.push(request.url());
    }
  });

  await page.goto("/");
  const pakistanCard = page.getByRole("article").filter({ hasText: "Pakistan Community Cricket Cup" });
  await pakistanCard.getByRole("button", { name: "Load sample" }).click();

  await expect(page.getByRole("heading", { name: /confirm the playing field/i })).toBeVisible({ timeout: 20_000 });
  const firstVenue = page.getByLabel("Venue display name").first();
  await expect(firstVenue).toHaveValue("Canal Community Ground");
  await firstVenue.fill("Canal Community Ground — Judge Test");
  await expect(page.getByText("All changes saved")).toBeVisible({ timeout: 15_000 });

  await page.getByRole("link", { name: "Activity" }).click();
  await page.getByRole("link", { name: "Setup" }).click();
  await expect(firstVenue).toHaveValue("Canal Community Ground — Judge Test");

  await page.getByLabel(/I reviewed the hard constraints/i).check();
  await page.getByRole("button", { name: "Confirm and generate schedules" }).click();
  await expect(page.getByText("Building validated options")).toBeVisible();
  await expect(page).toHaveURL(/\/workspace\/options\?run_id=/, { timeout: 120_000 });
  expect(scheduleRunRequests).toHaveLength(1);

  await expect(page.getByText("Balanced", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Weather-first", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Fairness-first", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Independent validation passed")).toHaveCount(3);

  await page.getByRole("button", { name: "Review Balanced" }).click();
  await page.getByLabel(/I reviewed the validated metrics/i).check();
  await page.getByRole("button", { name: "Set as official workspace schedule" }).click();
  await expect(page.getByText("Official Version 1")).toBeVisible({ timeout: 15_000 });

  await page.getByRole("link", { name: "Schedule" }).click();
  await expect(page.getByText("Official workspace schedule")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("Version 1 · official")).toBeVisible();
  await expect(page.locator(".fixture-card")).toHaveCount(15);
  await expect(page.getByText("Canal Community Ground — Judge Test").first()).toBeVisible();
});
