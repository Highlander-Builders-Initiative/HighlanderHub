import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

const repoRoot = fileURLToPath(new URL("../", import.meta.url));

function readJson(path) {
  return JSON.parse(readFileSync(`${repoRoot}/${path}`, "utf8"));
}

function schemaPropertyKeys(schema) {
  return new Set(Object.keys(schema.properties ?? {}));
}

function parseInterfaceFields(tsSource, interfaceName) {
  const block = tsSource.match(
    new RegExp(`export interface ${interfaceName} \\{([\\s\\S]*?)\\n\\}`)
  );
  assert.ok(block, `missing interface ${interfaceName}`);
  const fields = new Set();
  for (const line of block[1].split("\n")) {
    const m = line.match(/^\s+([a-z_][a-z0-9_]*)\??:/);
    if (m) fields.add(m[1]);
  }
  return fields;
}

test("generated EventRow matches events upsert schema", () => {
  const schema = readJson("schemas/events.upsert.schema.json");
  const generated = readFileSync(new URL("../src/lib/supabase-rows.ts", import.meta.url), "utf8");
  const rowFields = parseInterfaceFields(generated, "EventRow");
  assert.deepEqual(rowFields, schemaPropertyKeys(schema));
});

test("events.ts reads rows through generated EventRow type", () => {
  const eventsTs = readFileSync(new URL("../src/lib/events/index.ts", import.meta.url), "utf8");
  const mapper = readFileSync(new URL("../src/lib/events/map-event-row.ts", import.meta.url), "utf8");
  // Stored rows are the generated upsert shape plus columns the database derives.
  assert.match(mapper, /from "@\/lib\/supabase-rows"/);
  assert.match(mapper, /export type StoredEventRow = EventRow & \{/);
  assert.match(eventsTs, /StoredEventRow/);
  assert.match(eventsTs, /overrideTypes<StoredEventRow\[\], \{ merge: false \}>/);
  assert.match(eventsTs, /EventFilterCountRow/);
  assert.doesNotMatch(eventsTs, /interface EventRow/);
  assert.doesNotMatch(eventsTs, /as EventRow/);
});

test("generate:rows is in sync with schemas", () => {
  const before = readFileSync(new URL("../src/lib/supabase-rows.ts", import.meta.url), "utf8");
  const result = spawnSync(process.execPath, ["scripts/generate-row-types.mjs"], {
    cwd: repoRoot,
    encoding: "utf8",
  });
  assert.equal(result.status, 0, result.stderr || result.stdout);
  const after = readFileSync(new URL("../src/lib/supabase-rows.ts", import.meta.url), "utf8");
  assert.equal(after, before, "run npm run generate:rows and commit src/lib/supabase-rows.ts");
});
