import { expect, test } from "@playwright/test";

test("event filters expose accessible state and recovery actions", async ({
  page,
}) => {
  await page.goto("/events");

  const search = page.getByLabel("Search events");
  const summary = page.locator("#event-filter-summary");

  await expect(search).toHaveAttribute(
    "aria-describedby",
    "event-filter-summary"
  );
  await expect(summary).toHaveAttribute("aria-live", "polite");
  await expect(summary).toHaveText("1 event loaded");

  await page.getByRole("button", { name: "Social" }).click();
  await expect(page.getByRole("button", { name: "Social" })).toHaveAttribute(
    "aria-pressed",
    "true"
  );
  await expect(summary).toHaveText("1 matching event");
  await expect(page.getByRole("button", { name: "Clear" })).toBeVisible();

  await search.fill("does-not-match");
  await expect(summary).toHaveText("0 matching events");
  await expect(page.getByText("No matches.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Clear filters" })).toBeVisible();

  await page.getByRole("button", { name: "Clear filters" }).click();
  await expect(summary).toHaveText("1 event loaded");
});

test("calendar shows loading state while month events refresh", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto("/events");

  const calendarRail = page.locator(
    'aside[aria-label="Calendar and time filter"]'
  );
  await expect(calendarRail.getByRole("heading")).toBeVisible();

  let releaseCalendarResponse!: () => void;
  const calendarResponse = new Promise<void>((resolve) => {
    releaseCalendarResponse = resolve;
  });

  await page.route("**/api/events/calendar**", async (route) => {
    await calendarResponse;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ events: [] }),
    });
  });

  await calendarRail.getByRole("button", { name: "Next month" }).click();
  await expect(calendarRail.getByRole("status")).toHaveText("Loading");

  releaseCalendarResponse();
  await expect(calendarRail.getByRole("status")).toHaveCount(0);
});
