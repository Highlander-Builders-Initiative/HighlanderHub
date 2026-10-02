import assert from "node:assert/strict";
import { test } from "node:test";
import {
  optimizerAllows as allows,
  remotePatterns,
  supabaseOrigin,
} from "./helpers/next-remote-match.mjs";

test("next/image remote patterns do not allow arbitrary HTTPS hosts", () => {
  assert.ok(remotePatterns.length > 0);
  assert.equal(
    remotePatterns.some(
      (pattern) => pattern.protocol === "https" && pattern.hostname === "**"
    ),
    false
  );

  assert.equal(allows("https://evil.example/flyer.jpg"), false);
});

test("next/image remote patterns allow scraper-produced image hosts", () => {
  assert.equal(
    allows(
      "https://scontent-lax7-1.cdninstagram.com/v/t51.82787-15/flyer.jpg"
    ),
    true
  );
  assert.equal(
    allows(
      `${supabaseOrigin}/storage/v1/object/public/submission-flyers/829c3a3b-93fc-47b4-9c16-ee00fa356710.jpg`
    ),
    false
  );
  assert.equal(
    allows(
      `${supabaseOrigin}/storage/v1/object/public/event-flyers/instagram/acm_ucr/3894795737410658767.jpg`
    ),
    true
  );
});

test("optimized flyers stay cached long enough not to re-spend transformations", async () => {
  const { default: nextConfig } = await import("../next.config.js");
  // Supabase answers `cache-control: no-cache`, so this TTL alone decides how
  // often Vercel re-optimizes each flyer variant.
  assert.ok(nextConfig.images.minimumCacheTTL >= 30 * 24 * 60 * 60);
});
