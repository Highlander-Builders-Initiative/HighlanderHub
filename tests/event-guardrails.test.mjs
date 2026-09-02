import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { test } from "node:test";

const sourceFile = (path) => new URL(`../${path}`, import.meta.url);
const read = (path) => readFileSync(sourceFile(path), "utf8");

test("event validation helpers reject unsafe URLs and use Pacific wall-clock times", () => {
  const result = spawnSync(
    process.execPath,
    [
      "--input-type=module",
      "--eval",
      `
        import { importTsModule } from "./tests/helpers/import-ts-module.mjs";
        const validation = await importTsModule("src/lib/events/validation.ts");
        const ok = validation.validateEventTimes("2026-05-20T12:00", "2026-05-20T12:00");
        const backwards = validation.validateEventTimes("2026-05-20T12:00", "2026-05-20T11:59");
        const badStart = validation.validateEventTimes("not a date", "");
        const pacific = validation.validateEventTimes("2026-05-20T23:30", "");
        console.log(JSON.stringify({
          httpsUrl: validation.normalizeHttpUrl(" https://events.ucr.edu/foo "),
          httpUrl: validation.normalizeHttpUrl("http://example.com/a"),
          javascriptUrl: validation.normalizeHttpUrl("javascript:alert(1)"),
          mailtoUrl: validation.normalizeHttpUrl("mailto:club@example.com"),
          relativeUrl: validation.normalizeHttpUrl("/events/1"),
          okError: ok.error,
          okStartsAt: ok.startsAt,
          okEndsAt: ok.endsAt,
          backwardsField: backwards.field,
          backwardsError: backwards.error,
          badStartField: badStart.field,
          pacificStartsAt: pacific.startsAt,
        }));
      `,
    ],
    {
      cwd: process.cwd(),
      env: { ...process.env, TZ: "Asia/Tokyo" },
      encoding: "utf8",
    }
  );

  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(JSON.parse(result.stdout.trim()), {
    httpsUrl: "https://events.ucr.edu/foo",
    httpUrl: "http://example.com/a",
    javascriptUrl: null,
    mailtoUrl: null,
    relativeUrl: null,
    okError: null,
    okStartsAt: "2026-05-20T19:00:00.000Z",
    okEndsAt: "2026-05-20T19:00:00.000Z",
    backwardsField: "ends_at",
    backwardsError: "End time must be at or after the start time.",
    badStartField: "starts_at",
    pacificStartsAt: "2026-05-21T06:30:00.000Z",
  });
});

test("submission validation requires RSVP URL from form data", () => {
  const result = spawnSync(
    process.execPath,
    [
      "--input-type=module",
      "--eval",
      `
        import { importTsModule } from "./tests/helpers/import-ts-module.mjs";
        const submission = await importTsModule("src/components/forms/submit/submit-validation.ts");
        const submissions = await importTsModule("src/lib/submissions.ts");
        const form = new FormData();
        form.set("title", "Club night");
        form.set("starts_at", "2026-05-20T18:00");
        form.set("location", "HUB");
        form.set("host", "ACM");
        form.set("submitter_name", "Taylor");
        form.set("submitter_email", "taylor@example.com");
        form.set("rsvp_required", "on");
        const missing = submission.validateSubmissionFields(form);
        form.set("rsvp_url", "https://events.ucr.edu/rsvp");
        const valid = submission.validateSubmissionFields(form);
        form.set("rsvp_url", "javascript:alert(1)");
        const invalid = submission.validateSubmissionFields(form);
        console.log(JSON.stringify({
          missing,
          valid,
          invalid,
          row: submissions.buildSubmissionRow(form, "2026-05-21T01:00:00.000Z", null, null)
        }));
      `,
    ],
    {
      cwd: process.cwd(),
      env: { ...process.env, TZ: "UTC" },
      encoding: "utf8",
    }
  );

  assert.equal(result.status, 0, result.stderr);
  const parsed = JSON.parse(result.stdout.trim());
  assert.deepEqual(parsed.missing, { rsvp_url: "This field is required." });
  assert.deepEqual(parsed.valid, {});
  assert.deepEqual(parsed.invalid, { rsvp_url: "Use an http(s) URL." });
  assert.equal(parsed.row.rsvp_required, true);
});

test("submission Discord alert avoids submitter contact details", () => {
  const result = spawnSync(
    process.execPath,
    [
      "--input-type=module",
      "--eval",
      `
        import { importTsModule } from "./tests/helpers/import-ts-module.mjs";
        const discord = await importTsModule("src/lib/discord.ts");
        const message = discord.buildSubmissionDiscordMessage({
          title: "Club night",
          starts_at: "2026-05-21T01:00:00.000Z",
          location: "HUB 302",
          host: "ACM at UCR",
          submitter_name: "Private Person",
          submitter_email: "private@example.com"
        });
        console.log(JSON.stringify({ message }));
      `,
    ],
    {
      cwd: process.cwd(),
      env: { ...process.env, TZ: "UTC" },
      encoding: "utf8",
    }
  );

  assert.equal(result.status, 0, result.stderr);
  const { message } = JSON.parse(result.stdout.trim());
  assert.match(message, /New Highlander Hub submission needs review/);
  assert.match(message, /Club night/);
  assert.match(message, /Hosted by ACM at UCR/);
  assert.match(message, /Review: \/admin/);
  assert.doesNotMatch(message, /Private Person/);
  assert.doesNotMatch(message, /private@example\.com/);
});

test("submission and detail surfaces use shared URL and time guards", () => {
  const form = read("src/components/forms/submit/SubmitForm.tsx");
  const validation = read("src/components/forms/submit/submit-validation.ts");
  const submissions = read("src/lib/submissions.ts");
  const detail = read("src/app/events/[id]/page.tsx");
  const actions = read("src/lib/events/actions.ts");
  const events = read("src/lib/events/index.ts");
  const mapRow = read("src/lib/events/map-event-row.ts");
  const adminEdit = read("src/app/admin/useAdminEventEdit.ts");

  assert.match(validation, /normalizeHttpUrl/);
  assert.match(submissions, /buildSubmissionRow/);
  assert.match(submissions, /parseSubmissionInsert/);
  assert.match(form, /validateEventTimes/);
  assert.match(form, /fieldErrors\.ends_at/);
  assert.match(validation, /Use an http\(s\) URL\./);
  assert.match(detail, /safeRsvpUrl/);
  assert.match(detail, /safeSourceUrl/);
  assert.match(actions, /normalizeHttpUrl\(event\.rsvpUrl\)/);
  assert.match(actions, /normalizeHttpUrl\(event\.sourceUrl\)/);
  assert.match(mapRow, /normalizeHttpUrl\(r\.source_url\)/);
  assert.match(mapRow, /normalizeHttpUrl\(r\.image_url\)/);
  assert.match(mapRow, /normalizeHttpUrl\(r\.rsvp_url\)/);
  assert.match(events, /eventRowToCampusEvent/);
  assert.match(adminEdit, /validateEventTimes/);
  assert.match(adminEdit, /formatPacificDateTimeInput/);
});

test("database migration adds Discord notification ledger for free food", () => {
  const migrationsDir = sourceFile("supabase/migrations");
  const migrationName = readdirSync(migrationsDir).find((name) =>
    name.includes("discord_notifications")
  );
  const stableKeyMigrationName = readdirSync(migrationsDir).find((name) =>
    name.includes("discord_notification_stable_keys")
  );

  assert.ok(migrationName, "missing Discord notification ledger migration");
  assert.ok(stableKeyMigrationName, "missing Discord stable key migration");
  const migration = read(`supabase/migrations/${migrationName}`);
  const stableKeyMigration = read(
    `supabase/migrations/${stableKeyMigrationName}`
  );

  assert.match(migration, /create table if not exists discord_notifications/i);
  assert.match(migration, /primary key \(event_id, kind\)/i);
  assert.match(migration, /kind in \('free_food'\)/i);
  assert.match(migration, /enable row level security/i);
  assert.match(migration, /where category = 'free_food'/i);
  assert.match(stableKeyMigration, /notification_key text/i);
  assert.match(stableKeyMigration, /drop constraint if exists discord_notifications_event_id_fkey/i);
  assert.match(stableKeyMigration, /discord_notifications_kind_notification_key_idx/i);
  assert.match(stableKeyMigration, /has_free_food or category = 'free_food'/i);
});

test("event detail lookup is request-level cached", () => {
  const source = read("src/lib/events/index.ts");

  assert.match(source, /import \{ cache \} from "react"/);
  assert.match(source, /const getEventByIdUncached = cache\(/);
});

test("public event reads are Data-Cached and busted on admin writes", () => {
  const data = read("src/lib/events/index.ts");
  const adminActions = read("src/app/admin/actions.ts");

  // The Supabase client is hardwired to no-store, so the reads are wrapped in
  // the Data Cache to spare repeat visits the round-trips. (Static/edge ISR is
  // not possible here: no-store bars prerender, so the routes stay dynamic.)
  assert.match(data, /import \{ unstable_cache \} from "next\/cache"/);
  assert.match(data, /export const EVENTS_CACHE_TAG = "events"/);
  assert.match(data, /function cachePublicRead/);
  assert.match(data, /unstable_cache\(operation, keyParts, eventsCacheOptions\)/);
  assert.match(data, /e2eFixturesEnabled\(\) \? operation\(\.\.\.args\) : cached\(\.\.\.args\)/);
  for (const name of [
    "getEventsSummary",
    "getEventsPage",
    "getEventFilterCountSource",
    "getSitemapEvents",
    "getCalendarEvents",
    "getEventById",
  ]) {
    assert.match(
      data,
      new RegExp(`export const ${name} = cachePublicRead\\(`),
      `${name} must read through the Data Cache`
    );
  }

  // Admin mutations bust the cache immediately rather than waiting for TTL.
  assert.match(adminActions, /import \{ EVENTS_CACHE_TAG \} from "@\/lib\/events"/);
  assert.match(adminActions, /revalidateTag\(EVENTS_CACHE_TAG, "max"\)/);
});

test("e2e fixtures stay outside the main event reader", () => {
  const events = read("src/lib/events/index.ts");

  assert.ok(
    existsSync(sourceFile("src/lib/events/fixtures.ts")),
    "missing fixture module"
  );
  assert.match(events, /from "\.\/fixtures"/);
  assert.doesNotMatch(events, /HIGHLANDERHUB_E2E_FIXTURES/);
  assert.doesNotMatch(events, /E2E Test: Highlander Hub Showcase/);
});

test("Pacific datetime-local values round-trip regardless of runtime TZ", () => {
  const result = spawnSync(
    process.execPath,
    [
      "--input-type=module",
      "--eval",
      `
        import { importTsModule } from "./tests/helpers/import-ts-module.mjs";
        const dates = await importTsModule("src/lib/dates.ts");
        const local = "2026-05-20T23:30";
        const iso = dates.parsePacificDateTimeInput(local);
        const back = dates.formatPacificDateTimeInput(iso);
        console.log(JSON.stringify({ iso, back }));
      `,
    ],
    {
      cwd: process.cwd(),
      env: { ...process.env, TZ: "Asia/Tokyo" },
      encoding: "utf8",
    }
  );

  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(JSON.parse(result.stdout.trim()), {
    iso: "2026-05-21T06:30:00.000Z",
    back: "2026-05-20T23:30",
  });
});

test("database migration adds URL scheme and end-time guardrails", () => {
  const migrationsDir = sourceFile("supabase/migrations");
  const migrationName = readdirSync(migrationsDir).find((name) =>
    name.includes("event_url_time_guardrails")
  );

  assert.ok(migrationName, "missing event URL/time guardrail migration");
  const migrationPath = `supabase/migrations/${migrationName}`;
  assert.equal(existsSync(sourceFile(migrationPath)), true);

  const migration = read(migrationPath);
  assert.match(migration, /events_ends_at_after_starts_at[\s\S]*ends_at is null or ends_at >= starts_at[\s\S]*not valid/i);
  assert.match(migration, /submissions_ends_at_after_starts_at[\s\S]*ends_at is null or ends_at >= starts_at[\s\S]*not valid/i);
  for (const column of ["source_url", "image_url", "rsvp_url"]) {
    assert.match(migration, new RegExp(`events_${column}_http[\\s\\S]*https\\?://`, "i"));
    assert.match(migration, new RegExp(`submissions_${column}_http[\\s\\S]*https\\?://`, "i"));
  }
});
