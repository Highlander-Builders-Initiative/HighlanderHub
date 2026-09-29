import { expect, test } from "@playwright/test";

test("admin dashboard rejects missing and forged sessions", async ({ page, context, baseURL }) => {
  await page.goto("/admin");
  await expect(page).toHaveURL(/\/admin\/login$/);
  await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();

  await context.addCookies([{
    name: "hh_admin_session",
    value: `${Date.now() + 86400000}.${"a".repeat(64)}`,
    url: baseURL!,
  }]);
  await page.goto("/admin");
  await expect(page).toHaveURL(/\/admin\/login$/);
  await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
});

test("admin RSC requests and image optimizer reject untrusted access", async ({ request }) => {
  const response = await request.get("/admin", { headers: { RSC: "1" }, maxRedirects: 0 });
  const body = await response.text();
  expect(response.status() === 307 || body.includes("NEXT_REDIRECT")).toBe(true);
  expect(body).not.toContain("event_duplicate_reviews");
  const image = await request.get("/_next/image", {
    params: { url: "http://127.0.0.1/private", w: "640", q: "75" },
  });
  expect(image.status()).toBe(400);
});
