import assert from 'node:assert/strict';
import { test } from 'node:test';
import { registerHooks } from 'node:module';
import { importTsModule } from './helpers/import-ts-module.mjs';

// unstable_cache keys an entry by its keyParts plus the serialized call args.
// Record those args to check that day-relative reads key on today's date.
process.env.NEXT_PUBLIC_SUPABASE_URL = 'https://cache-key-test.supabase.co';
process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = 'test';
delete process.env.HIGHLANDERHUB_E2E_FIXTURES;
globalThis.__cacheCalls = [];
const unstableCache = 'export const unstable_cache = (fn, keyParts) => (...args) => {'
  + ' globalThis.__cacheCalls.push({ key: keyParts[0], args: JSON.stringify(args) }); return fn(...args); };';
const hook = registerHooks({ resolve(specifier, context, next) {
  if (specifier === 'next/cache') return { url: `data:text/javascript,${encodeURIComponent(unstableCache)}`, shortCircuit: true };
  if (specifier === 'react') return { url: 'data:text/javascript,export const cache = (fn) => fn;', shortCircuit: true };
  return next(specifier, context);
} });
const events = await importTsModule('src/lib/events/index.ts');
hook.deregister();

function emptyDb(t) {
  t.mock.method(globalThis, 'fetch', async () => new Response('[]', {
    status: 200,
    headers: { 'Content-Type': 'application/json', 'Content-Range': '*/0' },
  }));
}

async function keyOn(t, instant, read) {
  globalThis.__cacheCalls = [];
  t.mock.timers.enable({ apis: ['Date'], now: Date.parse(instant) });
  await read();
  t.mock.timers.reset();
  return globalThis.__cacheCalls.map(call => `${call.key} ${call.args}`);
}

test('the Today feed is cached per Pacific day, not reused the next morning', async t => {
  emptyDb(t);
  const read = () => events.getEventsPage({ dayWindow: 'today' });
  // 11:30 PM and 12:30 AM Pacific (PST) on either side of midnight.
  const lateNight = await keyOn(t, '2026-11-05T07:30:00Z', read);
  const nextMorning = await keyOn(t, '2026-11-05T08:30:00Z', read);
  assert.match(lateNight[0], /"todayKey":"2026-11-04"/);
  assert.match(nextMorning[0], /"todayKey":"2026-11-05"/);
  // A caller's own todayKey still wins.
  const pinned = await keyOn(t, '2026-11-05T08:30:00Z', () => events.getEventsPage({ todayKey: '2026-12-01' }));
  assert.match(pinned[0], /"todayKey":"2026-12-01"/);
});

test('the this-week count is cached per Pacific day', async t => {
  emptyDb(t);
  const saturday = await keyOn(t, '2026-11-08T07:30:00Z', () => events.getEventsUpcomingThisWeek());
  const sunday = await keyOn(t, '2026-11-08T08:30:00Z', () => events.getEventsUpcomingThisWeek());
  assert.deepEqual(saturday, ['events-upcoming-this-week ["2026-11-07"]']);
  assert.deepEqual(sunday, ['events-upcoming-this-week ["2026-11-08"]']);
});
