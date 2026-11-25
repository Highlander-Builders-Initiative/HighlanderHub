import { expect, test } from "@playwright/test";
import { signInAsAdmin } from "./admin-helpers";

test.beforeEach(async ({ context, baseURL, page }) => {
  await signInAsAdmin(context, baseURL!);
  await page.goto("/admin");
});

test("merging offers a choice where the listings disagree", async ({ page }) => {
  const pair = page.getByRole("listitem", { name: /Wellness Wednesday/ });
  await pair.click({ position: { x: 4, y: 4 } });
  await page.keyboard.press("2");
  await expect(pair.getByRole("button", { name: "Merge listings" })).toBeFocused();

  const venue = pair.getByRole("radiogroup", { name: "Venue" });
  await expect(venue.getByRole("radio", { name: /USP/ })).toBeChecked();
  await venue.getByText("Costo Hall 224").click();
  await expect(venue.getByRole("radio", { name: /Costo Hall 224/ })).toBeChecked();
  // The single post lacks an end time, so the quarterly one's is taken.
  await expect(
    pair.getByRole("radiogroup", { name: "End time" }).getByRole("radio", { name: /Ends/ })
  ).toBeChecked();

  await page.keyboard.press("Escape");
  await expect(pair.getByRole("button", { name: "Merge listings" })).toHaveCount(0);
});

test("search finds a listing from a pasted Instagram link, and filters narrow the list", async ({ page }) => {
  const live = page.getByRole("region", { name: "Live events" });
  await page.keyboard.press("/");
  await expect(page.getByRole("searchbox", { name: "Search live events" })).toBeFocused();
  await page.keyboard.type("https://www.instagram.com/p/E2ESingle1/?igsh=abc&img_index=1");
  await expect(live.getByRole("article")).toHaveCount(1);
  await expect(live.getByText("Showing 1 of 7")).toBeVisible();

  await page.keyboard.press("Escape");
  await live.getByRole("button", { name: /Hidden from public/ }).click();
  await expect(live.getByRole("article")).toHaveCount(1);
  await expect(live.getByText("Hidden · Fundraiser")).toBeVisible();
});

test("the edit drawer is a labelled modal that guards unsaved changes", async ({ page }) => {
  const edit = page
    .getByRole("region", { name: "Live events" })
    .getByRole("button", { name: "Edit Study Jam" });
  await edit.click();

  const dialog = page.getByRole("dialog", { name: "Edit event" });
  await expect(dialog).toBeVisible();
  await dialog.getByLabel("Location").fill("Rivera Library");

  page.once("dialog", (prompt) => prompt.dismiss());
  await page.keyboard.press("Escape");
  await expect(dialog).toBeVisible();

  page.once("dialog", (prompt) => prompt.accept());
  await dialog.getByRole("button", { name: "Close" }).click();
  await expect(dialog).toBeHidden();
  await expect(edit).toBeFocused();
});
