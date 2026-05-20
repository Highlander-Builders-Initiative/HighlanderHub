import { expect, test } from "@playwright/test";

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
  await expect(summary).toHaveText("1 event loaded");

  await page.getByRole("button", { name: "Social" }).click();
  await expect(page.getByRole("button", { name: "Social" })).toHaveAttribute(
    "aria-pressed",
    "true"
  );
  await expect(summary).toHaveText("1 matching event");
  await expect(page.getByRole("button", { name: "Clear" })).toBeVisible();

  await search.fill("does-not-match");
  await expect(summary).toHaveText("0 matching events");
  await expect(page.getByText("No matches.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Clear filters" })).toBeVisible();

  await page.getByRole("button", { name: "Clear filters" }).click();
  await expect(summary).toHaveText("1 event loaded");
});
