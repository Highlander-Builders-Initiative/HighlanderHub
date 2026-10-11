import { expect, test, type Locator, type Page } from "@playwright/test";

test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

async function pull(page: Page, target: Locator, distance: number, flick = false) {
  const box = (await target.boundingBox())!;
  const x = box.x + box.width / 2;
  const y = box.y + box.height / 2;
  const session = await page.context().newCDPSession(page);
  const startedAt = Date.now() / 1000;
  await session.send("Input.dispatchTouchEvent", {
    type: "touchStart", touchPoints: [{ x, y }], timestamp: startedAt,
  });
  for (let step = 1; step <= 5; step++) {
    await page.waitForTimeout(flick ? 5 : 60);
    await session.send("Input.dispatchTouchEvent", {
      type: "touchMove", touchPoints: [{ x, y: y + distance * step / 5 }],
      // CDP delivery waits for compositor frames; give a flick its intended
      // input timestamps rather than measuring test-runner round trips.
      timestamp: startedAt + step * (flick ? 0.01 : 0.06),
    });
  }
  // A slow pull rests before release so it tests distance rather than velocity.
  if (!flick) await page.waitForTimeout(120);
  await session.send("Input.dispatchTouchEvent", {
    type: "touchEnd", touchPoints: [], timestamp: startedAt + (flick ? 0.06 : 0.5),
  });
  await session.detach();
}

async function openFilters(page: Page) {
  await page.getByRole("button", { name: /^Filter\b/ }).click();
  const dialog = page.getByRole("dialog", { name: "Filter events" });
  await expect(dialog).toBeVisible();
  const panel = dialog.locator('[tabindex="-1"]').filter({ has: page.getByRole("heading", { name: "Filter events" }) });
  await panel.evaluate(async (element) => {
    await Promise.all(element.getAnimations().map((animation) => animation.finished));
  });
  return { dialog, panel, header: dialog.getByRole("heading", { name: "Filter events" }) };
}

test("mobile filters snap back on short pulls and close on long pulls without clearing selections", async ({ page }) => {
  await page.goto("/events");
  const { dialog, panel, header } = await openFilters(page);
  await dialog.getByRole("button", { name: /^Hang out/ }).click();
  await expect(page).toHaveURL(/cat=hangout/);

  await pull(page, header, 40);
  await expect(dialog).toBeVisible();
  await expect.poll(() => panel.evaluate((element) => element.style.translate)).toBe("");

  await pull(page, header, 200);
  await expect(dialog).toHaveCount(0);
  await expect(page.locator("html")).not.toHaveCSS("overflow", "hidden");
  await expect(page.getByRole("button", { name: /^Filter\b/ })).toBeFocused();

  await openFilters(page);
  await expect(dialog.getByRole("button", { name: /^Hang out/ })).toHaveAttribute("aria-pressed", "true");
  await pull(page, header, 200);
  await expect(dialog).toHaveCount(0);
});

test("mobile filters scroll normally and close on a downward flick from the top", async ({ page }) => {
  await page.goto("/events");
  const { dialog, panel } = await openFilters(page);
  const scroller = dialog.locator(".overflow-y-auto");
  await scroller.evaluate((element) => { element.scrollTop = 180; });
  await expect.poll(() => scroller.evaluate((element) => element.scrollTop)).toBeGreaterThan(0);
  await pull(page, scroller, 50);
  await expect(dialog).toBeVisible();
  await expect(panel).toHaveCSS("translate", "none");

  await scroller.evaluate((element) => { element.scrollTop = 0; });
  await pull(page, scroller, 70, true);
  await expect(dialog).toHaveCount(0);
});

test("mobile event details still close on a downward pull", async ({ page }) => {
  await page.goto("/events/e2e-highlander-hub-showcase");
  const dialog = page.getByRole("dialog");
  const heading = dialog.getByRole("heading", { name: "E2E Test: Highlander Hub Showcase" });
  await expect(heading).toBeVisible();
  await dialog.evaluate(async (element) => {
    await Promise.all(element.getAnimations().map((animation) => animation.finished));
  });
  await pull(page, heading, 200);
  await expect(dialog).toHaveCount(0);
  await expect(page).toHaveURL(/\/events$/);
});
