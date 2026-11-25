// Run with PGLITE_MODULE pointing to @electric-sql/pglite's ESM entrypoint.
// Executes the follow-up posts migration: the video-cover flag through the
// publication RPC, and a merge that takes the other listing's date and time.
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
  '20260925010000_drop_highlander_link_reconcile.sql', '20260926010000_publication_noop_writes.sql',
  '20260927000000_duplicate_review_queue.sql', '20261125000000_follow_up_posts.sql']) {
  await db.exec(await readFile(new URL(name, migrations), 'utf8'));
}

function row(id, extra = {}) {
  return { id, title: 'Diwali Night', description: 'Join us',
    starts_at: '2026-12-05T02:00:00Z', ends_at: '2026-12-05T04:00:00Z', all_day: false,
    location: 'HUB 302', host: 'Club', host_handle: 'club', category: 'academic',
    content_kind: 'student_event', tags: [], source: 'instagram',
    image_url: `https://example.org/${id}.jpg`, image_is_video: null, has_free_food: false,
    rsvp_required: false, scraped_at: '2026-11-20T19:00:00Z', ...extra };
}
const update = (key, rows = []) => ({
  source_key: `instagram:${key}`, origin: 'instagram', assessment: { status: 'complete', reason: 'test' },
  rows, known_event_ids: [],
});
const publish = async updates =>
  (await db.query('select reconcile_source_assessments($1::jsonb) as result', [JSON.stringify(updates)])).rows[0].result;
const event = async id => (await db.query('select * from events where id = $1', [id])).rows[0];
const stamp = async id => (await event(id)).updated_at.toISOString();
const merge = async (keptId, removedId, changes = {}) =>
  db.query('select merge_duplicate_events($1, $2, $3::jsonb, $4, $5)', [keptId, removedId,
    JSON.stringify(changes), await stamp(keptId), await stamp(removedId)]);
async function reset() {
  await db.exec('truncate events, source_assessments, deleted_events, discord_notifications, event_duplicate_reviews');
}

test('publication stores whether a flyer is a video cover, and a change to it is a write', async () => {
  await reset();
  const posts = [update('post:1', [row('ig_club_p1')]), update('post:2', [row('ig_club_p2', { image_is_video: true })])];
  assert.equal((await publish(posts)).written, 2);
  assert.equal((await event('ig_club_p1')).image_is_video, null);
  assert.equal((await event('ig_club_p2')).image_is_video, true);
  // Republishing the same rows writes nothing.
  assert.equal((await publish(posts)).written, 0);
  // A reassessment that picks a still slide clears the flag.
  assert.equal((await publish([update('post:2', [row('ig_club_p2')])])).written, 1);
  assert.equal((await event('ig_club_p2')).image_is_video, null);
  // A row from a pipeline that predates the flag still publishes.
  const { image_is_video: _, ...legacy } = row('ig_club_p3');
  assert.equal((await publish([update('post:3', [legacy])])).written, 1);
});

test('a merge can take the other listing\'s date and time, which locks the kept listing', async () => {
  await reset();
  await publish([update('post:1', [row('ig_club_p1')]),
    update('post:2', [row('ig_club_p2', { starts_at: '2026-12-12T03:00:00Z', ends_at: null, image_is_video: true })])]);
  await merge('ig_club_p1', 'ig_club_p2',
    { starts_at: '2026-12-12T03:00:00Z', all_day: false, ends_at: null });

  const kept = await event('ig_club_p1');
  assert.equal(kept.starts_at.toISOString(), '2026-12-12T03:00:00.000Z');
  assert.equal(kept.ends_at, null);
  assert.equal(kept.all_day, false);
  assert.equal(kept.image_url, 'https://example.org/ig_club_p1.jpg');
  assert.equal(kept.is_locked, true);
  // The announcement's own post still states the old time; it must not win it back.
  assert.equal((await publish([update('post:1', [row('ig_club_p1')])])).written, 0);
  assert.equal((await event('ig_club_p1')).starts_at.toISOString(), '2026-12-12T03:00:00.000Z');
});

test('a merge locks the kept listing on request, so the next import keeps the admin\'s flyer', async () => {
  await reset();
  await publish([update('post:1', [row('ig_club_p1')]), update('post:2', [row('ig_club_p2')])]);
  await merge('ig_club_p1', 'ig_club_p2', { image_url: 'https://example.org/ig_club_p2.jpg', is_locked: true });
  assert.equal((await event('ig_club_p1')).is_locked, true);
  assert.equal((await publish([update('post:1', [row('ig_club_p1')])])).written, 0);
  assert.equal((await event('ig_club_p1')).image_url, 'https://example.org/ig_club_p2.jpg');
});

test('a merge can never unlock a listing', async () => {
  await reset();
  await publish([update('post:1', [row('ig_club_p1')]), update('post:2', [row('ig_club_p2')])]);
  await db.query("update events set is_locked = true where id = 'ig_club_p1'");
  await merge('ig_club_p1', 'ig_club_p2', { is_locked: false });
  assert.equal((await event('ig_club_p1')).is_locked, true);
});

test('a merge that takes no time leaves the kept listing unlocked, and a taken flyer brings its flag', async () => {
  await reset();
  await publish([update('post:1', [row('ig_club_p1')]),
    update('post:2', [row('ig_club_p2', { image_is_video: true })])]);
  await merge('ig_club_p2', 'ig_club_p1',
    { image_url: 'https://example.org/ig_club_p1.jpg', image_is_video: null });
  const kept = await event('ig_club_p2');
  assert.equal(kept.is_locked, false);
  assert.equal(kept.image_url, 'https://example.org/ig_club_p1.jpg');
  assert.equal(kept.image_is_video, null);
});

test('a merge still cannot rewrite what identifies the kept event', async () => {
  await reset();
  await publish([update('post:1', [row('ig_club_p1')]), update('post:2', [row('ig_club_p2')])]);
  await assert.rejects(merge('ig_club_p1', 'ig_club_p2', { title: 'Renamed' }), /only combine details/);
  await assert.rejects(merge('ig_club_p1', 'ig_club_p2', { source_url: 'https://example.org' }), /only combine details/);
});
