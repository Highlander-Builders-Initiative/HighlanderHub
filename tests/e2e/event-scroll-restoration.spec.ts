import { expect, test } from "@playwright/test";

async function readScrollY(page) {
  return page.evaluate(() => window.scrollY);
}

async function readTop(locator) {
  return locator.evaluate((el) => el.getBoundingClientRect().top);
}

test("event detail returns to the prior scroll position", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 480 });
  await page.goto("/events");
  await page.addStyleTag({
    content:
      "html { scroll-behavior: auto !important; } #events { padding-top: 900px !important; } main { min-height: 2400px !important; }",
  });

  const eventLink = page.getByRole("link", {
    name: /E2E Test: Highlander Hub Showcase/i,
  });

  await eventLink.scrollIntoViewIfNeeded();

  const scrolledY = await readScrollY(page);
  const originalTop = await readTop(eventLink);
  expect(scrolledY).toBeGreaterThan(0);

  await Promise.all([
    page.waitForURL("**/events/e2e-highlander-hub-showcase"),
    eventLink.click(),
  ]);
  await expect(
    page.getByRole("heading", {
      level: 1,
      name: "E2E Test: Highlander Hub Showcase",
    })
  ).toBeVisible();

  await Promise.all([page.waitForURL("**/events"), page.goBack()]);
  await expect(page.getByRole("heading", { name: "Events" })).toBeVisible();
  await page.waitForFunction(
    ({ targetTop }) => {
      const card = document.querySelector(
        '[data-event-id="e2e-highlander-hub-showcase"]'
      );
      return (
        card instanceof HTMLElement &&
        Math.abs(card.getBoundingClientRect().top - targetTop) <= 8
      );
    },
    { targetTop: originalTop }
  );
  const secondTop = await readTop(eventLink);

  await Promise.all([
    page.waitForURL("**/events/e2e-highlander-hub-showcase"),
    eventLink.click(),
  ]);
  await expect(
    page.getByRole("heading", {
      level: 1,
      name: "E2E Test: Highlander Hub Showcase",
    })
  ).toBeVisible();

  await Promise.all([
    page.waitForURL("**/events"),
    page.getByRole("button", { name: /Back/i }).click(),
  ]);
  await expect(page.getByRole("heading", { name: "Events" })).toBeVisible();
  await page.waitForFunction(
    ({ targetTop }) => {
      const card = document.querySelector(
        '[data-event-id="e2e-highlander-hub-showcase"]'
      );
      return (
        card instanceof HTMLElement &&
        Math.abs(card.getBoundingClientRect().top - targetTop) <= 8
      );
    },
    { targetTop: secondTop }
  );
});
