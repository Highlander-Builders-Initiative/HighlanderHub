import { expect, test } from "@playwright/test";
import { E2E_FIXTURE_EVENT } from "../../src/lib/events/fixtures";

function eventsOn(day: string, count: number, prefix: string) {
  return Array.from({ length: count }, (_, index) => {
    const startsAt = `${day}T${String(10 + Math.floor(index / 6)).padStart(2, "0")}:${String((index % 6) * 10).padStart(2, "0")}:00-07:00`;
    return {
      ...E2E_FIXTURE_EVENT,
      id: `${prefix}-${index}`,
      title: `${prefix} ${index}`,
      startsAt,
      sortAt: startsAt,
      endsAt: undefined,
    };
  });
}

const initial = [
  ...eventsOn("2026-05-20", 20, "first"),
  ...eventsOn("2026-05-21", 4, "boundary"),
];
// Between the loaded pages and July's grid (which starts June 28).
const gap = eventsOn("2026-06-10", 6, "gap");
const target = eventsOn("2026-07-15", 12, "target");
const pool = [...initial, ...gap, ...target];

test("a calendar jump past the loaded pages also loads the days before the grid", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.addInitScript(({ initial }) => {
    sessionStorage.setItem("highlanderhub.eventFeed", JSON.stringify({
      path: "/events", scrollY: 0, events: initial, hasMore: true,
      cursor: { sortAt: initial[initial.length - 1].sortAt, id: initial[initial.length - 1].id },
      category: "all", query: "", dayWindow: "all",
      loadedCount: 24, eventId: initial[0].id, eventTop: 300, savedAt: Date.now(),
    }));
    sessionStorage.setItem("highlanderhub.returnScroll", JSON.stringify({
      path: "/events", scrollY: 0, detailPath: "/events/first-0",
      eventId: initial[0].id, eventTop: 300, loadedCount: 24,
    }));
  }, { initial });
  const ranges: string[][] = [];
  await page.route("**/api/events/calendar**", (route) => {
    const url = new URL(route.request().url());
    const start = url.searchParams.get("start")!;
    const end = url.searchParams.get("end")!;
    ranges.push([start, end]);
    const day = (startsAt: string) => startsAt.slice(0, 10);
    route.fulfill({ json: { events: pool.filter((e) => day(e.startsAt) >= start && day(e.startsAt) <= end) } });
  });
  // Pagination cannot fill the gap in this test; only the jump can.
  await page.route(/\/api\/events\?/, (route) => route.fulfill({ status: 500 }));

  await page.goto("/events");
  await expect(page.locator("[data-event-id]")).toHaveCount(24);
  const calendar = page.getByRole("complementary", { name: "Calendar and time filter" });
  await calendar.getByRole("button", { name: "Next month" }).click();
  await calendar.getByRole("button", { name: "Next month" }).click();
  await calendar.getByRole("button", { name: "Jump to 2026-07-15, 12 events", exact: true }).click();

  await expect(page.locator('[data-event-id^="target-"]')).toHaveCount(12);
  await expect(page.locator('[data-event-id^="gap-"]')).toHaveCount(6);
  expect(ranges).toContainEqual(["2026-05-21", "2026-06-27"]);
});
