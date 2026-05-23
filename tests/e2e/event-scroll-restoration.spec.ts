import { expect, test, type Page } from "@playwright/test";

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

async function clickUntilPressed(page: Page, name: string) {
  const button = page.getByRole("button", { name });
  await expect
    .poll(async () => {
      await button.click();
      return button.getAttribute("aria-pressed");
    })
    .toBe("true");
}

async function waitForEventsBrowserHydration(page: Page) {
  await clickUntilPressed(page, "Social");
  await clickUntilPressed(page, "All");
}

test("event detail returns to the prior scroll position", async ({
  page,
}: {
  page: Page;
}) => {
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
  await expect(
    page.getByRole("heading", {
      level: 1,
      name: "E2E Test: Highlander Hub Showcase",
    })
  ).toBeVisible();

  await Promise.all([page.waitForURL("**/events"), page.goBack()]);
  await expect(page.getByRole("heading", { name: "Events" })).toBeVisible();
  await waitForNoLoadError(page);
  await waitForEventsBrowserHydration(page);
  await waitForEventTop(page, firstSavedTop);

  await Promise.all([
    page.waitForURL("**/events/e2e-highlander-hub-showcase"),
    eventLink.click(),
  ]);
  const secondSavedTop = await readSavedEventTop(page);
  expect(secondSavedTop).not.toBeNull();
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
  await waitForNoLoadError(page);
  await waitForEventTop(page, secondSavedTop);
});
