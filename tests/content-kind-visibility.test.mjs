import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), "utf8");

test("public event reads filter to PUBLIC_CONTENT_KINDS", () => {
  const data = read("src/lib/events/index.ts");

  assert.match(data, /from "@\/lib\/events\/content-kind"/);
  assert.match(data, /PUBLIC_CONTENT_KINDS/);

  // Browse, counts, calendar, and summary all constrain content_kind. Each
  // public read adds `.in("content_kind", PUBLIC_CONTENT_KINDS)`; there are
  // eight such reads (3 summary counts, 2 page branches, filter counts,
  // sitemap, calendar).
  const filters = data.match(/\.in\("content_kind", PUBLIC_CONTENT_KINDS\)/g) ?? [];
  assert.ok(
    filters.length >= 8,
    `expected >= 8 content_kind filters, found ${filters.length}`
  );
});

test("event detail by id is intentionally not content-kind filtered", () => {
  const data = read("src/lib/events/index.ts");
  // Deep links to any kind must still resolve (and admins reach all kinds).
  assert.match(data, /NOT content-kind filtered/);
});

test("row mapping and CampusEvent carry contentKind", () => {
  const mapRow = read("src/lib/events/map-event-row.ts");
  const eventType = read("src/types/event.ts");

  assert.match(mapRow, /contentKind: r\.content_kind/);
  assert.match(eventType, /contentKind: EventContentKind/);
  assert.match(eventType, /SUBMIT_CONTENT_KINDS/);
});

test("submit form exposes a required Listing type control", () => {
  const form = read("src/components/forms/submit/SubmitForm.tsx");
  const types = read("src/types/event.ts");

  assert.match(form, /label="Listing type"/);
  assert.match(form, /name="content_kind"/);
  assert.match(form, /options=\{SUBMIT_CONTENT_KINDS\}/);
  assert.match(types, /SUBMIT_CONTENT_KINDS/);
  // No fundraiser option on the public form.
  assert.doesNotMatch(types, /value: "fundraiser"/);
});

test("admin can edit content_kind across all four kinds", () => {
  const types = read("src/app/admin/types.ts");
  const validate = read("src/app/admin/validate-event-update.ts");
  const hook = read("src/app/admin/useAdminEventEdit.ts");
  const drawer = read("src/app/admin/AdminEventEditDrawer.tsx");
  const actions = read("src/app/admin/actions.ts");

  assert.match(types, /"content_kind"/);
  assert.match(types, /content_kind: EventContentKind/);
  assert.match(validate, /EVENT_CONTENT_KINDS/);
  assert.match(validate, /content_kind is invalid\./);
  assert.match(hook, /contentKind: event\.content_kind/);
  assert.match(hook, /content_kind: form\.contentKind/);
  assert.match(drawer, /setField\("contentKind"/);
  assert.match(drawer, /value="fundraiser"/);
  assert.match(drawer, /value="other"/);
  // Approval copies the submitted kind into the events row.
  assert.match(actions, /content_kind: submission\.content_kind/);
});

test("deadlines render deadline-oriented affordances", () => {
  const card = read("src/components/events/EventCard.tsx");
  const timeColumn = read("src/components/events/EventListRowTimeColumn.tsx");
  const detail = read("src/app/events/[id]/page.tsx");
  const a11y = read("src/lib/events/a11y.ts");

  assert.match(timeColumn, /isDeadlineKind/);
  assert.match(timeColumn, />\s*Due\s*</);
  assert.match(card, /Deadline/);
  assert.match(detail, /Add reminder/);
  assert.match(a11y, /Deadline:/);
});

test("category rail is labeled Topics, not Browse", () => {
  const leftRail = read("src/components/events/EventsLeftRail.tsx");
  const sheet = read("src/components/events/EventsMobileFilterSheet.tsx");

  assert.match(leftRail, />Topics</);
  assert.match(sheet, />Topics</);
  assert.doesNotMatch(leftRail, />Browse</);
  assert.doesNotMatch(sheet, />Browse</);
});
