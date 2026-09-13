import { expect, test, type Page } from "@playwright/test";
import { E2E_FIXTURE_EVENT } from "../../src/lib/events/fixtures";
import { waitForEventsBrowserHydration } from "./events-browser-helpers";

const EVENT_NAME = "E2E Test: Highlander Hub Showcase";
const EVENT_URL = "**/events/e2e-highlander-hub-showcase";

async function openOverlay(page: Page) {
  await Promise.all([
    page.waitForURL(EVENT_URL),
    page.getByRole("link", { name: new RegExp(EVENT_NAME, "i") }).click(),
  ]);
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading", { name: EVENT_NAME })).toBeVisible();
  return dialog;
}

test("event cards open an overlay that closes back onto the list", async ({
  page,
}) => {
  await page.goto("/events");
  await waitForEventsBrowserHydration(page);

  const dialog = await openOverlay(page);
  // The list stays mounted underneath, and focus moves into the panel.
  await expect(page.getByLabel(/Search events/i)).toBeAttached();
  await expect(dialog).toBeFocused();

  await Promise.all([page.waitForURL("**/events"), page.keyboard.press("Escape")]);
  await expect(dialog).toHaveCount(0);

  await openOverlay(page);
  // Backdrop: the corner of the viewport is outside the centered panel.
  await Promise.all([page.waitForURL("**/events"), page.mouse.click(8, 8)]);
  await expect(dialog).toHaveCount(0);

  await openOverlay(page);
  await Promise.all([page.waitForURL("**/events"), page.goBack()]);
  await expect(dialog).toHaveCount(0);
});

test("reloading an open overlay keeps the card and closes back to the feed", async ({
  page,
}) => {
  await page.goto("/events");
  await waitForEventsBrowserHydration(page);
  await openOverlay(page);

  await page.reload();

  await expect(
    page.getByRole("dialog").getByRole("heading", { name: EVENT_NAME })
  ).toBeVisible();
  await expect(page.locator('script[type="application/ld+json"]')).toHaveCount(1);
  await page.getByRole("dialog").getByRole("button", { name: "Close event" }).click();
  await expect(page).toHaveURL(/\/events$/);
  await expect(page.getByRole("dialog")).toHaveCount(0);
});


test("a filtered feed does not rewrite the detail URL or reset when closed", async ({ page }) => {
  await page.goto("/events?cat=social&q=Showcase");
  await expect(page.locator('#event-filter-summary')).toHaveText("1 matching event");
  const dialog = await openOverlay(page);
  // Let both filter synchronization and the search debounce settle.
  await page.waitForTimeout(900);
  await expect(page).toHaveURL(/\/events\/e2e-highlander-hub-showcase$/);
  await dialog.getByRole("button", { name: "Close event" }).click();
  await expect(page).toHaveURL(/\/events\?cat=social&q=Showcase$/);
  await expect(page.getByLabel("Search events")).toHaveValue("Showcase");
  await page.goForward();
  await expect(page.getByRole("dialog").getByRole("heading", { name: EVENT_NAME })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("dialog").getByRole("heading", { name: EVENT_NAME })).toBeVisible();
  await page.getByRole("dialog").getByRole("button", { name: "Close event" }).click();
  await expect(page).toHaveURL(/\/events\?cat=social&q=Showcase$/);
});

for (const reload of [false, true]) {
  test(`loaded pages and the next cursor survive closing a card${reload ? " after refresh" : ""}`, async ({ page }) => {
    const events = Array.from({ length: 32 }, (_, i) => ({
      ...E2E_FIXTURE_EVENT,
      id: i === 24 ? E2E_FIXTURE_EVENT.id : `loaded-${i}`,
      title: i === 24 ? E2E_FIXTURE_EVENT.title : `Loaded event ${i}`,
    }));
    await page.addInitScript(({ events }) => {
      if (sessionStorage.getItem("modal-test-seeded")) return;
      sessionStorage.setItem("modal-test-seeded", "1");
      sessionStorage.setItem("highlanderhub.eventFeed", JSON.stringify({
        path: "/events", scrollY: 0, events, hasMore: true, nextOffset: 32,
        category: "all", query: "", dayWindow: "all", loadedCount: 32,
        eventId: events[0].id, eventTop: 100, savedAt: Date.now(),
      }));
      sessionStorage.setItem("highlanderhub.returnScroll", JSON.stringify({
        path: "/events", detailPath: `/events/${events[0].id}`,
        scrollY: 0, eventId: events[0].id, eventTop: 100, loadedCount: 32,
      }));
    }, { events });
    const offsets: string[] = [];
    await page.route(/\/api\/events\?/, async (route) => {
      offsets.push(new URL(route.request().url()).searchParams.get("offset") ?? "");
      await route.fulfill({ json: { events: [], hasMore: false, nextOffset: 32 } });
    });
    await page.goto("/events");
    await expect(page.locator('[data-event-id]')).toHaveCount(32);
    const link = page.locator(`[data-event-id="${E2E_FIXTURE_EVENT.id}"]`);
    await link.scrollIntoViewIfNeeded();
    await openOverlay(page);
    const saved = await page.evaluate(() => JSON.parse(sessionStorage.getItem("highlanderhub.returnScroll")!));
    if (reload) await page.reload();
    const dialog = page.getByRole("dialog");
    await expect(dialog.getByRole("heading", { name: EVENT_NAME })).toBeVisible();
    await dialog.getByRole("button", { name: "Close event" }).click();
    await expect(page).toHaveURL(/\/events$/);
    await expect(page.locator('[data-event-id]')).toHaveCount(32);
    await expect.poll(async () => Math.abs((await link.boundingBox())!.y - saved.eventTop)).toBeLessThanOrEqual(8);
    await page.locator('[data-event-id]').last().scrollIntoViewIfNeeded();
    await expect.poll(() => offsets).toContain("32");
  });
}

test("a fresh event link opens a card with a safe close destination", async ({ page }) => {
  await page.goto("/about");
  await page.goto("/events/e2e-highlander-hub-showcase");
  await expect(page.getByRole("dialog").getByRole("heading", { name: EVENT_NAME })).toBeVisible();
  await page.getByRole("dialog").getByRole("button", { name: "Close event" }).click();
  await expect(page).toHaveURL(/\/events$/);
});


test("mobile cards survive refresh and release scrolling on close", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/events");
  const dialog = await openOverlay(page);
  await page.reload();
  await expect(dialog.getByRole("heading", { name: EVENT_NAME })).toBeVisible();
  await dialog.getByRole("button", { name: "Close event" }).click();
  await expect(page).toHaveURL(/\/events$/);
  await expect(page.locator("body")).not.toHaveCSS("overflow", "hidden");
});

test("unavailable events keep the card's close controls", async ({ page }) => {
  await page.goto("/events/missing-event");
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading", { name: "This event is no longer listed." })).toBeVisible();
  await dialog.getByRole("button", { name: "Close event" }).click();
  await expect(page).toHaveURL(/\/events$/);
});
