import { expect, test } from "@playwright/test";
import path from "node:path";
import { E2E_FIXTURE_EVENT } from "../../src/lib/events/fixtures";

// Viewport route prefetching is disabled by Next in development. Run with
// PLAYWRIGHT_PRODUCTION=1 to exercise the actual tap-to-popup loading path.
test.skip(process.env.PLAYWRIGHT_PRODUCTION !== "1", "Requires production prefetching");
test.use({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 3, isMobile: true, hasTouch: true });

for (const view of ["Cards", "Compact"] as const) {
  test(`${view}: mobile popup shows the loaded flyer while the larger image downloads`, async ({ page }) => {
    const event = {
      ...E2E_FIXTURE_EVENT,
      imageUrl: "https://test.cdninstagram.com/mobile-flyer.png",
    };
    await page.addInitScript((event) => {
      sessionStorage.setItem("highlanderhub.eventFeed", JSON.stringify({
        path: "/events", scrollY: 0, events: [event], hasMore: false, nextOffset: 1,
        category: "all", query: "", dayWindow: "all", loadedCount: 1,
        eventId: event.id, eventTop: 100, savedAt: Date.now(),
      }));
      sessionStorage.setItem("highlanderhub.returnScroll", JSON.stringify({
        path: "/events", detailPath: `/events/${event.id}`, scrollY: 0,
        eventId: event.id, eventTop: 100, loadedCount: 1,
      }));
    }, event);

    let releaseImage!: () => void;
    const imageGate = new Promise<void>((resolve) => { releaseImage = resolve; });
    const detailWidths: number[] = [];
    await page.route("**/_next/image?*", async (route) => {
      const width = Number(new URL(route.request().url()).searchParams.get("w"));
      if (width > 256) {
        detailWidths.push(width);
        await imageGate;
      }
      await route.fulfill({ path: path.resolve("public/logo_icon.png"), contentType: "image/png" });
    });

    // Let Next prefetch the popup shell, then hold its fresh server data so
    // the test observes the feed handoff (whose flyer is already loaded).
    const shellReady = page.waitForResponse((response) =>
      new URL(response.url()).pathname === `/events/${event.id}` &&
      response.request().headers()["next-router-prefetch"] === "1" &&
      !response.request().headers()["next-router-segment-prefetch"]
    );
    await page.goto("/events");
    await shellReady;
    const card = page.locator(`[data-event-id="${event.id}"]`);
    await expect(card.locator("img")).toBeVisible();
    if (view === "Compact") await page.getByRole("button", { name: "Compact", exact: true }).click();
    const thumbnail = card.locator("img");
    await expect.poll(() => thumbnail.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBeGreaterThan(0);
    const thumbnailSrc = await thumbnail.evaluate((img: HTMLImageElement) => img.currentSrc);

    let releaseDetail!: () => void;
    const detailGate = new Promise<void>((resolve) => { releaseDetail = resolve; });
    await page.route(`**/events/${event.id}?*`, async (route) => {
      await detailGate;
      await route.continue();
    });

    try {
      await card.tap();
      const dialog = page.getByRole("dialog");
      await expect(dialog.getByRole("heading", { name: event.title })).toBeVisible();
      const flyer = dialog.locator('img:visible').first();
      await expect.poll(() => detailWidths.length).toBeGreaterThan(0);
      // The high-res file is still pending, but its cached thumbnail paints.
      await expect(flyer).toHaveCSS("opacity", "1");
      await expect(flyer).toHaveCSS("background-image", `url("${thumbnailSrc}")`);
      expect(await flyer.evaluate((img: HTMLImageElement) => img.complete)).toBe(false);
      expect(Math.max(...detailWidths)).toBeLessThanOrEqual(828);

      releaseImage();
      await expect.poll(() => flyer.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBeGreaterThan(0);
      await expect(flyer).toHaveCSS("background-image", "none");
      await expect(flyer).toHaveCSS("opacity", "1");
      await dialog.getByRole("button", { name: "Close event" }).click();
      await expect(page).toHaveURL(/\/events$/);
      await expect(dialog).toHaveCount(0);
    } finally {
      releaseImage();
      releaseDetail();
      await page.unrouteAll({ behavior: "ignoreErrors" });
    }
  });
}
