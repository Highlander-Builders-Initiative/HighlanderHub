import { expect, test } from "@playwright/test";

// Fixtures (HIGHLANDERHUB_E2E_FIXTURES=1) carry one row per content_kind:
// a student_event showcase, a student_deadline, a fundraiser, and an "other".
// Public /events must show the first two and exclude the last two.

test("public browse shows student events + deadlines, hides fundraiser/other", async ({
  page,
}) => {
  await page.goto("/events");

  await expect(
    page.getByRole("link", { name: /E2E Test: Highlander Hub Showcase/i })
  ).toBeVisible();

  // Deadlines stay in the feed but read as deadlines (link name leads with it).
  await expect(
    page.getByRole("link", {
      name: /Deadline: E2E Deadline: Scholarship Applications Due/i,
    })
  ).toBeVisible();

  // Fundraiser and other are excluded from public browse entirely.
  await expect(
    page.getByText("E2E Fundraiser: Boba Benefit Night")
  ).toHaveCount(0);
  await expect(
    page.getByText("E2E Other: Campus Facilities Notice")
  ).toHaveCount(0);
});

test("deadline detail uses reminder-oriented copy", async ({ page }) => {
  await page.goto("/events/e2e-student-deadline");

  await expect(
    page.getByRole("heading", {
      name: "E2E Deadline: Scholarship Applications Due",
    })
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: /Add reminder/i }).first()
  ).toBeVisible();
});

test("a direct link to an excluded kind still resolves", async ({ page }) => {
  // getEventById is intentionally not content-kind filtered: deep links work
  // even though the item never appears in browse.
  await page.goto("/events/e2e-fundraiser");

  await expect(
    page.getByRole("heading", { name: "E2E Fundraiser: Boba Benefit Night" })
  ).toBeVisible();
});
