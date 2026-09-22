import { expect, test } from "@playwright/test";
import { waitForEventsBrowserHydration } from "./events-browser-helpers";

test("club search includes scraped accounts outside the configured roster", async ({ page }) => {
  await page.goto("/events");
  await waitForEventsBrowserHydration(page);
  const search = page.getByRole("combobox", { name: "Search events and clubs" });
  await search.fill("@3d_at_ucr");
  await expect(page.getByRole("option")).toContainText("@3d_at_ucr");
  await page.getByRole("option").click();
  await expect(search).toHaveValue("3d_at_ucr");
  await expect(page).toHaveURL(/q=3d_at_ucr/);
});

test("current event hosts appear by name and selection retains their events", async ({ page }) => {
  await page.goto("/events");
  await waitForEventsBrowserHydration(page);
  const search = page.getByRole("combobox", { name: "Search events and clubs" });
  await search.fill("Highlander Hub QA");
  await expect(page.getByRole("option")).toContainText("@highlanderhub");
  await search.press("ArrowDown");
  await search.press("Enter");
  await expect(search).toHaveValue("highlanderhub");
  await expect(page).toHaveURL(/q=highlanderhub/);
  await expect(page.getByRole("link", { name: /E2E Test: Highlander Hub Showcase/ }).first()).toBeVisible();
});
