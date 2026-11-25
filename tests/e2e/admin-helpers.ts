import crypto from "node:crypto";
import type { BrowserContext } from "@playwright/test";

/**
 * The admin password for fixture-mode e2e servers only (see
 * playwright.config.ts). It guards nothing real: fixture mode serves sample
 * listings and has no database credentials.
 */
export const E2E_ADMIN_PASSWORD = "e2e-fixture-admin-password-not-a-secret";

/** Signs in the way loginAdmin does, without its database rate limit. */
export async function signInAsAdmin(context: BrowserContext, baseURL: string) {
  const expiresAt = String(Date.now() + 60 * 60 * 1000);
  const signature = crypto
    .createHmac("sha256", E2E_ADMIN_PASSWORD)
    .update(expiresAt)
    .digest("hex");
  await context.addCookies([
    { name: "hh_admin_session", value: `${expiresAt}.${signature}`, url: baseURL },
  ]);
}
