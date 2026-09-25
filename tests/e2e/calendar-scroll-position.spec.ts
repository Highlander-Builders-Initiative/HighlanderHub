import { expect, test, type Page } from "@playwright/test";
import { E2E_FIXTURE_EVENT } from "../../src/lib/events/fixtures";

function eventsOn(day: string, count: number, prefix: string) {
  return Array.from({ length: count }, (_, index) => ({
    ...E2E_FIXTURE_EVENT,
    id: `${prefix}-${index}`,
    title: `${prefix} ${index}`,
    startsAt: `${day}T${String(10 + Math.floor(index / 6)).padStart(2, "0")}:${String((index % 6) * 10).padStart(2, "0")}:00-07:00`,
    endsAt: undefined,
  }));
}

const initial = [
  ...eventsOn("2026-05-20", 20, "first"),
  ...eventsOn("2026-05-21", 4, "boundary"),
];
const missing = eventsOn("2026-05-21", 24, "missing").slice(4);
const target = eventsOn("2026-05-22", 12, "target");
const calendarEvents = [...initial, ...missing, ...target];

async function openFeed(page: Page, mobile: boolean, view: "cards" | "compact") {
  await page.setViewportSize(mobile ? { width: 390, height: 844 } : { width: 1280, height: 720 });
  // Restore a real page boundary: the first 24 rows end partway through May 21.
  await page.addInitScript(({ initial }) => {
    sessionStorage.setItem("highlanderhub.eventFeed", JSON.stringify({
      path: "/events", scrollY: 0, events: initial, hasMore: true,
      nextOffset: 24, category: "all", query: "", dayWindow: "all",
      loadedCount: 24, eventId: initial[0].id, eventTop: 300, savedAt: Date.now(),
    }));
    sessionStorage.setItem("highlanderhub.returnScroll", JSON.stringify({
      path: "/events", scrollY: 0, detailPath: "/events/first-0",
      eventId: initial[0].id, eventTop: 300, loadedCount: 24,
    }));
  }, { initial });
  await page.route("**/api/events/calendar**", (route) =>
    route.fulfill({ json: { events: calendarEvents } })
  );
  await page.route(/\/api\/events\?/, (route) =>
    route.fulfill({ json: { events: [...missing, ...target], hasMore: false, nextOffset: 56 } })
  );
  await page.goto("/events");
  await expect(page.locator("[data-event-id]")).toHaveCount(24);
  await expect.poll(() => page.evaluate(() => sessionStorage.getItem("highlanderhub.returnScroll"))).toBeNull();
  await page.getByRole("button", { name: view === "cards" ? "Cards" : "Compact", exact: true }).click();
}

async function selectTarget(page: Page, mobile: boolean) {
  if (mobile) await page.getByRole("button", { name: "Filter", exact: true }).click();
  const calendar = mobile
    ? page.getByRole("dialog", { name: "Filter events" })
    : page.getByRole("complementary", { name: "Calendar and time filter" });
  await calendar.getByRole("button", { name: "Jump to 2026-05-22, 12 events", exact: true }).click();
}

async function expectSettledTarget(page: Page) {
  // Do not pass just because the heading crosses the right position mid-scroll.
  await page.waitForTimeout(1800);
  const top = () => page.locator('[data-day-key="2026-05-22"]').evaluate((el) => el.getBoundingClientRect().top);
  await expect.poll(async () => Math.abs(await top() - 96)).toBeLessThan(2);
  const first = await page.locator('[data-event-id="target-0"]').boundingBox();
  expect(first!.y).toBeGreaterThan(96);
  expect(first!.y).toBeLessThan(200);
  await page.waitForTimeout(300);
  expect(Math.abs(await top() - 96)).toBeLessThan(2);
}

for (const mobile of [false, true]) {
  for (const view of ["cards", "compact"] as const) {
    test(`unpaginated calendar jump settles at the first event: ${mobile ? "mobile" : "desktop"} ${view}`, async ({ page }) => {
      await openFeed(page, mobile, view);
      await selectTarget(page, mobile);
      await expectSettledTarget(page);
    });
  }
}

test("mobile selecting the current day returns to its first event", async ({ page }) => {
  await openFeed(page, true, "cards");
  await selectTarget(page, true);
  await page.waitForTimeout(1800);
  await page.locator('[data-event-id="target-8"]').evaluate((el) => el.scrollIntoView({ behavior: "instant" }));
  await expect.poll(() => page.locator('[data-event-id="target-0"]').evaluate((el) => el.getBoundingClientRect().top)).toBeLessThan(-500);
  await selectTarget(page, true);
  await expectSettledTarget(page);
});

test("calendar jump completes the partially loaded boundary day", async ({ page }) => {
  await openFeed(page, false, "cards");
  await selectTarget(page, false);
  await expect(page.locator('[data-event-id^="missing-"]')).toHaveCount(20);
  await expect(page.locator("[data-event-id]")).toHaveCount(56);
  const saved = await page.evaluate(() => JSON.parse(sessionStorage.getItem("highlanderhub.eventFeed")!));
  // Calendar merges are not sequential API pages; the pagination cursor stays put.
  expect(saved.nextOffset).toBe(24);
});

test("manual scrolling cancels the calendar landing correction", async ({ page }) => {
  await openFeed(page, false, "cards");
  await selectTarget(page, false);
  await page.waitForFunction(() => window.scrollY > 500);
  await page.mouse.move(600, 400);
  await page.mouse.wheel(0, -500);
  await page.waitForTimeout(1800);
  const first = await page.locator('[data-event-id="target-0"]').boundingBox();
  expect(first!.y).toBeGreaterThan(500);
});

test("reduced-motion calendar jumps still settle after cards render", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await openFeed(page, true, "cards");
  await selectTarget(page, true);
  await expectSettledTarget(page);
});
