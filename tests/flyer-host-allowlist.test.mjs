import assert from "node:assert/strict";
import { test } from "node:test";
import nextConfig from "../next.config.js";
import { hasMatch } from "next/dist/shared/lib/match-remote-pattern.js";
import { importTsModule } from "./helpers/import-ts-module.mjs";

const { isOptimizableFlyerHost } = await importTsModule(
  "src/lib/events/flyer-hosts.ts"
);

const remotePatterns = nextConfig.images?.remotePatterns ?? [];
const optimizerAllows = (url) => hasMatch([], remotePatterns, new URL(url));
const supabaseOrigin = new URL(
  process.env.NEXT_PUBLIC_SUPABASE_URL ??
    "https://qyxlojftdtjasxhzyqil.supabase.co"
).origin;

// The client-side helper must agree with the server-side optimizer allowlist:
// if it says "optimizable" for a host next/image actually rejects, the
// optimizer 400s and the flyer breaks. These URLs cover each pattern plus the
// edge cases (wrong path, extra subdomain segment, non-HTTPS, foreign host).
const cases = [
  "https://scontent-lax7-1.cdninstagram.com/v/t51.82787-15/flyer.jpg",
  "https://a.b.cdninstagram.com/flyer.jpg",
  "http://scontent-lax7-1.cdninstagram.com/flyer.jpg",
  "https://se-images.campuslabs.com/clink/images/flyer.jpg",
  "https://se-images.campuslabs.com/other/flyer.jpg",
  "https://localist-images.azureedge.net/photos/123/original.jpg",
  `${supabaseOrigin}/storage/v1/object/public/submission-flyers/abc.jpg`,
  `${supabaseOrigin}/storage/v1/object/public/event-flyers/instagram/acm_ucr/389.jpg`,
  `${supabaseOrigin}/storage/v1/object/public/other/abc.jpg`,
  "https://evil.example/flyer.jpg",
];

test("isOptimizableFlyerHost agrees with next/image remotePatterns", () => {
  for (const url of cases) {
    assert.equal(
      isOptimizableFlyerHost(url),
      optimizerAllows(url),
      `disagreement for ${url}`
    );
  }
});

test("isOptimizableFlyerHost rejects arbitrary and malformed input", () => {
  assert.equal(isOptimizableFlyerHost("not a url"), false);
  assert.equal(isOptimizableFlyerHost("https://evil.example/flyer.jpg"), false);
});
