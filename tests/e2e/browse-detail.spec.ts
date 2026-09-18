import { expect, test } from "@playwright/test";
import { waitForEventsBrowserHydration } from "./events-browser-helpers";

test("browses events and opens detail", async ({ page }) => {
  await page.goto("/events");

  await expect(page.getByLabel(/Search events/i)).toBeVisible();
  await waitForEventsBrowserHydration(page);

  await page
    .getByRole("link", {
      name: /E2E Test: Highlander Hub Showcase/i,
    })
    .click();

  const dialog = page.getByRole("dialog");
  await expect(
    dialog.getByRole("heading", { name: "E2E Test: Highlander Hub Showcase" })
  ).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Close event" })).toBeVisible();
  await expect(
    dialog.getByRole("button", { name: /Add to calendar/i })
  ).toBeVisible();
  await expect(dialog.getByRole("button", { name: /Share/i })).toBeVisible();
});
