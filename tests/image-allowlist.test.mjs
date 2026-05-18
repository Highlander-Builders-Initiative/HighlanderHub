import assert from "node:assert/strict";
import { test } from "node:test";
import nextConfig from "../next.config.js";
import { hasMatch } from "next/dist/shared/lib/match-remote-pattern.js";

const remotePatterns = nextConfig.images?.remotePatterns ?? [];
const allows = (url) => hasMatch([], remotePatterns, new URL(url));

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
    allows("https://se-images.campuslabs.com/clink/images/flyer.jpg"),
    true
  );
  assert.equal(
    allows(
      "https://localist-images.azureedge.net/photos/123456789/original.jpg"
    ),
    true
  );
});
