import { expect, test } from "@playwright/test";

test("browses events, opens detail, and submits an event for review", async ({
  page,
}) => {
  await page.goto("/events");

  await expect(page.getByRole("heading", { name: "Events" })).toBeVisible();

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
  await page.route("**/rest/v1/submissions**", async (route) => {
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: "[]",
    });
  });

  await page.getByLabel("Event title").fill("E2E Submitted Event");
  await page
    .getByLabel("Description")
    .fill("Submitted by Playwright to verify the review flow.");
  await page.getByLabel("Starts").fill("2026-05-20T18:30");
  await page.getByLabel("Location").fill("HUB 302");
  await page.getByLabel("Host / organization").fill("Highlander Hub QA");
  await page.getByLabel("Your name").fill("Test Submitter");
  await page.getByLabel("Your email").fill("submitter@example.com");

  await page.getByRole("button", { name: "Submit for review" }).click();

  await expect(page.getByRole("heading", { name: "Got it." })).toBeVisible();
  await expect(page.getByText(/queued for review/i)).toBeVisible();
});
