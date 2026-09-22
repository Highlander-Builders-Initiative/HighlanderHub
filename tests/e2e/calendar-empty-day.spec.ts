import { expect, test } from "@playwright/test";
import { E2E_FIXTURE_EVENT } from "../../src/lib/events/fixtures";

for (const scenario of ["loaded month", "adjacent month", "filtered day"] as const) {
  test(`empty calendar date does not expand the feed: ${scenario}`, async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    const juneEvents = Array.from({ length: 120 }, (_, index) => ({
      ...E2E_FIXTURE_EVENT,
      id: `calendar-load-${index}`,
      title: `Calendar load event ${index}`,
      startsAt: "2026-06-01T18:30:00-07:00",
      endsAt: "2026-06-01T20:00:00-07:00",
    }));
    const calendarEvents = scenario === "filtered day"
      ? [...juneEvents, {
          ...E2E_FIXTURE_EVENT,
          id: "calendar-filtered-out",
          startsAt: "2026-06-02T18:30:00-07:00",
          category: "academic",
        }]
      : juneEvents;
    let juneRequests = 0;
    await page.route("**/api/events/calendar**", async (route) => {
      const url = new URL(route.request().url());
      if (url.searchParams.get("start") !== "2026-05-31") {
        await route.continue();
        return;
      }
      juneRequests += 1;
      await route.fulfill({ json: { events: calendarEvents } });
    });

    await page.goto(scenario === "filtered day" ? "/events?cat=social" : "/events");
    const rail = page.getByRole("complementary", { name: "Calendar and time filter" });
    await expect(rail.getByRole("heading", { level: 2 })).toHaveText(/may 2026/i);
    await expect(rail.locator("[aria-busy]")).toHaveAttribute("aria-busy", "false");
    if (scenario !== "adjacent month") {
      await rail.getByRole("button", { name: "Next month" }).click();
      await expect(rail.getByRole("button", { name: "Jump to 2026-06-01, 120 events" })).toBeVisible();
    }
    const initialCount = scenario === "filtered day" ? 1 : 2;
    await expect(page.locator("[data-event-id]")).toHaveCount(initialCount);
    await rail.getByRole("button", { name: "Jump to 2026-06-02, no events" }).click();
    await expect(rail.getByRole("heading", { level: 2 })).toHaveText(/june 2026/i);
    await expect(rail.locator("[aria-busy]")).toHaveAttribute("aria-busy", "false");
    // Let jump suppression expire so delayed work cannot hide the regression.
    await page.waitForTimeout(1400);
    await expect(page.locator("[data-event-id]")).toHaveCount(initialCount);
    expect(juneRequests).toBe(1);
    expect(errors).toEqual([]);

    // A real target must still merge its events and finish the jump.
    await rail.getByRole("button", { name: "Jump to 2026-06-01, 120 events" }).click();
    await expect(page.locator('[data-day-key="2026-06-01"]')).toBeInViewport();
    await expect(page.locator("[data-event-id]")).toHaveCount(initialCount + 120);
  });
}
