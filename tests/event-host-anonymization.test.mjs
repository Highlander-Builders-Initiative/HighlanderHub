import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { test } from "node:test";

test("highlander_opps host is stripped for public display", () => {
  const result = spawnSync(
    process.execPath,
    [
      "--input-type=module",
      "--eval",
      `
        import { importTsModule } from "./tests/helpers/import-ts-module.mjs";
        const hosts = await importTsModule("src/lib/events/anonymized-hosts.ts");
        const sanitized = hosts.sanitizePublicEventHost(
          "highlander_opps",
          "highlander_opps"
        );
        console.log(JSON.stringify({
          isAnonymized: hosts.isAnonymizedHostHandle("@highlander_opps"),
          host: sanitized.host,
          hostHandle: sanitized.hostHandle ?? null,
          otherHost: hosts.sanitizePublicEventHost("ACM @ UCR", "acm_ucr").host,
        }));
      `,
    ],
    { cwd: process.cwd(), encoding: "utf8" }
  );

  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(JSON.parse(result.stdout.trim()), {
    isAnonymized: true,
    host: "",
    hostHandle: null,
    otherHost: "ACM @ UCR",
  });
});
