import { expect, type Page } from "@playwright/test";

/** Category rail toggle (not active-filter chips, which also mention the label). */
export function categoryFilterButton(page: Page, label: string) {
  return page
    .getByRole("group", { name: "Filter events by category" })
    .getByRole("button", { name: new RegExp(`^${label}`) });
}

async function clickUntilPressed(page: Page, name: string) {
  const button = categoryFilterButton(page, name);
  await expect
    .poll(async () => {
      await button.click();
      return button.getAttribute("aria-pressed");
    })
    .toBe("true");
}

/**
 * Filter toggles only respond once React has hydrated. Card clicks before that
 * are plain anchor loads (full page) instead of intercepted overlays.
 */
export async function waitForEventsBrowserHydration(page: Page) {
  await clickUntilPressed(page, "Social");
  await clickUntilPressed(page, "All");
  // Wait for the filter navigation to commit before opening a detail route.
  await expect(page).toHaveURL(/\/events$/);
}
