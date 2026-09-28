import assert from 'node:assert/strict';
import { test } from 'node:test';
import { registerHooks } from 'node:module';
import { importTsModule } from './helpers/import-ts-module.mjs';

process.env.NEXT_PUBLIC_SUPABASE_URL = 'https://query-test.supabase.co';
process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = 'test';
delete process.env.HIGHLANDERHUB_E2E_FIXTURES;
const hook = registerHooks({ resolve(specifier, context, next) {
  if (specifier === 'next/cache') return { url: 'data:text/javascript,export const unstable_cache = (fn) => fn;', shortCircuit: true };
  if (specifier === 'next/server') return { url: 'data:text/javascript,export const NextResponse = { json: (body, init) => Response.json(body, init) };', shortCircuit: true };
  // The installed react (18) only exports cache() under Next's vendored React 19.
  if (specifier === 'react') return { url: 'data:text/javascript,export const cache = (fn) => fn;', shortCircuit: true };
  return next(specifier, context);
} });
const events = await importTsModule('src/lib/events/index.ts');
const calendarRoute = await importTsModule('src/app/api/events/calendar/route.ts');
const eventsRoute = await importTsModule('src/app/api/events/route.ts');
const eventsApi = await importTsModule('src/lib/events/api.ts');
hook.deregister();

const source = Array.from({ length: 1101 }, (_, i) => ({
  id: `ig_${String(i).padStart(4, '0')}`, title: i === 1100 ? 'Boundary Match' : `Event ${i}`,
  description: '', starts_at: '2027-05-25T18:00:00Z', ends_at: '2027-05-25T20:00:00Z',
  location: 'HUB', host: 'Club', host_handle: i === 1099 ? 'aacfucriverside' : 'club', hosts: [],
  category: i % 2 ? 'academic' : 'hangout',
  content_kind: i === 1098 ? 'student_deadline' : 'student_event', tags: [], has_free_food: i === 1100,
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
    if (p.has('has_free_food')) rows = rows.filter(row => `eq.${row.has_free_food}` === p.get('has_free_food'));
    for (const kind of p.getAll('content_kind').filter(value => value.startsWith('eq.'))) {
      rows = rows.filter(row => `eq.${row.content_kind}` === kind);
    }
    for (const value of p.getAll('or')) {
      const after = /^\(starts_at\.gt\."(.+)",and\(starts_at\.eq\."(.+)",id\.gt\."(.+)"\)\)$/.exec(value);
      if (after) rows = rows.filter(row => row.starts_at > after[1] || (row.starts_at === after[2] && row.id > after[3]));
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

test('search pages stay disjoint when a matched row ends before hydration', async t => {
  const requests = installApi(t);
  const fetch = globalThis.fetch;
  t.mock.method(globalThis, 'fetch', async (...args) => {
    const response = await fetch(...args);
    const url = new URL(args[0] instanceof Request ? args[0].url : args[0]);
    if (!url.searchParams.has('id')) return response;
    // The cached count source still lists ig_0003; the live read no longer does.
    const rows = (await response.json()).filter(row => row.id !== 'ig_0003');
    return new Response(JSON.stringify(rows), { status: 200, headers: { 'Content-Type': 'application/json' } });
  });
  const first = await events.getEventsPage({ query: 'event', limit: 24 });
  const second = await events.getEventsPage({ query: 'event', after: first.cursor, limit: 24 });
  const firstIds = first.events.map(row => row.id);
  assert.deepEqual(firstIds.filter(id => second.events.some(row => row.id === id)), []);
  assert.deepEqual(first.cursor, { startsAt: '2027-05-25T18:00:00Z', id: 'ig_0023' });
  assert.equal(second.events[0].id, 'ig_0024');
  // Each page hydrates exactly its own ids, never the next page's first row.
  const hydrated = requests.filter(r => r.params.has('id')).map(r => r.params.get('id').slice(4, -1).split(','));
  assert.ok(hydrated.every(ids => ids.length === 24));
  assert.ok(!hydrated[0].includes('ig_0024'));
});

test('events that end between page reads do not shift later events out of the feed', async t => {
  // Five early events end at 12:00; the rest stay active. Page one is read
  // just before, page two just after: a position count would skip five.
  const rows = Array.from({ length: 60 }, (_, i) => ({
    ...source[i], id: `ev_${String(i).padStart(2, '0')}`,
    starts_at: new Date(Date.UTC(2027, 0, 1, 10, i)).toISOString(),
    ends_at: i < 5 ? '2027-01-01T12:00:00.000Z' : '2027-01-02T12:00:00.000Z',
  }));
  t.mock.method(globalThis, 'fetch', async (input) => {
    const p = new URL(input).searchParams;
    let page = rows;
    for (const filter of p.getAll('or')) {
      const active = /^\(ends_at\.gte\.([^,]+),/.exec(filter);
      if (active) page = page.filter(row => row.ends_at >= active[1]);
      const after = /^\(starts_at\.gt\."(.+)",and\(starts_at\.eq\."(.+)",id\.gt\."(.+)"\)\)$/.exec(filter);
      if (after) page = page.filter(row => row.starts_at > after[1] || (row.starts_at === after[2] && row.id > after[3]));
    }
    const offset = Number(p.get('offset') ?? 0);
    page = page.slice(offset, offset + Number(p.get('limit') ?? 1000));
    return new Response(JSON.stringify(page), { status: 200, headers: { 'Content-Type': 'application/json' } });
  });
  t.mock.timers.enable({ apis: ['Date'], now: Date.parse('2027-01-01T11:58:00Z') });
  const first = await events.getEventsPage({ limit: 24 });
  t.mock.timers.setTime(Date.parse('2027-01-01T12:02:00Z'));
  const second = await events.getEventsPage({ after: first.cursor, limit: 24 });
  const shown = new Set([...first.events, ...second.events].map(row => row.id));
  assert.deepEqual(rows.slice(5, 48).map(row => row.id).filter(id => !shown.has(id)), []);
  assert.deepEqual(first.cursor, { startsAt: rows[23].starts_at, id: 'ev_23' });
  assert.equal(second.events[0].id, 'ev_24');
});

test('the events API rejects a cursor it cannot read instead of starting over', async t => {
  const requests = installApi(t);
  // Page one would carry an equally unreadable cursor back: the feed would never advance.
  for (const query of ['after=yesterday&afterId=ig_0001', 'after=2027-05-25T18:00:00Z', 'afterId=ig_0001']) {
    const response = await eventsRoute.GET(new Request(`https://hub.test/api/events?${query}`));
    assert.equal(response.status, 400, query);
  }
  assert.equal(requests.length, 0);
  const next = await eventsRoute.GET(new Request('https://hub.test/api/events?after=2027-05-25T18:00:00Z&afterId=ig_0001&limit=2'));
  assert.deepEqual((await next.json()).events.map(event => event.id), ['ig_0002', 'ig_0003']);
});

test('the calendar API reads at most one six-week grid', async t => {
  const requests = installApi(t);
  const huge = await calendarRoute.GET(new Request('https://hub.test/api/events/calendar?start=2000-01-01&end=2100-12-31'));
  assert.equal(huge.status, 200);
  const [gte, lt] = requests[0].params.getAll('starts_at');
  assert.match(gte, /^gte\.2000-01-01T/);
  assert.match(lt, /^lt\.2000-02-12T/);
  // A well-formed but impossible date falls back like any other unusable value.
  const invalid = await calendarRoute.GET(new Request('https://hub.test/api/events/calendar?start=2026-99-99&end=2026-10-01'));
  assert.equal(invalid.status, 200);
});

test('a calendar range longer than a grid is fetched in contiguous grid-sized requests', async t => {
  const ranges = [];
  t.mock.method(globalThis, 'fetch', async (input) => {
    const url = new URL(input, 'https://hub.test');
    ranges.push([url.searchParams.get('start'), url.searchParams.get('end')]);
    return new Response(JSON.stringify({ events: [{ id: url.searchParams.get('start') }] }), { status: 200 });
  });
  const events = await eventsApi.fetchCalendarRange('2026-09-28', '2026-12-31');
  assert.deepEqual(ranges, [
    ['2026-09-28', '2026-11-08'],
    ['2026-11-09', '2026-12-20'],
    ['2026-12-21', '2026-12-31'],
  ]);
  assert.deepEqual(events.map(event => event.id), ['2026-09-28', '2026-11-09', '2026-12-21']);
});

test('category and date filters precede page ranges, including free food', async t => {
  const requests = installApi(t);
  const first = await events.getEventsPage({ category: 'hangout', limit: 24 });
  const second = await events.getEventsPage({ category: 'hangout', after: first.cursor, limit: 24 });
  assert.equal(first.events.length, 24);
  assert.equal(first.hasMore, true);
  assert.equal(new Set([...first.events, ...second.events].map(row => row.id)).size, 48);
  assert.equal(requests.reduce((n, r) => n + r.rows, 0), 50);
  const food = await events.getEventsPage({ freeFood: true, dayWindow: 'today', todayKey: '2027-05-25' });
  assert.deepEqual(food.events.map(row => row.id), ['ig_1100']);
  assert.ok(requests.at(-1).params.getAll('starts_at').length === 2);
  // Free food narrows a topic rather than replacing it.
  const hangoutFood = await events.getEventsPage({ category: 'hangout', freeFood: true });
  assert.deepEqual(hangoutFood.events.map(row => row.id), ['ig_1100']);
  const deadlines = await events.getEventsPage({ deadlines: true });
  assert.deepEqual(deadlines.events.map(row => row.id), ['ig_1098']);
  t.diagnostic(`Two category pages: 50 rows, ${requests.slice(0, 2).reduce((n, r) => n + r.bytes, 0)} JSON bytes`);
});

test('Hosted by pages through the shared source, like search', async t => {
  installApi(t);
  const faith = await events.getEventsPage({ hostGroup: 'faith' });
  assert.deepEqual(faith.events.map(row => row.id), ['ig_1099']);
  assert.equal(faith.hasMore, false);
  const faithRoute = await eventsRoute.GET(new Request('https://hub.test/api/events?host=faith'));
  assert.deepEqual((await faithRoute.json()).events.map(row => row.id), ['ig_1099']);
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
