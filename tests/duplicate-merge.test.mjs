import assert from "node:assert/strict";
import { test } from "node:test";
import { importTsModule } from "./helpers/import-ts-module.mjs";

const { duplicateMergeChanges } = await importTsModule("src/app/admin/duplicate-merge.ts");

function listing(id, extra = {}) {
  return {
    id,
    title: "USM's 13th Annual Conference",
    description: "",
    starts_at: "2026-11-06T18:00:00+00:00",
    ends_at: null,
    all_day: false,
    location: "University of Southern California",
    host: "United Sikh Movement",
    host_handle: "unitedsikhmovement",
    hosts: [],
    category: "community",
    content_kind: "student_event",
    tags: [],
    source: "instagram",
    source_url: null,
    image_url: null,
    has_free_food: false,
    rsvp_required: false,
    rsvp_url: null,
    scraped_at: "2026-09-25T00:00:00+00:00",
    is_locked: false,
    created_at: "2026-09-25T00:00:00+00:00",
    updated_at: "2026-09-25T00:00:00+00:00",
    ...extra,
  };
}

test("the kept listing keeps what identifies it and fills only what it lacks", () => {
  const kept = listing("ig_usm", { image_url: "https://example.com/usm.jpg" });
  const repost = listing("ig_ssa", {
    title: "USM Conference",
    location: "SoCal",
    host: "Sikh Student Association",
    host_handle: "ssa_ucr",
    image_url: "https://example.com/ssa.jpg",
    ends_at: "2026-11-06T22:00:00+00:00",
    has_free_food: true,
    rsvp_required: true,
    rsvp_url: "https://forms.example.com/ssa",
  });
  const { changes, additions } = duplicateMergeChanges(kept, repost);
  assert.deepEqual(changes, {
    has_free_food: true,
    hosts: [
      { host: "United Sikh Movement", host_handle: "unitedsikhmovement" },
      { host: "Sikh Student Association", host_handle: "ssa_ucr" },
    ],
    ends_at: "2026-11-06T22:00:00+00:00",
  });
  assert.deepEqual(additions, ["free food", "co-host @ssa_ucr", "end time"]);
});

test("the same host's signup carries over; a partner's does not", () => {
  const kept = listing("ig_a");
  const signup = { rsvp_required: true, rsvp_url: "https://forms.example.com/usm" };
  assert.deepEqual(duplicateMergeChanges(kept, listing("ig_b", signup)).changes, signup);
  const partner = listing("ig_c", { ...signup, host: "Partner", host_handle: "partner" });
  assert.equal("rsvp_url" in duplicateMergeChanges(kept, partner).changes, false);
});

test("a vague venue takes the other listing's named one", () => {
  for (const location of ["", "UC Riverside", "Room TBA", "TBD"]) {
    const { changes, additions } = duplicateMergeChanges(
      listing("ig_a", { location }),
      listing("ig_b", { location: "HUB 302" })
    );
    assert.equal(changes.location, "HUB 302", location);
    assert.deepEqual(additions, ["venue (HUB 302)"]);
  }
  assert.deepEqual(
    duplicateMergeChanges(listing("ig_a", { location: "TBA" }), listing("ig_b", { location: "UCR" })).changes,
    {}
  );
});

test("an end on another day or from a date-only listing is not a time", () => {
  const kept = listing("ig_a");
  assert.deepEqual(
    duplicateMergeChanges(kept, listing("ig_b", {
      starts_at: "2026-11-07T18:00:00+00:00", ends_at: "2026-11-07T20:00:00+00:00",
    })).changes,
    {}
  );
  assert.deepEqual(
    duplicateMergeChanges(kept, listing("ig_c", {
      starts_at: "2026-11-06T08:00:00+00:00", ends_at: "2026-11-07T08:00:00+00:00", all_day: true,
    })).changes,
    {}
  );
});

test("anonymous accounts never become co-hosts, and identical listings add nothing", () => {
  const kept = listing("ig_a");
  const anonymous = listing("ig_b", { host: "Opportunities", host_handle: "highlander_opps" });
  assert.deepEqual(duplicateMergeChanges(kept, anonymous), { changes: {}, additions: [] });
  assert.deepEqual(duplicateMergeChanges(kept, listing("ig_c")), { changes: {}, additions: [] });
});
