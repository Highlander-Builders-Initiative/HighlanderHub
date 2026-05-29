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

  assert.match(headers["Strict-Transport-Security"], /max-age=\d+/);
  assert.ok(headers["Permissions-Policy"].includes("geolocation=()"));

  const csp = headers["Content-Security-Policy"];
  assert.ok(csp, "expected a Content-Security-Policy header");
  for (const directive of [
    "default-src 'self'",
    "base-uri 'self'",
    "object-src 'none'",
    "frame-ancestors 'none'",
    "form-action 'self'",
  ]) {
    assert.ok(
      csp.includes(directive),
      `CSP should lock down ${directive}`
    );
  }
  // The browser uploads flyers straight to Supabase storage; that origin must
  // stay allowed in connect-src or submissions silently break.
  assert.ok(csp.includes("https://qyxlojftdtjasxhzyqil.supabase.co"));
});
