// Run with PGLITE_MODULE pointing to @electric-sql/pglite's ESM entrypoint.
// This executes the actual PostgreSQL migration in a disposable database.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';

const { PGlite } = await import(process.env.PGLITE_MODULE || '@electric-sql/pglite');
const migrations = new URL('../../supabase/migrations/', import.meta.url);
const db = new PGlite();
await db.exec('create role anon; create role authenticated; create role service_role bypassrls;');
for (const name of ['20260513073310_init_schema.sql', '20260527000000_add_event_lock.sql',
  '20260529000000_deleted_events.sql', '20260530000000_event_content_kind.sql',
  '20260531000000_event_has_free_food.sql', '20260909000000_event_content_kind_application.sql',
  '20260911000000_source_assessments.sql', '20260912000000_source_assessment_fanout_overrides.sql']) {
  await db.exec(await readFile(new URL(name, migrations), 'utf8'));
}

function row(id, extra = {}) {
  return { id, title: 'Workshop', description: 'An actual workshop',
    starts_at: '2026-09-15T22:00:00Z', ends_at: '2026-09-16T00:00:00Z',
    location: 'HUB', host: 'Club', category: 'academic', content_kind: 'student_event',
    tags: [], source: 'instagram', is_free: true, has_free_food: false,
    rsvp_required: false, scraped_at: '2026-09-11T19:00:00Z', ...extra };
}
const update = (key, rows = [], aliases = [], status = 'complete') => ({
  source_key: `instagram:${key}`, origin: 'instagram', assessment: { status, reason: 'test' },
  rows, known_event_ids: aliases,
});
const publish = async updates => (await db.query('select reconcile_source_assessments($1::jsonb) as result', [JSON.stringify(updates)])).rows[0].result;
const ids = async () => (await db.query('select id from events order by id')).rows.map(r => r.id);
async function reset() { await db.exec('truncate events, source_assessments, deleted_events'); }

test('reconciliation preserves another source, then removes unsupported rows', async () => {
  await reset();
  await publish([update('a', [row('ig_shared')]), update('b', [row('ig_shared')])]);
  await publish([update('a')]);
  assert.deepEqual(await ids(), ['ig_shared']);
  await publish([update('b')]);
  assert.deepEqual(await ids(), []);
});

test('a failed reassessment preserves the previous result and retries safely', async () => {
  await reset();
  await publish([update('a', [row('ig_a')])]);
  await publish([update('a', [], [], 'error')]);
  assert.deepEqual(await ids(), ['ig_a']);
  const saved = (await db.query('select * from source_assessments')).rows[0];
  assert.equal(saved.assessment.status, 'error');
  assert.equal(saved.last_complete_assessment.status, 'complete');
  await publish([update('a')]);
  assert.deepEqual(await ids(), []);
});

test('a newly discovered failing source protects its legacy shared listing', async () => {
  await reset();
  await publish([update('a', [row('ig_shared')])]);
  await publish([update('a'), update('b', [], ['ig_shared'], 'error')]);
  assert.deepEqual(await ids(), ['ig_shared']);
});

test('invalid row rolls back both ownership and deletion in the whole batch', async () => {
  await reset();
  await publish([update('a', [row('ig_old')])]);
  await assert.rejects(publish([update('a'), update('b', [row('ig_bad', { title: null })])]));
  assert.deepEqual(await ids(), ['ig_old']);
  assert.deepEqual((await db.query('select event_ids from source_assessments')).rows[0].event_ids, ['ig_old']);
});

test('legacy identities retire and rekeying is idempotent', async () => {
  await reset();
  await publish([update('old', [row('ig_old')])]);
  const result = await publish([update('old', [row('ig_new')], ['ig_old'])]);
  assert.equal(result.deleted, 1);
  assert.deepEqual(await ids(), ['ig_new']);
  await publish([update('old', [row('ig_new')], ['ig_old'])]);
  assert.deepEqual(await ids(), ['ig_new']);
});

test('admin locks and tombstones bind replacement identities', async () => {
  await reset();
  await publish([update('a', [row('ig_old')])]);
  await db.exec("update events set is_locked=true where id='ig_old'");
  await publish([update('a', [row('ig_new')], ['ig_old'])]);
  assert.deepEqual(await ids(), ['ig_old']);
  await reset();
  await db.exec("insert into deleted_events(event_id) values ('ig_old')");
  await publish([update('a', [row('ig_new')], ['ig_old'])]);
  assert.deepEqual(await ids(), []);
});

test('source fanout updates only its supported sessions', async () => {
  await reset();
  await publish([update('hours', [row('ig_morning'), row('ig_afternoon')])]);
  await publish([update('hours', [row('ig_afternoon')])]);
  assert.deepEqual(await ids(), ['ig_afternoon']);
});

for (const override of ['lock', 'tombstone']) {
  test(`${override} on a morning session preserves its afternoon sibling`, async () => {
    await reset();
    await publish([update('hours', [row('ig_morning'), row('ig_afternoon')])]);
    if (override === 'lock') {
      await db.exec("update events set is_locked=true, title='Admin title' where id='ig_morning'");
    } else {
      await db.exec("insert into deleted_events(event_id) values ('ig_morning'); delete from events where id='ig_morning'");
    }
    for (const morning of ['ig_morning', 'ig_rekeyed_morning']) {
      await publish([update('hours', [row(morning), row('ig_afternoon', { title: 'Updated afternoon' })])]);
      assert.deepEqual(await ids(), override === 'lock' ? ['ig_afternoon', 'ig_morning'] : ['ig_afternoon']);
      assert.equal((await db.query("select title from events where id='ig_afternoon'")).rows[0].title, 'Updated afternoon');
    }
    if (override === 'lock') {
      assert.equal((await db.query("select title from events where id='ig_morning'")).rows[0].title, 'Admin title');
    }
    await publish([update('hours')]);
    assert.deepEqual(await ids(), override === 'lock' ? ['ig_morning'] : []);
  });
}

test('real importer RPC batches retire unsupported IDs while preserving a locked fanout session', async () => {
  const root = fileURLToPath(new URL('../../', import.meta.url));
  const venv = `${root}pipeline/.venv/bin/python`;
  const python = process.env.PIPELINE_PYTHON || (existsSync(venv) ? venv : 'python3');
  const [story, rejectedStory, calendar, vanishedCalendar] = JSON.parse(execFileSync(python,
    [fileURLToPath(new URL('./importer-publication-fixtures.py', import.meta.url))],
    { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }));
  assert.equal(story[0].assessment.status, 'complete');
  assert.equal(story[0].rows.length, 2);
  const [morning, afternoon] = story[0].rows.map(r => r.id);
  await reset();
  await publish(story);
  await db.query('update events set is_locked=true where id=$1', [morning]);
  await publish(story);
  assert.deepEqual(await ids(), [morning, afternoon].sort());
  await publish(rejectedStory);
  assert.deepEqual(await ids(), [morning]);

  await reset();
  await publish(story);
  await publish(rejectedStory);
  assert.deepEqual(await ids(), []);
  await publish(calendar);
  assert.deepEqual(await ids(), ['ucr_events_456']);
  await publish(vanishedCalendar);
  assert.deepEqual(await ids(), []);
});

test('deduplication transfers source support to the canonical event', async () => {
  await reset();
  await publish([update('a', [row('ig_a')]), update('b', [row('ig_b')])]);
  await db.query('select remap_assessed_event_sources($1::jsonb)', [JSON.stringify([
    { id: 'ig_a', replacement_id: 'ig_b' },
  ])]);
  assert.deepEqual(await ids(), ['ig_b']);
  await publish([update('b')]);
  assert.deepEqual(await ids(), ['ig_b']);
  await publish([update('a')]);
  assert.deepEqual(await ids(), []);
});

test('concurrent edits abort duplicate ownership remapping', async () => {
  await reset();
  await publish([update('a', [row('ig_a')]), update('b', [row('ig_b')])]);
  await assert.rejects(db.query('select remap_assessed_event_sources($1::jsonb)', [JSON.stringify([
    { id: 'ig_a', replacement_id: 'ig_b', updated_at: '2000-01-01T00:00:00Z' },
  ])]), /changed during/);
  assert.deepEqual(await ids(), ['ig_a', 'ig_b']);
});

test('public roles cannot read assessments or invoke the publisher', async () => {
  await reset();
  await db.exec('set role anon');
  await assert.rejects(db.query('select * from source_assessments'), /permission denied/);
  await assert.rejects(publish([]), /permission denied/);
  await assert.rejects(db.query("select remap_assessed_event_sources('[]')"), /permission denied/);
  await db.exec('reset role');
});

test.after(async () => { await db.close(); });
