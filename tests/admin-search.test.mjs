import assert from "node:assert/strict";
import { test } from "node:test";
import { importTsModule } from "./helpers/import-ts-module.mjs";

const { matchesAdminQuery, ADMIN_EVENT_FILTERS } = await importTsModule("src/app/admin/types.ts");

function row(extra = {}) {
  return {
    id: "ig_usp_ucr_p4032631646209299905",
    title: "Bookmark Decorating",
    description: "",
    starts_at: "2026-12-02T19:00:00+00:00",
    sort_at: "2026-12-02T19:00:00+00:00",
    ends_at: null,
    all_day: false,
    location: "USP",
    host: "Undocumented Student Programs",
    host_handle: "usp_ucr",
    hosts: [],
    category: "arts",
    content_kind: "student_event",
    tags: [],
    source: "instagram",
    source_url: "https://www.instagram.com/p/Df2yR3OTdXB/",
    image_url: null,
    has_free_food: false,
    rsvp_required: false,
    rsvp_url: null,
    scraped_at: "2026-11-25T00:00:00+00:00",
    is_locked: false,
    created_at: "2026-11-25T00:00:00+00:00",
    updated_at: "2026-11-25T00:00:00+00:00",
    ...extra,
  };
}

test("a pasted Instagram link finds the listing made from that post", () => {
  const event = row();
  for (const link of [
    "https://www.instagram.com/p/Df2yR3OTdXB/",
    "instagram.com/p/Df2yR3OTdXB/?igsh=MTc4&img_index=2",
    "https://www.instagram.com/usp_ucr/p/Df2yR3OTdXB/",
    "https://www.instagram.com/reel/Df2yR3OTdXB",
  ]) {
    assert.equal(matchesAdminQuery(link, event), true, link);
  }
  assert.equal(matchesAdminQuery("https://www.instagram.com/p/DeID0iFyAX7/", event), false);
});

test("@handle matches host and co-host accounts exactly", () => {
  const event = row({ hosts: [{ host: "ASPB", host_handle: "aspb.ucr" }] });
  assert.equal(matchesAdminQuery("@usp_ucr", event), true);
  assert.equal(matchesAdminQuery("@ASPB.ucr", event), true);
  assert.equal(matchesAdminQuery("@usp", event), false);
});

test("plain text searches the listing's details", () => {
  const event = row();
  assert.equal(matchesAdminQuery("bookmark", event), true);
  assert.equal(matchesAdminQuery("usp", event), true);
  assert.equal(matchesAdminQuery("  ", event), true);
  assert.equal(matchesAdminQuery("career fair", event), false);
});

test("quick filters", () => {
  const test = (key, event) => ADMIN_EVENT_FILTERS.find((f) => f.key === key).test(event);
  assert.equal(test("no_end", row()), true);
  assert.equal(test("no_end", row({ content_kind: "student_deadline" })), false);
  assert.equal(test("no_end", row({ all_day: true })), false);
  assert.equal(test("hidden", row({ content_kind: "fundraiser" })), true);
  assert.equal(test("hidden", row()), false);
  assert.equal(test("no_flyer", row({ image_url: "not a url" })), true);
  assert.equal(test("locked", row({ is_locked: true })), true);
});
