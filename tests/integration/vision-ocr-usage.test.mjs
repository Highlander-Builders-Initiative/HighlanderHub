import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { after, test } from 'node:test';

const { PGlite } = await import(process.env.PGLITE_MODULE || '@electric-sql/pglite');
const db = new PGlite();
await db.exec('create role anon; create role authenticated; create role service_role bypassrls;');
await db.exec(await readFile(new URL('../../supabase/migrations/20260921000000_vision_ocr_usage.sql', import.meta.url), 'utf8'));
after(() => db.close());

const month = "date_trunc('month', current_timestamp at time zone 'America/Los_Angeles')::date";
const reserve = async () => (await db.query('select public.reserve_vision_ocr_request() as result')).rows[0].result;

test('1000th attempt stays on primary; overflow continues beyond its 1000th attempt', async () => {
  await db.exec('truncate public.vision_ocr_usage');
  assert.deepEqual(await reserve(), {
    month: (await db.query(`select to_char(${month}, 'YYYY-MM-DD') as month`)).rows[0].month,
    slot: 'primary', used: 1,
  });
  await db.exec('update public.vision_ocr_usage set primary_requests = 999');
  assert.equal((await reserve()).slot, 'primary');
  assert.deepEqual((await reserve()).used, 1);
  await db.exec('update public.vision_ocr_usage set overflow_requests = 1000');
  const overflow = await reserve();
  assert.equal(overflow.slot, 'overflow');
  assert.equal(overflow.used, 1001);
  assert.equal((await db.query('select primary_requests from public.vision_ocr_usage')).rows[0].primary_requests, 1000);
});

test('a spent previous month does not consume the new month allowance', async () => {
  await db.exec('truncate public.vision_ocr_usage');
  await db.exec(`insert into public.vision_ocr_usage values ((${month} - interval '1 month')::date, 1000, 2500)`);
  const current = await reserve();
  assert.equal(current.slot, 'primary');
  assert.equal(current.used, 1);
  assert.equal((await db.query('select count(*)::int as count from public.vision_ocr_usage')).rows[0].count, 2);
});

test('multiple callers consume the last primary slot once', async () => {
  await db.exec('truncate public.vision_ocr_usage');
  await db.exec(`insert into public.vision_ocr_usage values (${month}, 999, 0)`);
  const results = await Promise.all(Array.from({ length: 10 }, reserve));
  assert.equal(results.filter(r => r.slot === 'primary').length, 1);
  assert.deepEqual(results.filter(r => r.slot === 'overflow').map(r => r.used), [1, 2, 3, 4, 5, 6, 7, 8, 9]);
});

test('public clients cannot view or change usage; service role can reserve', async () => {
  for (const role of ['anon', 'authenticated']) {
    await db.exec(`set role ${role}`);
    try {
      await assert.rejects(reserve, /permission denied/);
      await assert.rejects(db.query('select * from public.vision_ocr_usage'), /permission denied/);
      await assert.rejects(db.query('update public.vision_ocr_usage set primary_requests = 0'), /permission denied/);
    } finally {
      await db.exec('reset role');
    }
  }
  await db.exec('set role service_role');
  try {
    assert.equal((await reserve()).slot, 'overflow');
  } finally {
    await db.exec('reset role');
  }
});
