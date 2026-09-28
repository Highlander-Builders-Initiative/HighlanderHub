// Run with PGLITE_MODULE pointing to @electric-sql/pglite's ESM entrypoint.
// Applies the activity-category migrations the way the Supabase editor would:
// the enum values in one run, the backfill in the next.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';

const { PGlite } = await import(process.env.PGLITE_MODULE || '@electric-sql/pglite');
const migrations = new URL('../../supabase/migrations/', import.meta.url);
const db = new PGlite();
await db.exec('create role anon; create role authenticated; create role service_role bypassrls;');
for (const name of ['20260513073310_init_schema.sql', '20260527000000_add_event_lock.sql',
  '20260531000000_event_has_free_food.sql']) {
  await db.exec(await readFile(new URL(name, migrations), 'utf8'));
}

async function insert(id, category, extra = '') {
  await db.query(`insert into events(id, title, starts_at, source, category${extra ? ', is_locked' : ''})
    values ($1, $1, '2026-10-01T18:00:00Z', 'instagram', $2${extra ? `, ${extra}` : ''})`, [id, category]);
}

test('legacy categories retire into activities; new rows default to other', async () => {
  for (const [id, category] of [['club', 'club'], ['social', 'social'], ['community', 'community'],
    ['food', 'free_food'], ['arts', 'arts']]) {
    await insert(id, category);
  }
  await insert('locked', 'community', 'true');

  await db.exec(await readFile(new URL('20260928000000_activity_categories.sql', migrations), 'utf8'));
  await db.exec(await readFile(new URL('20260928010000_activity_categories_backfill.sql', migrations), 'utf8'));

  const { rows } = await db.query('select id, category, has_free_food from events order by id');
  assert.deepEqual(Object.fromEntries(rows.map((row) => [row.id, row.category])), {
    arts: 'arts', club: 'other', community: 'other', food: 'other', locked: 'other', social: 'hangout',
  });
  assert.equal(rows.find((row) => row.id === 'food').has_free_food, true);
  assert.equal(rows.find((row) => row.id === 'club').has_free_food, false);

  await db.query(`insert into events(id, title, starts_at, source) values ('new', 'new', now(), 'instagram')`);
  const { rows: [fresh] } = await db.query(`select category from events where id = 'new'`);
  assert.equal(fresh.category, 'other');
  for (const category of ['hangout', 'get_involved', 'volunteering', 'other']) {
    await db.query(`select $1::event_category`, [category]);
  }
});
