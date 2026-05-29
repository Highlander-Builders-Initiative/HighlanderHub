import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { test } from "node:test";

const require = createRequire(import.meta.url);
const nextConfigPath = require.resolve("../next.config.js");

const loadNextConfig = (nodeEnv) => {
  const previousNodeEnv = process.env.NODE_ENV;
  if (nodeEnv === undefined) {
    delete process.env.NODE_ENV;
  } else {
    process.env.NODE_ENV = nodeEnv;
  }
  delete require.cache[nextConfigPath];

  try {
    return require(nextConfigPath);
  } finally {
    delete require.cache[nextConfigPath];
    if (previousNodeEnv === undefined) {
      delete process.env.NODE_ENV;
    } else {
      process.env.NODE_ENV = previousNodeEnv;
    }
  }
};

const getAllRouteHeaders = async (nextConfig) => {
  assert.equal(typeof nextConfig.headers, "function");

  const rules = await nextConfig.headers();
  const allRoutesRule = rules.find((rule) => rule.source === "/:path*");

  assert.ok(allRoutesRule);

  return Object.fromEntries(
    allRoutesRule.headers.map(({ key, value }) => [key, value])
  );
};

const getCspDirective = (csp, directiveName) => {
  const directive = csp
    .split("; ")
    .find(
      (entry) => entry === directiveName || entry.startsWith(`${directiveName} `)
    );
  assert.ok(directive, `expected ${directiveName} in CSP`);
  if (directive === directiveName) {
    return [];
  }
  return directive.split(" ").slice(1);
};

test("next config applies core security headers to all routes", async () => {
  const nextConfig = loadNextConfig();
  const headers = await getAllRouteHeaders(nextConfig);

  assert.equal(headers["X-Frame-Options"], undefined);
  assert.equal(headers["X-Content-Type-Options"], "nosniff");
  assert.equal(headers["Referrer-Policy"], "strict-origin-when-cross-origin");

  assert.equal(headers["Strict-Transport-Security"], undefined);
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
  const supabaseStoragePattern = nextConfig.images.remotePatterns.find(
    (pattern) =>
      pattern.pathname === "/storage/v1/object/public/submission-flyers/**"
  );
  assert.ok(supabaseStoragePattern);
  assert.ok(
    getCspDirective(csp, "connect-src").includes(
      `https://${supabaseStoragePattern.hostname}`
    )
  );
});

test("production headers enable HSTS and HTTPS upgrades", async () => {
  const headers = await getAllRouteHeaders(loadNextConfig("production"));

  assert.equal(
    headers["Strict-Transport-Security"],
    "max-age=63072000; includeSubDomains; preload"
  );
  assert.deepEqual(
    getCspDirective(
      headers["Content-Security-Policy"],
      "upgrade-insecure-requests"
    ),
    []
  );
});
