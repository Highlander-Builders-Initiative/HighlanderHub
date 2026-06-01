import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const read = (relPath) => readFileSync(join(__dirname, "..", relPath), "utf8");

// The suite can't execute TypeScript (no ts-node), so assert on source the same
// way admin-event-update.test.mjs and security-headers.test.mjs do.

test("rate-limit lib exposes the limiter, IP helper, and tuned configs", () => {
  const src = read("src/lib/rate-limit.ts");

  assert.match(src, /export function rateLimit\(/);
  assert.match(src, /export function clientIp\(/);
  assert.match(src, /export function rateLimitHeaders\(/);
  assert.match(src, /export const SUBMISSION_RATE_LIMIT/);
  assert.match(src, /export const ADMIN_LOGIN_RATE_LIMIT/);

  // Fixed-window blocks once the per-key count reaches the limit.
  assert.match(src, /existing\.count >= limit/);
  // Expired entries are swept so the Map can't grow unbounded.
  assert.match(src, /store\.delete\(key\)/);
  // IP is taken from the leftmost proxy-forwarded address.
  assert.match(src, /x-forwarded-for/);
});

test("public submissions endpoint is rate limited with a 429", () => {
  const src = read("src/app/api/submissions/route.ts");

  assert.match(src, /SUBMISSION_RATE_LIMIT/);
  assert.match(src, /rateLimit\(\s*`submissions:\$\{clientIp\(request\.headers\)\}`/);
  assert.match(src, /status:\s*429/);

  // The guard must run before the row is inserted, so a flood is cheap to
  // reject and never reaches the DB or the Discord webhook.
  const guardIndex = src.indexOf("if (!limit.ok)");
  const insertIndex = src.indexOf('.from("submissions").insert');
  assert.ok(guardIndex !== -1, "expected a rate-limit guard");
  assert.ok(insertIndex !== -1, "expected the submissions insert");
  assert.ok(guardIndex < insertIndex, "rate-limit guard must precede the insert");
});

test("admin login is rate limited per IP to blunt brute-force", () => {
  const src = read("src/app/admin/actions.ts");

  assert.match(src, /ADMIN_LOGIN_RATE_LIMIT/);
  assert.match(src, /rateLimit\(\s*`admin-login:\$\{clientIp\(headers\(\)\)\}`/);

  // The throttle must gate verifyPassword, not run after a successful check.
  const guardIndex = src.indexOf("admin-login:");
  const verifyIndex = src.indexOf("verifyPassword(password)");
  assert.ok(guardIndex !== -1 && verifyIndex !== -1);
  assert.ok(guardIndex < verifyIndex, "throttle must precede password check");
});
