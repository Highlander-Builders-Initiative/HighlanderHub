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
const migrationNames = ['20260513073310_init_schema.sql', '20260527000000_add_event_lock.sql',
  '20260529000000_deleted_events.sql', '20260530000000_event_content_kind.sql',
  '20260531000000_event_has_free_food.sql', '20260909000000_event_content_kind_application.sql',
  '20260911000000_source_assessments.sql', '20260912000000_source_assessment_fanout_overrides.sql',
  '20260913000000_instagram_posts.sql', '20260916000000_instagram_only_publication.sql',
  '20260919000000_drop_event_is_free.sql', '20260922000000_event_duplicate_hosts.sql',
  '20260922010000_reconcile_legacy_duplicates.sql'];
for (const name of migrationNames) {
  await db.exec(await readFile(new URL(name, migrations), 'utf8'));
}

function row(id, extra = {}) {
  return { id, title: 'Workshop', description: 'An actual workshop',
    starts_at: '2026-09-15T22:00:00Z', ends_at: '2026-09-16T00:00:00Z',
    location: 'HUB', host: 'Club', category: 'academic', content_kind: 'student_event',
    tags: [], source: 'instagram', has_free_food: false,
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

const importerBatches = (() => {
  const root = fileURLToPath(new URL('../../', import.meta.url));
  const venv = `${root}pipeline/.venv/bin/python`;
  const python = process.env.PIPELINE_PYTHON || (existsSync(venv) ? venv : 'python3');
  return JSON.parse(execFileSync(python,
    [fileURLToPath(new URL('./importer-publication-fixtures.py', import.meta.url))],
    { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }));
})();


test('a post publishes one listing with its source and flyer', async () => {
  const [instagram] = importerBatches;
  await reset();
  const written = await publish(instagram);
  assert.deepEqual(await ids(), ['ig_acm.ucr_p700']);
  assert.deepEqual(instagram.map(i => i.source_key), ['instagram:post:700']);
  const row = (await db.query('select source_url, image_url, description from events')).rows[0];
  assert.equal(row.source_url, 'https://www.instagram.com/p/CStudy/');
  assert.equal(row.image_url, 'https://storage.example/700_0_n.jpg');
  assert.equal(written.written, 1);
});

test('a corrected caption withdraws the post-supported listing', async () => {
  const [instagram, withdrawn] = importerBatches;
  await reset();
  await publish(instagram);
  await publish(withdrawn);
  assert.deepEqual(await ids(), []);
});

for (const retainedBy of [null, 'other source', 'admin lock']) {
  test(`a no_text extraction removes post support, preserving ${retainedBy || 'no unsupported listing'}`, async () => {
    const [instagram, , , emptied] = importerBatches;
    const event = instagram[0].rows[0];
    await reset();
    await publish(instagram);
    if (retainedBy === 'other source') {
      await publish([update('another', [event])]);
    } else if (retainedBy === 'admin lock') {
      await db.query('update events set is_locked=true where id=$1', [event.id]);
    }
    await publish(emptied);
    assert.deepEqual(await ids(), retainedBy ? [event.id] : []);
    const source = (await db.query('select event_ids, assessment from source_assessments where source_key=$1',
      [instagram[0].source_key])).rows[0];
    assert.deepEqual(source.event_ids, []);
    assert.equal(source.assessment.status, 'complete');
  });
}

test('an unrelated club posting the same title and time keeps its own listing', async () => {
  const [instagram, , otherClub] = importerBatches;
  await reset();
  await publish(instagram);
  await publish(otherClub);
  assert.deepEqual(await ids(), ['ig_acm.ucr_p700', 'ig_ieee.ucr_p800']);
});

test('same-owner deadlines split legacy collisions without losing source ownership', async () => {
  const deadlines = importerBatches[4];
  await reset();
  const legacy = deadlines.map((item, index) => ({ ...item,
    rows: [{ ...item.rows[0], id: index < 2 ? 'ig_acm_ucr_20260925T0700Z' : 'ig_ideasandsociety_20260928T0700Z' }],
    known_event_ids: [],
  }));
  await publish(legacy);
  assert.equal((await ids()).length, 2); // Reproduce the old overwrite.
  const expected = deadlines.flatMap(item => item.rows.map(row => row.id)).sort();
  assert.equal(new Set(expected).size, 4);
  assert.deepEqual(await publish(deadlines), { written: 4, deleted: 2 });
  await publish(deadlines); // Idempotent replay.
  assert.deepEqual(await ids(), expected);
  for (const item of deadlines) {
    const saved = (await db.query('select * from source_assessments where source_key=$1', [item.source_key])).rows[0];
    assert.deepEqual(saved.event_ids, [item.rows[0].id]);
    const event = (await db.query('select * from events where id=$1', [item.rows[0].id])).rows[0];
    assert.equal(event.title, item.rows[0].title);
    assert.equal(event.rsvp_url, item.rows[0].rsvp_url);
    assert.equal(event.source_url, item.rows[0].source_url);
  }
  await publish([{ ...deadlines[0], rows: [] }]);
  assert.deepEqual(await ids(), expected.filter(id => id !== deadlines[0].rows[0].id));
});

for (const override of ['lock', 'tombstone']) {
  test(`legacy ${override} remains authoritative when a colliding deadline splits`, async () => {
    const deadlines = importerBatches[4].slice(0, 2);
    const oldId = 'ig_acm_ucr_20260925T0700Z';
    await reset();
    await publish(deadlines.map(item => ({ ...item, rows: [{ ...item.rows[0], id: oldId }], known_event_ids: [] })));
    if (override === 'lock') {
      await db.query('update events set is_locked=true where id=$1', [oldId]);
    } else {
      await db.query('insert into deleted_events(event_id) values ($1)', [oldId]);
      await db.query('delete from events where id=$1', [oldId]);
    }
    await publish(deadlines);
    assert.deepEqual(await ids(), override === 'lock' ? [oldId] : []);
  });
}

test('admin locks and tombstones bind a post-supported listing', async () => {
  const [instagram, withdrawn] = importerBatches;
  await reset();
  await publish(instagram);
  await db.exec("update events set is_locked=true, title='Admin title' where id='ig_acm.ucr_p700'");
  await publish(instagram);
  assert.equal((await db.query('select title from events')).rows[0].title, 'Admin title');
  await publish(withdrawn);
  assert.deepEqual(await ids(), ['ig_acm.ucr_p700']);

  await reset();
  await db.exec("insert into deleted_events(event_id) values ('ig_acm.ucr_p700')");
  await publish(instagram);
  assert.deepEqual(await ids(), []);
});

test('post collection state is service-role only and activation cannot move', async () => {
  await db.exec("truncate instagram_post_checkpoints");
  const claim = async at => (await db.query('select claim_post_activation($1::jsonb) as result',
    [JSON.stringify([{ handle: 'acm.ucr', activated_at: at }])])).rows[0].result;
  const first = await claim('2026-06-01T00:00:00Z');
  assert.equal(new Date(first['acm.ucr'].activated_at).toISOString(), '2026-06-01T00:00:00.000Z');
  // A rerun, a restored backup, or a lost local cache must not re-activate.
  const second = await claim('2026-09-11T00:00:00Z');
  assert.equal(new Date(second['acm.ucr'].activated_at).toISOString(), '2026-06-01T00:00:00.000Z');
  await db.exec('set role anon');
  await assert.rejects(db.query('select * from instagram_post_checkpoints'), /permission denied/);
  await assert.rejects(db.query('select * from post_extractions'), /permission denied/);
  await assert.rejects(db.query('select * from instagram_posts'), /permission denied/);
  await assert.rejects(db.query("select claim_post_activation('[]')"), /permission denied/);
  await db.exec('reset role');
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

test('retired campus duplicates can only reconcile into an Instagram survivor', async () => {
  await reset();
  await publish([update('post:1', [row('ig_survivor')])]);
  await db.query(`insert into events(id,title,description,starts_at,ends_at,location,host,category,
    content_kind,tags,source,has_free_food,rsvp_required,scraped_at)
    values ('highlander_link_1','Workshop','An actual workshop',$1,$2,'HUB','Club','academic',
    'student_event','{}','campus_website',false,false,$3)`,
    ['2026-09-15T22:00:00Z', '2026-09-16T00:00:00Z', '2026-09-11T19:00:00Z']);
  await db.query('select remap_assessed_event_sources($1::jsonb)', [JSON.stringify([
    { id: 'highlander_link_1', replacement_id: 'ig_survivor' },
  ])]);
  assert.deepEqual(await ids(), ['ig_survivor']);

  await db.query(`insert into events(id,title,description,starts_at,location,host,category,
    content_kind,tags,source,has_free_food,rsvp_required,scraped_at)
    values ('highlander_link_2','Other','Other event',$1,'HUB','Club','academic',
    'student_event','{}','campus_website',false,false,$2)`,
    ['2026-09-15T22:00:00Z', '2026-09-11T19:00:00Z']);
  await assert.rejects(db.query('select remap_assessed_event_sources($1::jsonb)', [JSON.stringify([
    { id: 'highlander_link_2', replacement_id: null },
  ])]), /must reconcile into Instagram/);
  assert.deepEqual(await ids(), ['highlander_link_2', 'ig_survivor']);
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


test('publication rejects unsupported origins and imported row types', async () => {
  await reset();
  await assert.rejects(publish([{ ...update('unsupported'), origin: 'website' }]), /Invalid assessment update/);
  await assert.rejects(publish([{ ...update('unsupported'), source_key: 'website:123' }]), /Invalid assessment update/);
  await assert.rejects(publish([update('wrong_id', [row('website_123')])]), /Only publishable imported/);
  await assert.rejects(publish([update('wrong_source', [row('ig_123', { source: 'campus_website' })])]), /Only publishable imported/);
  assert.deepEqual(await ids(), []);
});

test('publication retains assessed time precision and reconciled hosts across reruns', async () => {
  await reset();
  const event = row('ig_precision', { all_day: true });
  await publish([update('precision', [event])]);
  const hosts = [{ host: 'Club A', host_handle: 'club_a' }, { host: 'Club B', host_handle: 'club_b' }];
  await db.query('update events set hosts=$1::jsonb where id=$2', [JSON.stringify(hosts), event.id]);
  await publish([update('precision', [{ ...event, all_day: false }])]);
  const saved = (await db.query('select all_day, hosts from events where id=$1', [event.id])).rows[0];
  assert.equal(saved.all_day, false);
  assert.deepEqual(saved.hosts, hosts);
});

function reconciliationPlan(rows, tombstones = []) {
  const root = fileURLToPath(new URL('../../', import.meta.url));
  const venv = `${root}pipeline/.venv/bin/python`;
  const python = process.env.PIPELINE_PYTHON || (existsSync(venv) ? venv : 'python3');
  return JSON.parse(execFileSync(python, ['-c',
    "import json,sys; sys.path.insert(0, 'pipeline'); from reconcile_events import plan; rows,tombs=json.load(sys.stdin); u,r,m=plan(rows,tombs); print(json.dumps([u,sorted(r),m]))"],
  { cwd: root, input: JSON.stringify([rows, tombstones]), encoding: 'utf8',
    env: { ...process.env, PYTHON_DOTENV_DISABLED: '1' } }));
}

async function applyReconciliation(rows, tombstones = []) {
  const [updates, removed, replacements] = reconciliationPlan(rows, tombstones);
  for (const event of updates) {
    // Apply the planner's canonical row before the same removal payload main uses.
    await db.query(`update events set ends_at=r.ends_at, rsvp_url=r.rsvp_url,
      rsvp_required=r.rsvp_required, has_free_food=r.has_free_food, hosts=r.hosts,
      location=r.location, image_url=r.image_url
      from jsonb_populate_record(null::events, $1::jsonb) r where events.id=r.id`,
    [JSON.stringify(event)]);
  }
  const removals = removed.map(id => ({ id, replacement_id: replacements[id] ?? null,
    updated_at: rows.find(row => row.id === id).updated_at }));
  await db.query('select remap_assessed_event_sources($1::jsonb)', [JSON.stringify(removals)]);
  return [updates, removed, replacements];
}

test('planner outputs apply atomically across legacy, tombstoned, locked and Instagram groups', async () => {
  for (const locked of [false, true]) {
    await reset();
    const campusRows = [
      row('highlander_link_only', { title: 'Legacy Only', source: 'campus_website' }),
      row('ucr_events_only', { title: 'Legacy Only', source: 'campus_website' }),
      row('highlander_link_deleted', { title: 'Deleted Study Jam', source: 'campus_website' }),
      row('highlander_link_merge', { title: 'Merged Study Jam', source: 'campus_website', is_locked: locked }),
      row('ucr_events_merge', { title: 'Merged Study Jam', source: 'campus_website' }),
      row('highlander_link_manual', { title: 'Merged Study Jam', source: 'manual' }),
    ];
    for (const event of campusRows) {
      await db.query(`insert into events(id,title,description,starts_at,ends_at,location,host,
        category,content_kind,tags,source,has_free_food,rsvp_required,scraped_at,is_locked)
        select id,title,description,starts_at,ends_at,location,host,category,content_kind,tags,
          source,has_free_food,rsvp_required,scraped_at,coalesce(is_locked,false)
        from jsonb_populate_record(null::events,$1::jsonb)`, [JSON.stringify(event)]);
    }
    await publish([
      update('deleted', [row('ig_deleted_p101', { title: 'Deleted Study Jam' })]),
      update('merge', [row('ig_merge_p201', { title: 'Merged Study Jam' })]),
      update('independent1', [row('ig_independent_p301', { title: 'Unrelated Study Jam' })]),
      update('independent2', [row('ig_independent_p302', { title: 'Unrelated Study Jam' })]),
    ]);
    const rows = (await db.query('select * from events order by id')).rows;
    const tombstones = [row('ig_deleted_p100', { title: 'Deleted Study Jam' })];
    const [, removed, replacements] = await applyReconciliation(rows, tombstones);
    assert.deepEqual(removed, locked
      ? ['ig_deleted_p101', 'ig_independent_p301', 'ig_merge_p201']
      : ['highlander_link_merge', 'ig_deleted_p101', 'ig_independent_p301', 'ucr_events_merge']);
    assert.deepEqual(replacements, locked
      ? { ig_independent_p301: 'ig_independent_p302', ig_merge_p201: 'highlander_link_merge' }
      : { highlander_link_merge: 'ig_merge_p201', ig_independent_p301: 'ig_independent_p302', ucr_events_merge: 'ig_merge_p201' });
    assert.deepEqual(await ids(), rows.map(r => r.id).filter(id => !removed.includes(id)).sort());
    const sources = (await db.query('select source_key,event_ids from source_assessments')).rows;
    assert.deepEqual(sources.find(r => r.source_key === 'instagram:deleted').event_ids, []);
    assert.deepEqual(sources.find(r => r.source_key === 'instagram:independent1').event_ids, ['ig_independent_p302']);
    assert.deepEqual(sources.find(r => r.source_key === 'instagram:merge').event_ids,
      [locked ? 'highlander_link_merge' : 'ig_merge_p201']);
    assert.deepEqual(reconciliationPlan((await db.query('select * from events')).rows, tombstones), [[], [], {}]);
  }
});

test('KUCR teaser and timed announcement reconcile and remain supported after republication', async () => {
  await reset();
  const teaser = row('ig_ucralumni_p3966553446651553037', {
    title: 'KUCR 60th Anniversary gala', all_day: true,
    starts_at: '2026-10-02T07:00:00Z', ends_at: '2026-10-03T07:00:00Z',
    location: 'The Alumni and Visitors Center, UC Riverside',
    host: 'UCR Alumni Association', host_handle: 'ucralumni',
  });
  const timed = { ...teaser, id: 'ig_ucralumni_p3977498071100870455',
    title: 'KUCR 60th Anniversary Celebration', all_day: false,
    starts_at: '2026-10-03T01:00:00Z', ends_at: null,
    location: 'UCR Alumni & Visitors Center' };
  const inputs = [update('post:3966553446651553037', [teaser]), update('post:3977498071100870455', [timed])];
  for (let run = 0; run < 2; run++) {
    await publish(inputs);
    const rows = (await db.query('select * from events')).rows;
    const planned = await applyReconciliation(rows);
    assert.deepEqual(planned, [[], [teaser.id], { [teaser.id]: timed.id }]);
    assert.deepEqual(await ids(), [timed.id]);
    const sources = (await db.query('select event_ids from source_assessments')).rows;
    assert.ok(sources.every(source => source.event_ids.length === 1 && source.event_ids[0] === timed.id));
    assert.equal((await db.query('select ends_at from events')).rows[0].ends_at, null);
  }
});


test('time precision backfill uses the originating assessment and preserves locks', async () => {
  const legacy = new PGlite();
  try {
    await legacy.exec('create role anon; create role authenticated; create role service_role bypassrls;');
    const backfillMigration = '20260922000000_event_duplicate_hosts.sql';
    for (const name of migrationNames.slice(0, migrationNames.indexOf(backfillMigration))) {
      await legacy.exec(await readFile(new URL(name, migrations), 'utf8'));
    }
    const entries = ['101', '102', '103'].map(media => {
      const event = row(`ig_club_p${media}`);
      return { ...update(`post:${media}`, [event]), assessment: { status: 'complete', result: {
        occurrences: [{ all_day: true, starts_at: event.starts_at }],
      } } };
    });
    await legacy.query('select reconcile_source_assessments($1::jsonb)', [JSON.stringify(entries)]);
    await legacy.exec("update events set is_locked=true where id='ig_club_p102'; update events set starts_at=starts_at + interval '1 hour' where id='ig_club_p103'");
    await legacy.exec(await readFile(new URL(backfillMigration, migrations), 'utf8'));
    const rows = (await legacy.query('select id,all_day,hosts from events order by id')).rows;
    assert.deepEqual(rows.map(r => r.all_day), [true, null, null]);
    assert.ok(rows.every(r => r.hosts.length === 0));
  } finally {
    await legacy.close();
  }
});
