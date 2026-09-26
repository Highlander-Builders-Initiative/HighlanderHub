import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { test } from "node:test";
import { promisify } from "node:util";

const run = promisify(execFile);

test("parallel TypeScript imports cannot overwrite another worker's modules", async () => {
  const script = `
    import assert from "node:assert/strict";
    import ts from "typescript";
    import { importTsModule } from "./tests/helpers/import-ts-module.mjs";
    const paths = [];
    const writeFile = ts.sys.writeFile;
    ts.sys.writeFile = (path, ...args) => {
      paths.push(path);
      return writeFile(path, ...args);
    };
    const filters = await importTsModule("src/components/events/events-filters.ts");
    const event = await importTsModule("src/types/event.ts");
    assert.equal(filters.coerceFeedView("compact"), "compact");
    assert.ok(event.EVENT_CATEGORIES.length > 0);
    console.log(JSON.stringify(paths));
  `;
  const workers = await Promise.all(Array.from({ length: 2 }, () =>
    run(process.execPath, ["--input-type=module", "-e", script], {
      cwd: new URL("../", import.meta.url),
    })
  ));
  const [first, second] = workers.map(({ stdout }) => JSON.parse(stdout));
  assert.ok(first.length > 0);
  assert.ok(second.length > 0);
  assert.deepEqual(first.filter((path) => second.includes(path)), []);
});
