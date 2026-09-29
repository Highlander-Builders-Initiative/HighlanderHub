import { test } from "node:test";
import assert from "node:assert/strict";
import { importTsModule } from "./helpers/import-ts-module.mjs";

const { clientIp } = await importTsModule("src/lib/rate-limit.ts");

test("client address accepts IPs supplied by the trusted deployment proxy", () => {
  assert.equal(clientIp(new Headers({ "x-forwarded-for": "203.0.113.5, 10.0.0.1" })), "203.0.113.5");
  assert.equal(clientIp(new Headers({ "x-forwarded-for": "2001:db8::1" })), "2001:db8::1");
  assert.equal(clientIp(new Headers({ "x-real-ip": "203.0.113.6" })), "203.0.113.6");
});

test("missing or invalid addresses share a bucket", () => {
  for (const value of ["", "arbitrary-key", "999.1.1.1", "https://example.com"]) {
    assert.equal(clientIp(new Headers({ "x-forwarded-for": value })), "unknown");
  }
  assert.equal(clientIp(new Headers()), "unknown");
});
