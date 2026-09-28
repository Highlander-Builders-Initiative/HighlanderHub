// Run with PGLITE_MODULE pointing to @electric-sql/pglite's ESM entrypoint.
// Applies the sort_at migration over live-shaped rows, then writes through the
// real publication and merge RPCs, which must keep it current.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';

const { PGlite } = await import(process.env.PGLITE_MODULE || '@electric-sql/pglite');
const migrations = new URL('../../supabase/migrations/', import.meta.url);
const db = new PGlite();
await db.exec('create role anon; create role authenticated; create role service_role bypassrls;');
const apply = async name => db.exec(await readFile(new URL(name, migrations), 'utf8'));
for (const name of ['20260513073310_init_schema.sql', '20260527000000_add_event_lock.sql',
  '20260528010000_discord_notifications.sql', '20260529000000_deleted_events.sql',
  '20260530000000_event_content_kind.sql', '20260531000000_event_has_free_food.sql',
  '20260531010000_discord_notification_stable_keys.sql',
  '20260909000000_event_content_kind_application.sql', '20260911000000_source_assessments.sql',
  '20260912000000_source_assessment_fanout_overrides.sql', '20260913000000_instagram_posts.sql',
  '20260916000000_instagram_only_publication.sql', '20260919000000_drop_event_is_free.sql',
  '20260922000000_event_duplicate_hosts.sql', '20260922010000_reconcile_legacy_duplicates.sql',
  '20260925010000_drop_highlander_link_reconcile.sql', '20260926010000_publication_noop_writes.sql',
  '20260927000000_duplicate_review_queue.sql', '20260928000000_activity_categories.sql',
  '20260928010000_activity_categories_backfill.sql']) {
  await apply(name);
}

function row(id, starts_at, ends_at, extra = {}) {
  return { id, title: id, description: '', starts_at, ends_at, location: '', host: 'Club',
    category: 'get_involved', content_kind: 'student_deadline', tags: [], source: 'instagram',
    has_free_food: false, rsvp_required: false, scraped_at: '2026-09-20T00:00:00Z', ...extra };
}
const publish = rows => db.query('select reconcile_source_assessments($1::jsonb)', [JSON.stringify([{
  source_key: `instagram:${rows[0].id}`, origin: 'instagram',
  assessment: { status: 'complete', reason: 'test' }, rows, known_event_ids: [] }])]);
const sortAt = async id =>
  (await db.query('select sort_at from events where id = $1', [id])).rows[0].sort_at.toISOString();
const stamp = async id =>
  (await db.query('select updated_at from events where id = $1', [id])).rows[0].updated_at.toISOString();

// Monday Sep 28, as stored before the migration.
const monday = [
  row('ig_book_clubs', '2026-09-28T07:00:00Z', '2026-09-29T07:00:00Z', { all_day: true }),
  row('ig_fair', '2026-09-28T07:00:00Z', '2026-09-29T07:00:00Z', { content_kind: 'student_event', all_day: true }),
  row('ig_clinic_5pm', '2026-09-29T00:00:00Z', null),
  row('ig_meeting_7pm', '2026-09-29T02:00:00Z', '2026-09-29T03:00:00Z', { content_kind: 'student_event' }),
  row('ig_due_12am', '2026-09-29T07:00:00Z', null),
];
for (const event of monday) await publish([event]);
const before = Object.fromEntries(await Promise.all(monday.map(async ({ id }) => [id, await stamp(id)])));
await apply('20260928020000_event_sort_at.sql');

test('existing rows sort by when they start or are due, without being touched', async () => {
  const { rows } = await db.query('select id from events order by sort_at, id');
  // All-day events open the day; a date-only deadline closes it at 11:59 PM;
  // a printed 12:00 AM cutoff is the midnight that opens Tuesday.
  assert.deepEqual(rows.map(r => r.id),
    ['ig_fair', 'ig_clinic_5pm', 'ig_meeting_7pm', 'ig_book_clubs', 'ig_due_12am']);
  assert.equal(await sortAt('ig_book_clubs'), '2026-09-29T06:59:00.000Z');
  assert.equal(await sortAt('ig_fair'), '2026-09-28T07:00:00.000Z');
  for (const { id } of monday) assert.equal(await stamp(id), before[id], id);
});

test('publication, admin edits and merges keep it current; nothing can write it', async () => {
  // Winter offset, and each DST changeover day.
  for (const [id, start, end, due] of [
    ['ig_winter', '2027-01-18T08:00:00Z', '2027-01-19T08:00:00Z', '2027-01-19T07:59:00.000Z'],
    ['ig_fall_back', '2026-11-01T07:00:00Z', '2026-11-02T08:00:00Z', '2026-11-02T07:59:00.000Z'],
    ['ig_spring_forward', '2027-03-14T08:00:00Z', '2027-03-15T07:00:00Z', '2027-03-15T06:59:00.000Z'],
  ]) {
    await publish([row(id, start, end, { all_day: true })]);
    assert.equal(await sortAt(id), due, id);
  }

  // A corrected date republishes; an admin gives it a printed time.
  await publish([row('ig_book_clubs', '2026-09-30T07:00:00Z', '2026-10-01T07:00:00Z', { all_day: true })]);
  assert.equal(await sortAt('ig_book_clubs'), '2026-10-01T06:59:00.000Z');
  await db.query(`update events set starts_at = '2026-09-30T20:00:00Z', ends_at = null where id = 'ig_book_clubs'`);
  assert.equal(await sortAt('ig_book_clubs'), '2026-09-30T20:00:00.000Z');

  // A merge that gives the kept deadline a day-long span makes it date-only.
  await db.query('select merge_duplicate_events($1, $2, $3::jsonb, $4, $5)', ['ig_due_12am', 'ig_clinic_5pm',
    JSON.stringify({ ends_at: '2026-09-30T07:00:00Z' }), await stamp('ig_due_12am'), await stamp('ig_clinic_5pm')]);
  assert.equal(await sortAt('ig_due_12am'), '2026-09-30T06:59:00.000Z');

  await assert.rejects(db.query(`update events set sort_at = now() where id = 'ig_fair'`), /can only be updated to DEFAULT/);
});
