// Run with PGLITE_MODULE pointing to @electric-sql/pglite's ESM entrypoint.
// Executes the duplicate review migration against the real publication RPC.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';

const { PGlite } = await import(process.env.PGLITE_MODULE || '@electric-sql/pglite');
const migrations = new URL('../../supabase/migrations/', import.meta.url);
const db = new PGlite();
await db.exec('create role anon; create role authenticated; create role service_role bypassrls;');
for (const name of ['20260513073310_init_schema.sql', '20260527000000_add_event_lock.sql',
  '20260528010000_discord_notifications.sql', '20260529000000_deleted_events.sql',
  '20260530000000_event_content_kind.sql', '20260531000000_event_has_free_food.sql',
  '20260531010000_discord_notification_stable_keys.sql',
  '20260909000000_event_content_kind_application.sql', '20260911000000_source_assessments.sql',
  '20260912000000_source_assessment_fanout_overrides.sql', '20260913000000_instagram_posts.sql',
  '20260916000000_instagram_only_publication.sql', '20260919000000_drop_event_is_free.sql',
  '20260922000000_event_duplicate_hosts.sql', '20260922010000_reconcile_legacy_duplicates.sql',
  '20260925010000_drop_highlander_link_reconcile.sql', '20260927000000_duplicate_review_queue.sql']) {
  await db.exec(await readFile(new URL(name, migrations), 'utf8'));
}

function row(id, extra = {}) {
  return { id, title: 'Workshop', description: 'An actual workshop',
    starts_at: '2026-09-15T22:00:00Z', ends_at: '2026-09-16T00:00:00Z',
    location: 'HUB', host: 'Club', category: 'academic', content_kind: 'student_event',
    tags: [], source: 'instagram', has_free_food: false,
    rsvp_required: false, scraped_at: '2026-09-11T19:00:00Z', ...extra };
}
const update = (key, rows = []) => ({
  source_key: `instagram:${key}`, origin: 'instagram', assessment: { status: 'complete', reason: 'test' },
  rows, known_event_ids: [],
});
const publish = updates => db.query('select reconcile_source_assessments($1::jsonb)', [JSON.stringify(updates)]);
const ids = async () => (await db.query('select id from events order by id')).rows.map(r => r.id);
const event = async id => (await db.query('select * from events where id = $1', [id])).rows[0];
const stamp = async id => (await event(id)).updated_at.toISOString();
const merge = async (keptId, removedId, changes = {}, stamps = {}) =>
  db.query('select merge_duplicate_events($1, $2, $3::jsonb, $4, $5)', [keptId, removedId,
    JSON.stringify(changes), stamps.kept ?? await stamp(keptId), stamps.removed ?? await stamp(removedId)]);
async function reset() {
  await db.exec('truncate events, source_assessments, deleted_events, discord_notifications, event_duplicate_reviews');
}

test('a merge keeps one listing, combines details and moves source support onto it', async () => {
  await reset();
  await publish([update('post:1', [row('ig_a_p1')]), update('post:2', [row('ig_b_p2', { has_free_food: true })])]);
  await merge('ig_a_p1', 'ig_b_p2', { has_free_food: true, hosts: [{ host: 'B', host_handle: 'b' }] });

  assert.deepEqual(await ids(), ['ig_a_p1']);
  const kept = await event('ig_a_p1');
  assert.equal(kept.has_free_food, true);
  assert.deepEqual(kept.hosts, [{ host: 'B', host_handle: 'b' }]);
  assert.equal(kept.title, 'Workshop');
  const sources = (await db.query("select event_ids, known_event_ids from source_assessments where source_key = 'instagram:post:2'")).rows[0];
  assert.deepEqual(sources.event_ids, ['ig_a_p1']);
  assert.deepEqual(sources.known_event_ids.sort(), ['ig_a_p1', 'ig_b_p2']);

  const review = (await db.query('select * from event_duplicate_reviews')).rows[0];
  assert.equal(review.status, 'duplicate');
  assert.equal(review.kept_event_id, 'ig_a_p1');
  assert.equal(review.event_snapshot.id, 'ig_a_p1');
  assert.equal(review.other_snapshot.id, 'ig_b_p2');
  assert.equal(review.other_snapshot.has_free_food, true);
  assert.ok(review.decided_at);

  // The kept post withdrawing its listing no longer strands the other post's support.
  await publish([update('post:1')]);
  assert.deepEqual(await ids(), ['ig_a_p1']);
});

test('a merge only combines details and never rewrites what identifies the kept event', async () => {
  await reset();
  await publish([update('post:1', [row('ig_a_p1')]), update('post:2', [row('ig_b_p2')])]);
  await assert.rejects(merge('ig_a_p1', 'ig_b_p2', { title: 'Renamed' }), /only combine details/);
  await assert.rejects(merge('ig_a_p1', 'ig_a_p1'), /into itself/);
  await assert.rejects(merge('ig_a_p1', 'ig_missing', {}, { removed: '2026-01-01T00:00:00Z' }), /no longer exists/);
  assert.deepEqual(await ids(), ['ig_a_p1', 'ig_b_p2']);
  assert.equal((await db.query('select count(*)::int as n from event_duplicate_reviews')).rows[0].n, 0);
});

test('a listing changed after the review loaded aborts the merge', async () => {
  await reset();
  await publish([update('post:1', [row('ig_a_p1')]), update('post:2', [row('ig_b_p2')])]);
  const before = await stamp('ig_b_p2');
  await db.query("update events set title = 'Workshop (updated)' where id = 'ig_b_p2'");
  await assert.rejects(merge('ig_a_p1', 'ig_b_p2', {}, { removed: before }), /changed since this review loaded/);
  assert.deepEqual(await ids(), ['ig_a_p1', 'ig_b_p2']);
});

test('an admin merge may retire a locked listing, and ordering follows byte order', async () => {
  await reset();
  // "ig_swe.ucr" sorts before "ig_swe_ucr" by byte, after it in many locales.
  await publish([update('post:1', [row('ig_swe_ucr_p1')]), update('post:2', [row('ig_swe.ucr_p2')])]);
  await db.query("update events set is_locked = true where id = 'ig_swe.ucr_p2'");
  await merge('ig_swe_ucr_p1', 'ig_swe.ucr_p2');
  assert.deepEqual(await ids(), ['ig_swe_ucr_p1']);
  const review = (await db.query('select event_id, other_event_id, kept_event_id from event_duplicate_reviews')).rows[0];
  assert.deepEqual(review, { event_id: 'ig_swe.ucr_p2', other_event_id: 'ig_swe_ucr_p1', kept_event_id: 'ig_swe_ucr_p1' });
});

test('an alert already sent for the retired listing covers the kept one', async () => {
  await reset();
  await publish([update('post:1', [row('ig_a_p1', { title: 'Boba  Night' })]),
    update('post:2', [row('ig_b_p2', { has_free_food: true })])]);
  await db.query(`insert into discord_notifications(event_id, kind, notification_key, notified_at)
    values ('ig_b_p2', 'free_food', 'free_food:v2:title-day:workshop|20260915', '2026-09-12T00:00:00Z')`);
  await merge('ig_a_p1', 'ig_b_p2', { has_free_food: true });
  const ledger = (await db.query('select event_id, notification_key, notified_at from discord_notifications order by event_id')).rows;
  assert.deepEqual(ledger.map(n => [n.event_id, n.notification_key]), [
    ['ig_a_p1', 'free_food:v2:title-day:boba night|20260915'],
    ['ig_b_p2', 'free_food:v2:title-day:workshop|20260915'],
  ]);
  assert.equal(ledger[0].notified_at.toISOString(), '2026-09-12T00:00:00.000Z');
});

test('a merge replaces a pending flag, and the queue only accepts ordered pairs', async () => {
  await reset();
  await publish([update('post:1', [row('ig_a_p1')]), update('post:2', [row('ig_b_p2')])]);
  await db.query("insert into event_duplicate_reviews(event_id, other_event_id) values ('ig_a_p1', 'ig_b_p2')");
  await merge('ig_b_p2', 'ig_a_p1');
  const reviews = (await db.query('select status, kept_event_id from event_duplicate_reviews')).rows;
  assert.deepEqual(reviews, [{ status: 'duplicate', kept_event_id: 'ig_b_p2' }]);
  await assert.rejects(db.query("insert into event_duplicate_reviews(event_id, other_event_id) values ('ig_z', 'ig_y')"));
  await assert.rejects(db.query(`insert into event_duplicate_reviews(event_id, other_event_id, status, decided_at)
    values ('ig_c', 'ig_d', 'duplicate', now())`));
});

test('public roles cannot read the queue or merge', async () => {
  await reset();
  await db.exec('set role anon');
  try {
    await assert.rejects(db.query('select * from event_duplicate_reviews'), /permission denied/);
    await assert.rejects(merge('ig_a', 'ig_b', {}, { kept: '2026-01-01T00:00:00Z', removed: '2026-01-01T00:00:00Z' }),
      /permission denied/);
  } finally {
    await db.exec('reset role');
  }
});
