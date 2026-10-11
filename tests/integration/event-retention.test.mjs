import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';
import { test } from 'node:test';

const { PGlite } = await import(process.env.PGLITE_MODULE || '@electric-sql/pglite');
const db = new PGlite();
const migrations = new URL('../../supabase/migrations/', import.meta.url);
await db.exec(`create role anon; create role authenticated; create role service_role bypassrls;
  create schema storage;
  create table storage.buckets(id text primary key, name text, public boolean,
    file_size_limit bigint, allowed_mime_types text[]);
  create table storage.objects(bucket_id text, name text, metadata jsonb,
    created_at timestamptz default now(), updated_at timestamptz default now());`);
for (const name of (await readdir(migrations)).filter(f => f.endsWith('.sql')).sort()) {
  await db.exec(await readFile(new URL(name, migrations), 'utf8'));
}
const ids = async () => (await db.query('select id from events order by id')).rows.map(r => r.id);
const reset = () => db.exec('truncate events, source_assessments, instagram_posts, storage.objects, submissions, stories');
const event = (id, start = "now()-interval '40 days'", extra = '') => db.exec(`
  insert into events(id,title,starts_at,source${extra ? ', '+extra.split('=')[0] : ''})
  values('${id}','Workshop',${start},'instagram'${extra ? ', '+extra.split('=').slice(1).join('=') : ''})`);

test('retirement is oldest-first and bounded; locks, manual, recent and ongoing events survive', async () => {
  await reset();
  for (let i = 0; i < 60; i++) await event(`ig_${i}`, `now()-interval '${100-i} days'`);
  await event('ig_locked', undefined, 'is_locked=true');
  await event('ig_recent', "now()-interval '2 days'");
  await event('ig_three_weeks', "now()-interval '21 days'");
  await event('ig_ongoing', undefined, 'ends_at=now()+interval \'1 day\'');
  await event('manual');
  await db.exec("update events set source='manual' where id='manual'");
  await db.exec(`insert into source_assessments(source_key,origin,assessment,event_ids,known_event_ids)
    values('instagram:post:1','instagram','{"status":"complete"}',
    array['ig_0','ig_59'],array['ig_0','ig_59'])`);
  assert.equal((await db.query('select retire_old_events() as n')).rows[0].n, 50);
  assert.ok(!(await ids()).includes('ig_0'));
  assert.ok((await ids()).includes('ig_59'));
  const source = (await db.query('select * from source_assessments')).rows[0];
  assert.deepEqual(source.event_ids, ['ig_59']);
  assert.deepEqual(source.known_event_ids, ['ig_0', 'ig_59']);
  assert.equal((await db.query('select retire_old_events() as n')).rows[0].n, 10);
  assert.deepEqual(await ids(), ['ig_locked', 'ig_ongoing', 'ig_recent', 'ig_three_weeks', 'manual']);
});

const oldAssessment = {status: 'complete', result: {kind: 'activity', occurrences: [{
  starts_at: '2000-01-01T12:00:00Z', ends_at: '2000-01-02T12:00:00Z'}]}};
const path = id => `instagram/club/posts/${id}/cover.jpg`;
const url = id => `https://example.supabase.co/storage/v1/object/public/event-flyers/${path(id)}`;
async function flyer(id, assessment = oldAssessment, fresh = false) {
  await db.query(`insert into instagram_posts(media_id,handle,posted_at,record)
    values($1,'club',now()-interval '60 days','{}')`, [id]);
  await db.query(`insert into source_assessments(source_key,origin,assessment)
    values($1,'instagram',$2::jsonb)`, [`instagram:post:${id}`, JSON.stringify(assessment)]);
  await db.query(`insert into storage.objects values('event-flyers',$1,'{"size":1234}',
    now()-interval '60 days',now()-$2::interval)`, [path(id), fresh ? '1 day' : '60 days']);
}
const candidates = async () => (await db.query('select * from old_event_flyers()')).rows.map(r => r.name);

test('only unused finished files qualify; future sessions, source ownership and other references protect them', async () => {
  await reset();
  await flyer('old');
  await flyer('negative', {status: 'complete', result: {kind: 'announcement'}});
  await flyer('negative_three_weeks', {status: 'complete', result: {kind: 'announcement'}});
  await db.exec(`update storage.objects set created_at=now()-interval '21 days',
    updated_at=now()-interval '21 days' where name='${path('negative_three_weeks')}'`);
  await flyer('future', {status: 'complete', result: {kind: 'activity', occurrences: [
    ...oldAssessment.result.occurrences, {starts_at: '2099-01-01T00:00:00Z'}]}});
  await flyer('error', {status: 'error', result: oldAssessment.result});
  await flyer('unknown', {status: 'complete', result: {kind: 'uncertain'}});
  await flyer('bad-date', {status: 'complete', result: {kind: 'activity', occurrences: [{starts_at: 'bad'}]}});
  await flyer('fresh', oldAssessment, true);
  await flyer('shared');
  await event('ig_kept', "now()+interval '1 day'");
  await db.exec(`update source_assessments set event_ids=array['ig_kept'] where source_key='instagram:post:shared'`);
  await flyer('referenced');
  await db.query('update events set image_url=$1 where id=$2', [url('referenced'), 'ig_kept']);
  await flyer('submission');
  await db.query(`insert into submissions(title,starts_at,host,submitter_name,submitter_email,image_url)
    values('Review',now(),'Club','Name','name@example.com',$1)`, [url('submission')]);
  await flyer('story');
  await db.query(`insert into stories(id,handle,posted_at,image_url) values('s','club',now(),$1)`, [url('story')]);
  await db.exec(`insert into storage.objects values('submission-flyers','external.jpg','{"size":1}',
    now()-interval '60 days',now()-interval '60 days')`);
  assert.deepEqual((await candidates()).sort(), [path('negative'), path('negative_three_weeks'), path('old')]);
  // Candidate reads leave physical object metadata intact for API retries.
  assert.equal((await db.query('select count(*)::int n from storage.objects')).rows[0].n, 13);
});

test('schedule retention uses the full final Pacific day and public callers cannot execute cleanup', async () => {
  const check = async last_day => (await db.query('select retention_source_finished($1::jsonb,$2) ok', [
    JSON.stringify({status:'complete', result:{kind:'service_schedule', schedule:{last_day}}}),
    '2026-10-01T07:00:00Z'])).rows[0].ok;
  assert.equal(await check('2026-09-30'), false);
  assert.equal(await check('2026-09-29'), true);
  assert.equal(await check('bad'), false);
  for (const role of ['anon', 'authenticated']) {
    await db.exec(`set role ${role}`);
    try {
      await assert.rejects(db.query('select retire_old_events()'), {code:'42501'});
      await assert.rejects(db.query('select * from old_event_flyers()'), {code:'42501'});
    } finally { await db.exec('reset role'); }
  }
});
