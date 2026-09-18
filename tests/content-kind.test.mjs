import assert from "node:assert/strict";
import { test } from "node:test";
import { importTsModule } from "./helpers/import-ts-module.mjs";

const {
  PUBLIC_CONTENT_KINDS,
  isContentKind,
  isPublicContentKind,
  coerceContentKind,
  isDeadlineKind,
} = await importTsModule("src/lib/events/content-kind.ts");

test("public content kinds exclude fundraiser and other", () => {
  assert.deepEqual([...PUBLIC_CONTENT_KINDS].sort(), [
    "student_deadline",
    "student_event",
  ]);
  assert.equal(isPublicContentKind("student_event"), true);
  assert.equal(isPublicContentKind("student_deadline"), true);
  assert.equal(isPublicContentKind("fundraiser"), false);
  assert.equal(isPublicContentKind("other"), false);
  assert.equal(isPublicContentKind("nonsense"), false);
});

test("isContentKind recognizes all four kinds", () => {
  for (const kind of [
    "student_event",
    "student_deadline",
    "fundraiser",
    "other",
  ]) {
    assert.equal(isContentKind(kind), true);
  }
  assert.equal(isContentKind("nope"), false);
  assert.equal(isContentKind(undefined), false);
});

test("coercion falls back to safe defaults for unknown input", () => {
  assert.equal(coerceContentKind("fundraiser"), "fundraiser");
  assert.equal(coerceContentKind("nonsense"), "student_event");
  assert.equal(coerceContentKind(undefined), "student_event");
  assert.equal(coerceContentKind("nonsense", "other"), "other");
});

test("isDeadlineKind only matches student_deadline", () => {
  assert.equal(isDeadlineKind("student_deadline"), true);
  assert.equal(isDeadlineKind("student_event"), false);
  assert.equal(isDeadlineKind(undefined), false);
});
