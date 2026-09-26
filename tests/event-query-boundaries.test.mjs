import assert from 'node:assert/strict';
import { test } from 'node:test';
import { registerHooks } from 'node:module';
import { importTsModule } from './helpers/import-ts-module.mjs';

process.env.NEXT_PUBLIC_SUPABASE_URL = 'https://query-test.supabase.co';
process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = 'test';
delete process.env.HIGHLANDERHUB_E2E_FIXTURES;
const hook = registerHooks({ resolve(specifier, context, next) {
  if (specifier === 'next/cache') return { url: 'data:text/javascript,export const unstable_cache = (fn) => fn;', shortCircuit: true };
  return next(specifier, context);
} });
const events = await importTsModule('src/lib/events/index.ts');
hook.deregister();

const source = Array.from({ length: 1101 }, (_, i) => ({
  id: `ig_${String(i).padStart(4, '0')}`, title: i === 1100 ? 'Boundary Match' : `Event ${i}`,
  description: '', starts_at: '2027-05-25T18:00:00Z', ends_at: '2027-05-25T20:00:00Z',
  location: 'HUB', host: 'Club', host_handle: 'club', hosts: [], category: i % 2 ? 'academic' : 'social',
  content_kind: 'student_event', tags: [], has_free_food: i === 1100,
  source: 'instagram', rsvp_required: false, scraped_at: '2026-09-26T00:00:00Z',
}));
function installApi(t, cap = 1000) {
  const requests = [];
  t.mock.method(globalThis, 'fetch', async (input) => {
    const url = new URL(input instanceof Request ? input.url : input);
    const p = url.searchParams;
    assert.equal(p.get('order'), 'starts_at.asc,id.asc');
    assert.equal(p.get('content_kind'), 'in.(student_event,student_deadline)');
    let rows = source;
    if (p.has('id')) {
      const ids = p.get('id').slice(4, -1).split(',');
      rows = rows.filter(row => ids.includes(row.id));
    }
    if (p.has('category')) rows = rows.filter(row => `eq.${row.category}` === p.get('category'));
    if (p.getAll('or').some(value => value.includes('has_free_food'))) {
      rows = rows.filter(row => row.has_free_food || row.category === 'free_food');
    }
    for (const condition of p.getAll('starts_at')) {
      const [operator, ...value] = condition.split('.');
      rows = rows.filter(row => operator === 'gte' ? row.starts_at >= value.join('.') : row.starts_at < value.join('.'));
    }
    const offset = Number(p.get('offset') ?? 0);
    const limit = Math.min(Number(p.get('limit') ?? cap), cap);
    rows = rows.slice(offset, offset + limit);
    if (p.get('select') !== '*') {
      const fields = p.get('select').split(',');
      rows = rows.map(row => Object.fromEntries(fields.map(key => [key, row[key]])));
    }
    requests.push({ params: p, rows: rows.length, bytes: Buffer.byteLength(JSON.stringify(rows)) });
    return new Response(JSON.stringify(rows), { status: 200, headers: { 'Content-Type': 'application/json' } });
  });
  return requests;
}

test('search finds a row beyond the response cap and hydrates only its page', async t => {
  const requests = installApi(t, 1000);
  const page = await events.getEventsPage({ query: 'Boundary Match' });
  assert.deepEqual(page.events.map(row => row.id), ['ig_1100']);
  assert.equal(page.hasMore, false);
  assert.equal(requests.filter(r => r.params.get('select') === '*').reduce((n, r) => n + r.rows, 0), 1);
  assert.equal(requests.filter(r => r.params.get('select') !== '*').reduce((n, r) => n + r.rows, 0), 1101);
});

test('category and date filters precede page ranges, including free food', async t => {
  const requests = installApi(t);
  const first = await events.getEventsPage({ category: 'social', limit: 24 });
  const second = await events.getEventsPage({ category: 'social', offset: 24, limit: 24 });
  assert.equal(first.events.length, 24);
  assert.equal(first.hasMore, true);
  assert.equal(new Set([...first.events, ...second.events].map(row => row.id)).size, 48);
  assert.equal(requests.reduce((n, r) => n + r.rows, 0), 50);
  const food = await events.getEventsPage({ category: 'free_food', dayWindow: 'today', todayKey: '2027-05-25' });
  assert.deepEqual(food.events.map(row => row.id), ['ig_1100']);
  assert.ok(requests.at(-1).params.getAll('starts_at').length === 2);
  t.diagnostic(`Two category pages: 50 rows, ${requests.slice(0, 2).reduce((n, r) => n + r.bytes, 0)} JSON bytes`);
});

test('counts and calendars exhaust even a server cap smaller than the batch', async t => {
  installApi(t, 137);
  assert.equal((await events.getEventFilterCountSource()).length, 1101);
  assert.equal((await events.getCalendarEvents({ startDayKey: '2027-05-01', endDayKey: '2027-05-31' })).length, 1101);
});

test('a failed continuation rejects the entire count result', async t => {
  installApi(t, 137);
  const fetch = globalThis.fetch;
  t.mock.method(globalThis, 'fetch', async (...args) => {
    const url = new URL(args[0]);
    if (Number(url.searchParams.get('offset')) > 0) {
      return new Response(JSON.stringify({ message: 'offline' }), { status: 500 });
    }
    return fetch(...args);
  });
  await assert.rejects(events.getEventFilterCountSource(), /Unable to load event filter counts/);
});

test('events-only header requests one exact count without event payloads', async t => {
  const requests = [];
  t.mock.method(globalThis, 'fetch', async (input, init) => {
    const url = new URL(input);
    requests.push(url);
    assert.equal(init.method, 'HEAD');
    assert.equal(url.searchParams.get('select'), 'id');
    assert.equal(url.searchParams.getAll('starts_at').length, 2);
    return new Response(null, { headers: { 'content-range': '*/7' } });
  });
  assert.equal(await events.getEventsUpcomingThisWeek(), 7);
  assert.equal(requests.length, 1);
});
