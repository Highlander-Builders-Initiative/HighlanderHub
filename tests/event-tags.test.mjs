import assert from "node:assert/strict";
import { test } from "node:test";
import { importTsModule } from "./helpers/import-ts-module.mjs";

const { eventTags } = await importTsModule("src/lib/category-colors.ts");

const labels = (event) =>
  eventTags({ contentKind: "student_event", hasFreeFood: false, rsvpRequired: false, ...event }).map(
    (tag) => tag.label
  );

test("tags run Deadline, category, Free food, RSVP", () => {
  assert.deepEqual(
    labels({ contentKind: "student_deadline", category: "career", hasFreeFood: true, rsvpRequired: true }),
    ["Deadline", "Career", "Free food", "RSVP"]
  );
});

test("a free-food category and the free-food flag make one tag", () => {
  assert.deepEqual(labels({ category: "free_food", hasFreeFood: true }), ["Free food"]);
  assert.deepEqual(labels({ category: "free_food" }), ["Free food"]);
  assert.deepEqual(labels({ category: "social", hasFreeFood: true }), ["Social", "Free food"]);
});

test("each tag names its kind, so the compact row can drop the category", () => {
  const kinds = eventTags({
    contentKind: "student_deadline",
    category: "career",
    hasFreeFood: true,
    rsvpRequired: true,
  }).map((tag) => tag.kind);
  assert.deepEqual(kinds, ["deadline", "category", "free_food", "rsvp"]);
});
