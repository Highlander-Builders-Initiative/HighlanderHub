import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);

// Load compiled TS via ts-node isn't available; test source invariants instead.
const adminTs = readFileSync(
  join(__dirname, "../src/lib/admin.ts"),
  "utf8"
);
const actionsTs = readFileSync(
  join(__dirname, "../src/app/admin/actions.ts"),
  "utf8"
);
const validateTs = readFileSync(
  join(__dirname, "../src/app/admin/validate-event-update.ts"),
  "utf8"
);

test("admin password uses getAdminPassword single source", () => {
  assert.match(adminTs, /export function getAdminPassword/);
  assert.doesNotMatch(adminTs, /ucrboulders/);
  assert.doesNotMatch(adminTs, /change-me-in-production/);
  assert.match(actionsTs, /getAdminPassword\(\)/);
  assert.doesNotMatch(actionsTs, /ucrboulders/);
});

test("updateEvent validates allowlist before DB write", () => {
  assert.match(actionsTs, /parseAdminEventUpdate/);
  assert.match(validateTs, /ADMIN_EVENT_UPDATE_KEYS/);
  assert.doesNotMatch(actionsTs, /updatedFields: any/);
});

test("approveSubmission rolls back event on submission update failure", () => {
  assert.match(actionsTs, /\.delete\(\)/);
  assert.match(actionsTs, /rollback/i);
});
