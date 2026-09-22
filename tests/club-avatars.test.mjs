import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { test } from "node:test";
import { importTsModule } from "./helpers/import-ts-module.mjs";

const { clubAvatarSrc, clubInitials } = await importTsModule("src/lib/club-avatars.ts");
const { avatars } = JSON.parse(readFileSync(new URL("../src/lib/club-avatars.json", import.meta.url)));
const avatarDir = new URL("../public/club-avatars/", import.meta.url);
const files = (() => {
  try {
    return readdirSync(avatarDir).filter((name) => name.endsWith(".webp"));
  } catch {
    return [];
  }
})();

test("the manifest and the committed pictures list the same clubs", () => {
  assert.deepEqual(
    files.map((name) => name.slice(0, -".webp".length)).sort(),
    Object.keys(avatars).sort()
  );
  for (const name of files) {
    const bytes = readFileSync(new URL(name, avatarDir));
    assert.equal(bytes.subarray(8, 12).toString("latin1"), "WEBP", name);
    // 128px pictures are a few KB; a large file means a resize step was skipped.
    assert.ok(statSync(new URL(name, avatarDir)).size < 32_000, name);
  }
});

test("avatar lookups normalize handles and only resolve listed clubs", () => {
  const [handle] = Object.keys(avatars);
  if (handle) {
    assert.equal(clubAvatarSrc(` @${handle.toUpperCase()} `), `/club-avatars/${handle}.webp`);
  }
  assert.equal(clubAvatarSrc("definitely_not_a_listed_club"), undefined);
  assert.equal(clubAvatarSrc(""), undefined);
  assert.equal(clubAvatarSrc(undefined), undefined);
  assert.equal(clubAvatarSrc("highlander_opps"), undefined);
  assert.equal(Object.hasOwn(avatars, "highlander_opps"), false);
});

test("monograms skip connective words and numbering", () => {
  assert.equal(clubInitials("Association for Computing Machinery at UCR"), "AC");
  assert.equal(clubInitials("909 Dance Troupe"), "DT");
  assert.equal(clubInitials("@acm_ucr"), "AU");
  assert.equal(clubInitials("ACM"), "AC");
  assert.equal(clubInitials(""), "?");
});
