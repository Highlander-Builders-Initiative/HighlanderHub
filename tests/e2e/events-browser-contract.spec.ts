import { expect, test } from "@playwright/test";
import { categoryFilterButton, waitForEventsBrowserHydration } from "./events-browser-helpers";

test("a newer filter selection cancels an in-flight replacement of the current URL", async ({ page }) => {
  await page.goto("/events");
  await waitForEventsBrowserHydration(page);

  let releaseSocialResponse!: () => void;
  const socialResponse = new Promise<void>((resolve) => {
    releaseSocialResponse = resolve;
  });
  let socialRequests = 0;
  let allRequests = 0;
  await page.route(/\/events\?/, async (route) => {
    const url = new URL(route.request().url());
    if (route.request().headers().rsc !== "1") {
      await route.continue();
      return;
    }
    if (url.searchParams.get("cat") === "social") {
      socialRequests += 1;
      await socialResponse;
    } else if (!url.searchParams.has("cat")) {
      allRequests += 1;
    }
    await route.continue();
  });

  try {
    await categoryFilterButton(page, "Social").click();
    await expect.poll(() => socialRequests).toBeGreaterThan(0);
    await categoryFilterButton(page, "All").click();
    await expect(categoryFilterButton(page, "All")).toHaveAttribute("aria-pressed", "true");
    // Even though the address bar still says /events, replace the pending
    // social navigation so its response cannot leave the feed filtered.
    await expect.poll(() => allRequests).toBeGreaterThan(0);
  } finally {
    releaseSocialResponse();
  }
  await expect(page).toHaveURL(/\/events$/);
  await expect(page.locator("[data-event-id]")).toHaveCount(2);
  await expect(page.locator("#event-filter-summary")).toHaveText("2 events loaded");
});

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
  await expect(summary).toHaveText("2 events loaded");

  const socialFilter = categoryFilterButton(page, "Social");
  await socialFilter.click();
  await expect(socialFilter).toHaveAttribute("aria-pressed", "true");
  await expect(summary).toHaveText("1 matching event");
  await expect(page.getByRole("button", { name: "Clear" })).toBeVisible();

  await search.fill("does-not-match");
  await expect(summary).toHaveText("0 matching events");
  await expect(page.getByText(/Nothing in Social matches/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Clear filters" })).toBeVisible();

  await page.getByRole("button", { name: "Clear filters" }).click();
  await expect(summary).toHaveText("2 events loaded");
});

test("club suggestion highlight survives narrowed search results", async ({
  page,
}) => {
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));

  await page.goto("/events");

  const search = page.getByLabel("Search events");
  await search.fill("ucr");
  await expect(page.getByRole("listbox", { name: "Clubs" })).toBeVisible();

  for (let i = 0; i < 6; i += 1) {
    await search.press("ArrowDown");
  }

  await search.fill("mcvb");

  await expect(page.getByRole("option", { name: /ucr_mcvb/i })).toBeVisible();
  expect(pageErrors).toEqual([]);
});

test("calendar shows loading state while month events refresh", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto("/events");

  const calendarRail = page.getByRole("complementary", {
    name: "Calendar and time filter",
  });
  const calendarHeading = calendarRail.getByRole("heading", { level: 2 });
  await expect(calendarRail).toBeVisible();
  // The calendar follows the feed's first visible day, so it settles on the
  // observed month (May 2026) shortly after load. Wait for that initial sync to
  // finish before testing a navigation fetch — otherwise the stray sync request
  // races the click and the displayed month reads as already-loaded on slow CI.
  await expect(calendarHeading).toHaveText(/may 2026/i);

  let releaseCalendarResponse!: () => void;
  const calendarResponse = new Promise<void>((resolve) => {
    releaseCalendarResponse = resolve;
  });

  // Installed only after the initial sync settled, so the single request it holds
  // open is the one triggered by the Next-month click below.
  await page.route("**/api/events/calendar**", async (route) => {
    await calendarResponse;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ events: [] }),
    });
  });

  const calendarGrid = calendarRail.locator("[aria-busy]").first();
  await calendarRail.getByRole("button", { name: "Next month" }).click();
  await expect(calendarHeading).toHaveText(/june 2026/i);
  await expect(calendarGrid).toHaveAttribute("aria-busy", "true");

  releaseCalendarResponse();
  await expect(calendarGrid).toHaveAttribute("aria-busy", "false");
});

test("calendar trailing next-month days load that month before jumping", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto("/events");

  const calendarRail = page.getByRole("complementary", {
    name: "Calendar and time filter",
  });
  const calendarHeading = calendarRail.getByRole("heading", { level: 2 });
  await expect(calendarRail).toBeVisible();
  await expect(calendarHeading).toHaveText(/may 2026/i);

  const nextMonthEvent = {
    id: "e2e-next-month-jump",
    title: "E2E Test: Next Month Jump",
    description:
      "A deterministic event used to verify out-of-month calendar jumps.",
    startsAt: "2026-06-01T18:30:00.000-07:00",
    endsAt: "2026-06-01T20:00:00.000-07:00",
    location: "HUB 260",
    host: "Highlander Hub QA",
    hostHandle: "@highlanderhub",
    category: "social",
    tags: ["e2e", "calendar"],
    source: "manual",
    sourceUrl: "https://example.com/e2e-next-month-jump",
    hasFreeFood: false,
    rsvpRequired: false,
    scrapedAt: "2026-05-18T12:00:00.000Z",
  };
  let nextMonthRequestCount = 0;

  await page.route("**/api/events/calendar**", async (route) => {
    const url = new URL(route.request().url());
    if (
      url.searchParams.get("start") === "2026-05-31" &&
      url.searchParams.get("end") === "2026-07-11"
    ) {
      nextMonthRequestCount += 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ events: [nextMonthEvent] }),
      });
      return;
    }

    await route.continue();
  });

  await calendarRail
    .getByRole("button", { name: "Jump to 2026-06-01" })
    .click();

  // Cursor flips on click; the mocked month fetch can finish later on slow CI runners.
  await expect
    .poll(async () => calendarHeading.textContent(), { timeout: 15_000 })
    .toMatch(/june 2026/i);
  await expect.poll(() => nextMonthRequestCount).toBeGreaterThan(0);
  await expect(calendarRail.locator('[aria-busy="true"]')).toHaveCount(0);
  await expect(page.locator('[data-day-key="2026-06-01"]')).toBeAttached();
  await expect(page.getByText(nextMonthEvent.title)).toBeVisible();
});

test("empty adjacent-month calendar days release the pending jump", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto("/events");

  const calendarRail = page.getByRole("complementary", {
    name: "Calendar and time filter",
  });
  const calendarHeading = calendarRail.getByRole("heading", { level: 2 });
  await expect(calendarRail).toBeVisible();
  await expect(calendarHeading).toHaveText(/may 2026/i);

  let nextMonthRequestCount = 0;
  await page.route("**/api/events/calendar**", async (route) => {
    const url = new URL(route.request().url());
    if (
      url.searchParams.get("start") === "2026-05-31" &&
      url.searchParams.get("end") === "2026-07-11"
    ) {
      nextMonthRequestCount += 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ events: [] }),
      });
      return;
    }

    await route.continue();
  });

  await calendarRail
    .getByRole("button", { name: "Jump to 2026-06-02, no events" })
    .click();

  await expect
    .poll(async () => calendarHeading.textContent(), { timeout: 15_000 })
    .toMatch(/june 2026/i);
  await expect.poll(() => nextMonthRequestCount).toBeGreaterThan(0);
  await expect(calendarRail.locator('[aria-busy="true"]')).toHaveCount(0);

  await page.waitForTimeout(700);
  await page.mouse.wheel(0, 160);

  await expect
    .poll(async () => calendarHeading.textContent(), { timeout: 15_000 })
    .toMatch(/may 2026/i);
});

test("calendar jumps leave the selected day below the sticky search bar", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto("/events");

  const dayKey = "2026-05-20";
  const dayButton = page.getByRole("button", { name: `Jump to ${dayKey}` });
  const dayHeader = page.locator(`[data-day-key="${dayKey}"]`);
  const search = page.getByLabel("Search events");

  await dayButton.click();

  await expect.poll(async () => {
    const searchBox = await search.boundingBox();
    const headerBox = await dayHeader.boundingBox();
    if (!searchBox || !headerBox) return -1;
    return headerBox.y - (searchBox.y + searchBox.height + 8);
  }).toBeGreaterThan(0);
});

test("calendar jumps back to a day that is already loaded", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto("/events");

  // A month fetch finishing mid-jump re-runs the scroll effect on its own and
  // would hide the bug, so start from a settled calendar.
  const calendarRail = page.getByRole("complementary", {
    name: "Calendar and time filter",
  });
  await expect(calendarRail.getByRole("heading", { level: 2 })).toHaveText(
    /may 2026/i
  );
  await expect(calendarRail.locator('[aria-busy="true"]')).toHaveCount(0);

  const dayKey = "2026-05-20";
  const dayHeader = page.locator(`[data-day-key="${dayKey}"]`);
  const headerTop = () =>
    dayHeader.evaluate((el) => el.getBoundingClientRect().top);

  await page.evaluate(() =>
    window.scrollTo(0, document.documentElement.scrollHeight)
  );
  await expect.poll(headerTop).toBeLessThan(0);

  await page.getByRole("button", { name: `Jump to ${dayKey}` }).click();

  await expect.poll(headerTop).toBeGreaterThanOrEqual(0);
});
