import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { test } from "node:test";

const sourceFile = (path) => new URL(`../${path}`, import.meta.url);
const read = (path) => readFileSync(sourceFile(path), "utf8");

test("event validation helpers reject unsafe URLs and backwards end times", () => {
  const result = spawnSync(
    process.execPath,
    [
      "--experimental-strip-types",
      "--input-type=module",
      "--eval",
      `
        const validation = await import("./src/lib/event-validation.ts");
        const ok = validation.validateEventTimes("2026-05-20T12:00", "2026-05-20T12:00");
        const backwards = validation.validateEventTimes("2026-05-20T12:00", "2026-05-20T11:59");
        const badStart = validation.validateEventTimes("not a date", "");
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
        }));
      `,
    ],
    {
      cwd: process.cwd(),
      env: { ...process.env, TZ: "America/Los_Angeles" },
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
  });
});

test("submission and detail surfaces use shared URL and time guards", () => {
  const form = read("src/components/forms/SubmitForm.tsx");
  const detail = read("src/app/events/[id]/page.tsx");
  const actions = read("src/lib/event-actions.ts");
  const events = read("src/lib/events.ts");

  assert.match(form, /normalizeHttpUrl/);
  assert.match(form, /validateEventTimes/);
  assert.match(form, /fieldErrors\.ends_at/);
  assert.match(form, /Use an http\(s\) URL\./);
  assert.match(detail, /safeRsvpUrl/);
  assert.match(detail, /safeSourceUrl/);
  assert.match(actions, /normalizeHttpUrl\(event\.rsvpUrl\)/);
  assert.match(actions, /normalizeHttpUrl\(event\.sourceUrl\)/);
  assert.match(events, /normalizeHttpUrl\(r\.source_url\)/);
  assert.match(events, /normalizeHttpUrl\(r\.image_url\)/);
  assert.match(events, /normalizeHttpUrl\(r\.rsvp_url\)/);
});

test("event detail lookup is request-level cached", () => {
  const source = read("src/lib/events.ts");

  assert.match(source, /import \{ cache \} from "react"/);
  assert.match(source, /export const getEventById = cache\(/);
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
