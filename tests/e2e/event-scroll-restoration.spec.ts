import { expect, test, type Page } from "@playwright/test";
import { waitForEventsBrowserHydration } from "./events-browser-helpers";

async function readScrollY(page: Page) {
  return page.evaluate(() => window.scrollY);
}

async function readSavedEventTop(page: Page) {
  return page.evaluate(() => {
    const saved = sessionStorage.getItem("highlanderhub.returnScroll");
    if (!saved) return null;
    const parsed = JSON.parse(saved);
    return typeof parsed.eventTop === "number" ? parsed.eventTop : null;
  });
}

async function waitForEventTop(page: Page, targetTop: number) {
  await page.waitForFunction(
    ({ targetTop }: { targetTop: number }) => {
      const card = document.querySelector(
        '[data-event-id="e2e-highlander-hub-showcase"]'
      );
      return (
        card instanceof HTMLElement &&
        Math.abs(card.getBoundingClientRect().top - targetTop) <= 8
      );
    },
    { targetTop }
  );
}

async function waitForNoLoadError(page: Page) {
  await expect(page.getByText("Could not load more events. Try again.")).toHaveCount(
    0
  );
}

function eventOverlayHeading(page: Page) {
  return page.getByRole("dialog").getByRole("heading", {
    name: "E2E Test: Highlander Hub Showcase",
  });
}

test("event overlay closes back to the prior scroll position", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 480 });
  await page.goto("/events");
  await page.addStyleTag({
    content:
      "html { scroll-behavior: auto !important; } #events { padding-top: 900px !important; } main { min-height: 2400px !important; }",
  });
  await waitForEventsBrowserHydration(page);

  const eventLink = page.getByRole("link", {
    name: /E2E Test: Highlander Hub Showcase/i,
  });

  await eventLink.scrollIntoViewIfNeeded();

  const scrolledY = await readScrollY(page);
  expect(scrolledY).toBeGreaterThan(0);

  await Promise.all([
    page.waitForURL("**/events/e2e-highlander-hub-showcase"),
    eventLink.click(),
  ]);
  const firstSavedTop = await readSavedEventTop(page);
  expect(firstSavedTop).not.toBeNull();
  await expect(eventOverlayHeading(page)).toBeVisible();

  await Promise.all([page.waitForURL("**/events"), page.goBack()]);
  await expect(
    page.getByLabel(/Search events/i)
  ).toBeVisible();
  await waitForNoLoadError(page);
  await waitForEventsBrowserHydration(page);
  await waitForEventTop(page, firstSavedTop);

  await Promise.all([
    page.waitForURL("**/events/e2e-highlander-hub-showcase"),
    eventLink.click(),
  ]);
  const secondSavedTop = await readSavedEventTop(page);
  expect(secondSavedTop).not.toBeNull();
  await expect(eventOverlayHeading(page)).toBeVisible();

  await Promise.all([
    page.waitForURL("**/events"),
    page
      .getByRole("dialog")
      .getByRole("button", { name: "Close event" })
      .click(),
  ]);
  // Closing onto the still-mounted list spends the return marker.
  await expect
    .poll(() =>
      page.evaluate(() => sessionStorage.getItem("highlanderhub.returnScroll"))
    )
    .toBeNull();
  await expect(
    page.getByLabel(/Search events/i)
  ).toBeVisible();
  await waitForNoLoadError(page);
  await waitForEventTop(page, secondSavedTop);
});
