import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { after, test } from 'node:test';

const { PGlite } = await import(process.env.PGLITE_MODULE || '@electric-sql/pglite');
const db = new PGlite();
await db.exec('create role anon; create role authenticated; create role service_role bypassrls;');
await db.exec(await readFile(new URL('../../supabase/migrations/20260921000000_vision_ocr_usage.sql', import.meta.url), 'utf8'));
await db.exec(await readFile(new URL('../../supabase/migrations/20260925000000_add_vision_ocr_keys.sql', import.meta.url), 'utf8'));
after(() => db.close());

const month = "date_trunc('month', current_timestamp at time zone 'America/Los_Angeles')::date";
const reserve = async () => (await db.query('select public.reserve_vision_ocr_request() as result')).rows[0].result;
const reserveExtra = async (secondary = true, tertiary = true) => (
  await db.query('select public.reserve_vision_ocr_request($1::boolean, $2::boolean) as result', [secondary, tertiary])
).rows[0].result;

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
      await assert.rejects(() => reserveExtra(), /permission denied/);
      await assert.rejects(db.query('select * from public.vision_ocr_usage'), /permission denied/);
      await assert.rejects(db.query('update public.vision_ocr_usage set primary_requests = 0'), /permission denied/);
    } finally {
      await db.exec('reset role');
    }
  }
  await db.exec('set role service_role');
  try {
    assert.equal((await reserve()).slot, 'overflow');
    assert.equal((await reserveExtra()).slot, 'secondary');
  } finally {
    await db.exec('reset role');
  }
});

test('extra slots each reserve 1000 attempts before uncapped overflow', async () => {
  await db.exec('truncate public.vision_ocr_usage');
  await db.exec(`insert into public.vision_ocr_usage (month, primary_requests) values (${month}, 999)`);
  assert.equal((await reserveExtra()).slot, 'primary');
  assert.equal((await reserveExtra()).slot, 'secondary');
  await db.exec('update public.vision_ocr_usage set secondary_requests = 999');
  assert.equal((await reserveExtra()).used, 1000);
  assert.equal((await reserveExtra()).slot, 'tertiary');
  await db.exec('update public.vision_ocr_usage set tertiary_requests = 999');
  assert.equal((await reserveExtra()).used, 1000);
  assert.equal((await reserveExtra()).slot, 'overflow');
  await db.exec('update public.vision_ocr_usage set overflow_requests = 1000');
  assert.deepEqual(await reserveExtra(), {
    month: (await db.query(`select to_char(${month}, 'YYYY-MM-DD') as month`)).rows[0].month,
    slot: 'overflow', used: 1001,
  });
});

test('adding, disabling and re-enabling optional slots preserves prior usage', async () => {
  await db.exec('truncate public.vision_ocr_usage');
  await db.exec(`insert into public.vision_ocr_usage (month, primary_requests, overflow_requests) values (${month}, 1000, 2500)`);
  assert.equal((await reserveExtra(false, false)).used, 2501);
  assert.equal((await reserveExtra(false, true)).slot, 'tertiary');
  assert.equal((await reserveExtra(true, false)).slot, 'secondary');
  assert.equal((await reserve()).used, 2502);
  assert.equal((await reserveExtra()).used, 2);
  assert.equal((await reserveExtra(false, true)).used, 2);
  assert.deepEqual((await db.query('select primary_requests, secondary_requests, tertiary_requests, overflow_requests::int from public.vision_ocr_usage')).rows[0], {
    primary_requests: 1000, secondary_requests: 2, tertiary_requests: 2, overflow_requests: 2502,
  });
});

test('multiple callers consume each last optional allowance once', async () => {
  for (const slot of ['secondary', 'tertiary']) {
    await db.exec('truncate public.vision_ocr_usage');
    await db.exec(`insert into public.vision_ocr_usage (month, primary_requests, secondary_requests, tertiary_requests)
      values (${month}, 1000, ${slot === 'secondary' ? 999 : 1000}, ${slot === 'tertiary' ? 999 : 0})`);
    const results = await Promise.all(Array.from({ length: 10 }, () => reserveExtra()));
    assert.equal(results.filter(r => r.slot === slot).length, 1);
    const next = slot === 'secondary' ? 'tertiary' : 'overflow';
    assert.deepEqual(results.filter(r => r.slot === next).map(r => r.used), [1, 2, 3, 4, 5, 6, 7, 8, 9]);
  }
});

test('a new month resets all allowances without deleting previous counts', async () => {
  await db.exec('truncate public.vision_ocr_usage');
  await db.exec(`insert into public.vision_ocr_usage (month, primary_requests, secondary_requests, tertiary_requests, overflow_requests)
    values ((${month} - interval '1 month')::date, 1000, 1000, 1000, 2500)`);
  assert.equal((await reserveExtra()).slot, 'primary');
  await db.exec(`update public.vision_ocr_usage set primary_requests = 1000 where month = ${month}`);
  assert.equal((await reserveExtra()).used, 1);
  assert.equal((await db.query('select count(*)::int as count from public.vision_ocr_usage')).rows[0].count, 2);
});
