import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const read = (path) =>
  readFileSync(new URL(`../${path}`, import.meta.url), "utf8");

test("about page opens with one editorial why-it-exists section", () => {
  const source = read("src/app/about/page.tsx");

  assert.match(source, /Campus events are scattered across ten different feeds\./);
  assert.doesNotMatch(source, /Why Highlander Hub exists\./);
  assert.doesNotMatch(source, /Scattered across ten feeds\./);
});
