import { expect, test } from "@playwright/test";

test("browses events, opens detail, and submits an event for review", async ({
  page,
}) => {
  await page.goto("/events");

  await expect(page.getByLabel(/Search events/i)).toBeVisible();

  await page
    .getByRole("link", {
      name: /E2E Test: Highlander Hub Showcase/i,
    })
    .click();

  await expect(
    page.getByRole("heading", { name: "E2E Test: Highlander Hub Showcase" })
  ).toBeVisible();
  await expect(page.getByRole("button", { name: /Back/i })).toBeVisible();
  await expect(page.getByRole("link", { name: /Add to calendar/i })).toBeVisible();
  await expect(page.getByRole("button", { name: /Share/i })).toBeVisible();

  await page.goto("/submit");
  await page.route("**/api/submissions", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ok: true }),
    });
  });

  await page.getByLabel("Event title").fill("E2E Submitted Event");
  await page
    .getByLabel("Description")
    .fill("Submitted by Playwright to verify the review flow.");
  await page.getByRole("button", { name: "Tomorrow" }).click();
  const startTime = page.getByRole("group", { name: "Start time" });
  await startTime.getByLabel("Hours").fill("06");
  await startTime.getByLabel("Minutes").fill("30");
  const periodToggle = startTime.getByRole("button", { name: /Period:/ });
  if ((await periodToggle.textContent())?.includes("AM")) {
    await periodToggle.click();
  }
  await page.getByLabel("Location").fill("HUB 302");
  await page.getByLabel("Hosted by").fill("Highlander Hub QA");
  await page.getByLabel("Your name").fill("Test Submitter");
  await page.getByLabel("Your email").fill("submitter@example.com");

  await page.getByRole("button", { name: "Submit for review" }).click();

  await expect(page.getByRole("heading", { name: "Got it." })).toBeVisible();
  await expect(page.getByText(/queued for review/i)).toBeVisible();
});
