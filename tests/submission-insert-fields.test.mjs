import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { importTsModule } from "./helpers/import-ts-module.mjs";

const { parseSubmissionInsert } = await importTsModule("src/lib/submissions.ts");

const VALID_SUBMISSION = {
  title: "Taco night",
  description: "",
  starts_at: "2027-01-01T00:00:00.000Z",
  ends_at: null,
  location: "HUB",
  host: "ACM at UCR",
  category: "free_food",
  tags: [" free food ", ""],
  source_url: " https://events.ucr.edu/taco-night ",
  image_url: null,
  is_free: true,
  rsvp_required: false,
  rsvp_url: null,
  submitter_name: " Abe ",
  submitter_email: " abe@ucr.edu ",
  submitter_org: "",
};

function parseValid(payload = {}) {
  const result = parseSubmissionInsert({ ...VALID_SUBMISSION, ...payload });
  assert.equal(result.ok, true, result.error);
  return result.row;
}

test("submission parser returns a canonical public insert row", () => {
  const row = parseValid();

  assert.deepEqual(Object.keys(row).sort(), [
    "category",
    "description",
    "ends_at",
    "host",
    "image_url",
    "is_free",
    "location",
    "rsvp_required",
    "rsvp_url",
    "source_url",
    "starts_at",
    "submitter_email",
    "submitter_name",
    "submitter_org",
    "tags",
    "title",
  ]);
  assert.equal(row.title, "Taco night");
  assert.equal(row.starts_at, "2027-01-01T00:00:00.000Z");
  assert.deepEqual(row.tags, ["free food"]);
  assert.equal(row.source_url, "https://events.ucr.edu/taco-night");
  assert.equal(row.submitter_name, "Abe");
  assert.equal(row.submitter_email, "abe@ucr.edu");
  assert.equal(row.submitter_org, null);
});

test("submission parser rejects moderation and identity columns", () => {
  const result = parseSubmissionInsert({
    ...VALID_SUBMISSION,
    status: "approved",
    reviewed_at: "2026-01-01T00:00:00Z",
    review_notes: "self approved",
    id: "00000000-0000-4000-8000-000000000000",
    created_at: "2000-01-01T00:00:00Z",
  });

  assert.deepEqual(result, {
    ok: false,
    error: "Disallowed fields: status, reviewed_at, review_notes, id, created_at",
  });
});

test("submission parser rejects malformed field values before insert", () => {
  assert.deepEqual(parseSubmissionInsert({ ...VALID_SUBMISSION, title: "A" }), {
    ok: false,
    error: "title must be 3 to 200 characters.",
  });
  assert.deepEqual(
    parseSubmissionInsert({
      ...VALID_SUBMISSION,
      source_url: "javascript:alert(1)",
    }),
    { ok: false, error: "source_url must be an http(s) URL." }
  );
  assert.deepEqual(
    parseSubmissionInsert({ ...VALID_SUBMISSION, tags: "free food" }),
    { ok: false, error: "tags must be an array of strings." }
  );
});

test("submission route inserts the parsed row, not the raw body", () => {
  const source = readFileSync(
    new URL("../src/app/api/submissions/route.ts", import.meta.url),
    "utf8"
  );

  assert.match(source, /const parsed = parseSubmissionInsert\(body\);/);
  assert.match(source, /const row = parsed\.row;/);
  assert.match(source, /\.insert\(row\)/);
  assert.match(source, /notifyNewSubmission\(row\)/);
  assert.doesNotMatch(source, /\.insert\(body\)/);
});
