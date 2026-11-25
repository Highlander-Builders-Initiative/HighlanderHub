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
    category: "other",
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

const { defaultMergeTakes, mergeFieldOptions } = await importTsModule("src/app/admin/duplicate-merge.ts");

test("a choice is offered only where the other listing has a different usable detail", () => {
  const kept = listing("ig_single", { location: "USP" });
  const quarterly = listing("ig_quarterly", {
    location: "Costo Hall 224",
    ends_at: "2026-11-06T20:00:00+00:00",
    image_url: "https://example.com/q.jpg",
  });
  assert.deepEqual(mergeFieldOptions(kept, quarterly), ["location", "ends_at", "image_url"]);
  // By default the other listing only fills gaps: USP is a named venue.
  assert.deepEqual(defaultMergeTakes(kept, quarterly), ["ends_at", "image_url"]);
  assert.deepEqual(mergeFieldOptions(kept, listing("ig_same", { location: " usp " })), []);
});

test("the admin's choices decide venue, end time, flyer and RSVP link", () => {
  const kept = listing("ig_single", {
    location: "USP",
    ends_at: "2026-11-06T19:00:00+00:00",
    image_url: "https://example.com/kept.jpg",
  });
  const other = listing("ig_other", {
    location: "Costo Hall 224",
    ends_at: "2026-11-06T20:00:00+00:00",
    image_url: "https://example.com/other.jpg",
    has_free_food: true,
  });
  assert.deepEqual(duplicateMergeChanges(kept, other, ["location", "ends_at"]), {
    changes: {
      has_free_food: true,
      ends_at: "2026-11-06T20:00:00+00:00",
      location: "Costo Hall 224",
      is_locked: true,
    },
    additions: ["free food", "end time", "venue (Costo Hall 224)"],
  });
  // Declining every choice keeps the kept listing's details; free food still carries.
  assert.deepEqual(duplicateMergeChanges(kept, other, []).changes, { has_free_food: true });
});

test("a choice the pair can't support is ignored", () => {
  const kept = listing("ig_a");
  const nextDay = listing("ig_b", {
    starts_at: "2026-11-07T18:00:00+00:00",
    ends_at: "2026-11-07T20:00:00+00:00",
  });
  assert.deepEqual(duplicateMergeChanges(kept, nextDay, ["ends_at", "image_url"]).changes, {});
});

test("taking a partner's RSVP link brings its signup requirement with it", () => {
  const kept = listing("ig_a");
  const partner = listing("ig_c", {
    host: "Partner",
    host_handle: "partner",
    rsvp_required: true,
    rsvp_url: "https://forms.example.com/partner",
  });
  assert.equal(defaultMergeTakes(kept, partner).includes("rsvp_url"), false);
  const { changes } = duplicateMergeChanges(kept, partner, ["rsvp_url"]);
  assert.equal(changes.rsvp_url, "https://forms.example.com/partner");
  assert.equal(changes.rsvp_required, true);
});

test("a date-only listing takes the other's time of day; another date or time is a choice", () => {
  const teaser = listing("ig_teaser", {
    starts_at: "2026-11-06T08:00:00+00:00",
    ends_at: "2026-11-07T08:00:00+00:00",
    all_day: true,
  });
  const timed = listing("ig_timed", { ends_at: "2026-11-06T20:00:00+00:00" });
  assert.deepEqual(defaultMergeTakes(teaser, timed), ["starts_at"]);
  assert.deepEqual(duplicateMergeChanges(teaser, timed), {
    changes: {
      starts_at: "2026-11-06T18:00:00+00:00",
      all_day: false,
      ends_at: "2026-11-06T20:00:00+00:00",
      is_locked: true,
    },
    additions: ["date and time"],
  });

  // A rescheduled event: nothing moves unless the admin says so.
  const kept = listing("ig_kept", { ends_at: "2026-11-06T20:00:00+00:00" });
  const moved = listing("ig_moved", { starts_at: "2026-11-13T19:00:00+00:00" });
  assert.deepEqual(mergeFieldOptions(kept, moved), ["starts_at"]);
  assert.deepEqual(duplicateMergeChanges(kept, moved).changes, {});
  // The replaced time's end goes with it, even when "end time" was also ticked.
  assert.deepEqual(duplicateMergeChanges(kept, moved, ["starts_at", "ends_at"]).changes, {
    starts_at: "2026-11-13T19:00:00+00:00",
    all_day: false,
    ends_at: null,
    is_locked: true,
  });
  assert.deepEqual(mergeFieldOptions(kept, listing("ig_same")), []);
});

test("whether a flyer is a video's cover frame travels with the flyer", () => {
  const reel = listing("ig_reel", { image_url: "https://example.com/cover.jpg", image_is_video: true });
  const flyer = listing("ig_flyer", { image_url: "https://example.com/flyer.jpg" });
  // A still flyer replaces a video's cover by default, as reconciliation does.
  assert.deepEqual(defaultMergeTakes(reel, flyer), ["image_url"]);
  assert.deepEqual(duplicateMergeChanges(reel, flyer).changes, {
    image_url: "https://example.com/flyer.jpg",
    image_is_video: null,
  });
  assert.deepEqual(defaultMergeTakes(flyer, reel), []);
  assert.deepEqual(duplicateMergeChanges(flyer, reel, ["image_url"]).changes, {
    image_url: "https://example.com/cover.jpg",
    image_is_video: true,
    is_locked: true,
  });
  // Unchanged, the flag is not sent.
  const other = listing("ig_other", { image_url: "https://example.com/other.jpg" });
  assert.deepEqual(duplicateMergeChanges(flyer, other, ["image_url"]).changes, {
    image_url: "https://example.com/other.jpg",
    is_locked: true,
  });
});

const { mergeLocksListing } = await importTsModule("src/app/admin/duplicate-merge.ts");

test("a merge locks the kept listing only where the next import would undo the admin's choice", () => {
  const kept = listing("ig_kept", { location: "USP", image_url: "https://example.com/kept.jpg" });
  const other = listing("ig_other", {
    location: "Costo Hall 224",
    ends_at: "2026-11-06T20:00:00+00:00",
    image_url: "https://example.com/other.jpg",
  });
  // The defaults are what an import does anyway: the listing keeps following its post.
  assert.deepEqual(defaultMergeTakes(kept, other), ["ends_at"]);
  assert.equal(mergeLocksListing(kept, other), false);
  assert.equal("is_locked" in duplicateMergeChanges(kept, other).changes, false);
  // Taking a detail the kept listing already has, or declining one it lacks.
  assert.equal(mergeLocksListing(kept, other, ["ends_at", "image_url"]), true);
  assert.equal(mergeLocksListing(kept, other, ["ends_at", "location"]), true);
  assert.equal(mergeLocksListing(kept, other, []), true);
  assert.equal(duplicateMergeChanges(kept, other, []).changes.is_locked, true);
  // A partner's signup link is the admin's call.
  const partner = listing("ig_partner", {
    host: "Partner", host_handle: "partner", rsvp_url: "https://forms.example.com/p",
  });
  assert.equal(mergeLocksListing(listing("ig_a"), partner, ["rsvp_url"]), true);
  // A choice that is not on offer changes nothing, and a locked listing stays as it is.
  assert.equal(mergeLocksListing(kept, listing("ig_same", { location: "USP" }), ["location"]), false);
  assert.equal(mergeLocksListing({ ...kept, is_locked: true }, other, []), false);
});
