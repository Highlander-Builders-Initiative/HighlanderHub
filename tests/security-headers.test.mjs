import assert from "node:assert/strict";
import { test } from "node:test";
import nextConfig from "../next.config.js";

test("next config applies core security headers to all routes", async () => {
  assert.equal(typeof nextConfig.headers, "function");

  const rules = await nextConfig.headers();
  const allRoutesRule = rules.find((rule) => rule.source === "/:path*");

  assert.ok(allRoutesRule);

  const headers = Object.fromEntries(
    allRoutesRule.headers.map(({ key, value }) => [key, value])
  );

  assert.equal(headers["X-Frame-Options"], "DENY");
  assert.equal(headers["X-Content-Type-Options"], "nosniff");
  assert.equal(headers["Referrer-Policy"], "strict-origin-when-cross-origin");
});
