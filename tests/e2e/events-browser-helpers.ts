import type { Page } from "@playwright/test";

/** Category rail toggle (not active-filter chips, which also mention the label). */
export function categoryFilterButton(page: Page, label: string) {
  return page
    .getByRole("group", { name: "Filter events by category" })
    .getByRole("button", { name: new RegExp(`^${label}`) });
}
