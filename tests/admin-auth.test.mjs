import assert from 'node:assert/strict';
import { test } from 'node:test';
import { registerHooks } from 'node:module';
import { importTsModule } from './helpers/import-ts-module.mjs';

process.env.NEXT_PUBLIC_SUPABASE_URL = 'https://admin-test.supabase.co';
process.env.SUPABASE_SERVICE_ROLE_KEY = 'test-service-key';
process.env.ADMIN_PASSWORD = 'a-long-random-test-password-only';
const state = { session: undefined, sets: [] };
globalThis.__adminSecurityTest = state;
const stub = source => ({ url: `data:text/javascript,${encodeURIComponent(source)}`, shortCircuit: true });
const hooks = registerHooks({ resolve(specifier, context, next) {
  if (specifier === 'server-only') return stub('export {}');
  if (specifier === 'next/headers') return stub(`
    export const cookies = async () => ({
      get: () => ({ value: globalThis.__adminSecurityTest.session }),
      set: (...args) => globalThis.__adminSecurityTest.sets.push(args)
    });
    export const headers = async () => new Headers({ 'x-forwarded-for': '203.0.113.5' });`);
  if (specifier === 'next/cache') return stub('export const revalidatePath = () => {}; export const revalidateTag = () => {};');
  if (/\/src\/lib\/events\/index\.[^/]+\.mjs$/.test(specifier)) return stub('export const EVENTS_CACHE_TAG = "events";');
  return next(specifier, context);
} });
const admin = await importTsModule('src/lib/admin.ts');
const actions = await importTsModule('src/app/admin/actions.ts');
hooks.deregister();

test('admin sessions reject expiry, tampering, malformed encodings and password rotation', t => {
  t.mock.method(Date, 'now', () => 1790640000000);
  const session = admin.signSession(Date.now() + 60_000);
  assert.equal(admin.verifySession(session), true);
  for (const value of [undefined, '', session + 'ff', session + 'garbage', session.replace('.', 'x.'),
    `${Date.now() + 120_000}.${session.split('.')[1]}`, admin.signSession(Date.now()), admin.signSession(Date.now() - 1)]) {
    assert.equal(admin.verifySession(value), false);
  }
  const password = process.env.ADMIN_PASSWORD;
  try {
    process.env.ADMIN_PASSWORD = 'different-test-password';
    assert.equal(admin.verifySession(session), false);
    delete process.env.ADMIN_PASSWORD;
    assert.equal(admin.verifySession(session), false);
    assert.equal(admin.verifyPassword(password), false);
  } finally { process.env.ADMIN_PASSWORD = password; }
  for (const value of [null, {}, [], 42, 'x'.repeat(1025)]) assert.equal(admin.verifyPassword(value), false);
});

test('every admin mutation refuses unauthenticated requests before any database call', async t => {
  state.session = undefined;
  const fetch = t.mock.method(globalThis, 'fetch', () => { throw new Error('Unexpected database call'); });
  for (const invoke of [() => actions.updateEvent('event', {}), () => actions.deleteEvent('event'),
    () => actions.mergeDuplicateEvents('a', 'b', {}), () => actions.markEventsDifferent('a', 'b')]) {
    await assert.rejects(invoke(), /Unauthorized/);
  }
  assert.equal(fetch.mock.callCount(), 0);
});

test('login fails closed when the shared limiter denies, fails or returns malformed data', async t => {
  state.sets = [];
  let reply = { ok: false, retry_after_seconds: 600 };
  const fetch = t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.ok(String(url).endsWith('/rpc/check_admin_login_rate_limit'));
    const body = JSON.parse(options.body);
    assert.match(body.p_key, /^[a-f0-9]{64}$/);
    assert.equal(JSON.stringify(body).includes('203.0.113.5'), false);
    return Response.json(reply);
  });
  assert.equal((await actions.loginAdmin(process.env.ADMIN_PASSWORD)).success, false);
  reply = { error: 'bad response' };
  assert.equal((await actions.loginAdmin(process.env.ADMIN_PASSWORD)).success, false);
  fetch.mock.mockImplementation(async () => Response.json({ message: 'unavailable' }, { status: 503 }));
  assert.equal((await actions.loginAdmin(process.env.ADMIN_PASSWORD)).success, false);
  assert.equal(state.sets.length, 0);
});

test('successful login requires a durable reservation and sets a protected cookie', async t => {
  state.sets = [];
  t.mock.method(globalThis, 'fetch', async () => Response.json({ ok: true, retry_after_seconds: 0 }));
  assert.equal((await actions.loginAdmin({ password: process.env.ADMIN_PASSWORD })).success, false);
  assert.equal(state.sets.length, 0);
  assert.equal((await actions.loginAdmin(process.env.ADMIN_PASSWORD)).success, true);
  assert.equal(state.sets[0][0], 'hh_admin_session');
  assert.equal(admin.verifySession(state.sets[0][1]), true);
  assert.equal(state.sets[0][2].httpOnly, true);
  assert.equal(state.sets[0][2].sameSite, 'strict');
});
