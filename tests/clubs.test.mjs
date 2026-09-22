import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { importTsModule } from "./helpers/import-ts-module.mjs";

const { getClubs, searchClubs } = await importTsModule("src/lib/clubs.ts");
const { normalizeEventQuery, buildEventSearchText, matchesQuery } =
  await importTsModule("src/components/events/events-filters.ts");

test("every public scraped handle is searchable, including accounts outside the roster", () => {
  const activity = JSON.parse(readFileSync(new URL("../pipeline/data/account_activity.json", import.meta.url)));
  for (const handle of Object.keys(activity)) {
    if (handle === "highlander_opps") continue;
    assert.equal(searchClubs(`@${handle}`)[0]?.handle, handle);
  }
  assert.equal(searchClubs("@3d_at_ucr")[0]?.handle, "3d_at_ucr");
  assert.equal(searchClubs("  @ACM_UCR  ")[0]?.label, "ACM at UCR");
});

test("current event hosts supplement the roster and provide names for scraped handles", () => {
  const clubs = getClubs([
    { host: "Three Dimensional Club", hostHandle: "@3d_at_ucr", category: "arts" },
    { host: "New Campus Club", hostHandle: " @NEW_CAMPUS_CLUB ", category: "club" },
    { host: "New Campus Club", hostHandle: "new_campus_club", category: "club" },
    { host: "Different ACM display name", hostHandle: "acm_ucr", category: "academic" },
    { host: "Anonymous", hostHandle: "@highlander_opps", category: "club" },
    { host: "No account", category: "club" },
  ]);
  assert.equal(searchClubs("three dimensional", 8, clubs)[0]?.handle, "3d_at_ucr");
  assert.equal(searchClubs("new campus", 8, clubs)[0]?.handle, "new_campus_club");
  assert.equal(clubs.filter((club) => club.handle === "new_campus_club").length, 1);
  assert.equal(searchClubs("acm_ucr", 8, clubs)[0]?.label, "ACM at UCR");
  assert.equal(clubs.some((club) => club.handle === "highlander_opps"), false);
  assert.equal(clubs.some((club) => !club.handle), false);
});

test("an exact account match ranks ahead of prefix matches within the dropdown limit", () => {
  const clubs = Array.from({ length: 10 }, (_, i) => ({
    handle: `ucr_club_${i}`, label: `A club ${i}`, category: "club",
  }));
  clubs.push({ handle: "ucr_club", label: "Z club", category: "club" });
  assert.equal(searchClubs("@ucr_club", 8, clubs)[0].handle, "ucr_club");
  assert.equal(searchClubs("ucr_club", 8, clubs).length, 8);
});

test("handle queries match events even when their display names differ", () => {
  const searchText = buildEventSearchText({
    title: "Club meeting", description: "", host: "An alternate display name",
    hostHandle: "acm_ucr", location: "HUB", tags: [],
  });
  assert.equal(matchesQuery(searchText, normalizeEventQuery(" @ACM_UCR ")), true);
  assert.equal(matchesQuery(searchText, normalizeEventQuery("acm_ucr")), true);
});
