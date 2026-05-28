import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { importTsModule } from "./helpers/import-ts-module.mjs";

const { pickSubmissionFields } = await importTsModule("src/lib/submissions.ts");

test("submission insert keeps only the public form fields", () => {
  const row = pickSubmissionFields({
    title: "Taco night",
    submitter_name: "Abe",
    submitter_email: "abe@ucr.edu",
    starts_at: "2027-01-01T00:00:00Z",
    tags: ["free food"],
    is_free: true,
  });

  assert.deepEqual(Object.keys(row).sort(), [
    "is_free",
    "starts_at",
    "submitter_email",
    "submitter_name",
    "tags",
    "title",
  ]);
});

test("submission insert strips moderation and identity columns", () => {
  const row = pickSubmissionFields({
    title: "Taco night",
    submitter_name: "Abe",
    submitter_email: "abe@ucr.edu",
    starts_at: "2027-01-01T00:00:00Z",
    status: "approved",
    reviewed_at: "2026-01-01T00:00:00Z",
    review_notes: "self approved",
    id: "00000000-0000-4000-8000-000000000000",
    created_at: "2000-01-01T00:00:00Z",
  });

  for (const blocked of [
    "status",
    "reviewed_at",
    "review_notes",
    "id",
    "created_at",
  ]) {
    assert.equal(blocked in row, false, `${blocked} should be dropped`);
  }
});

test("submission route inserts the sanitized row, not the raw body", () => {
  const source = readFileSync(
    new URL("../src/app/api/submissions/route.ts", import.meta.url),
    "utf8"
  );

  assert.match(source, /const row = pickSubmissionFields\(body\);/);
  assert.match(source, /\.insert\(row\)/);
  assert.match(source, /notifyNewSubmission\(row\)/);
  assert.doesNotMatch(source, /\.insert\(body\)/);
});
