import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';
import { test } from 'node:test';

const { PGlite } = await import(process.env.PGLITE_MODULE || '@electric-sql/pglite');
const migrations = new URL('../../supabase/migrations/', import.meta.url);

test('full migration history preserves public reads and denies client writes and private RPCs', async () => {
  const db = new PGlite();
  const asRole = async (role, sql, params = []) => {
    await db.exec(`set role ${role}`);
    try { return await db.query(sql, params); }
    finally { await db.exec('reset role'); }
  };
  try {
    // Match Supabase's broad original defaults so omitted revocations are visible.
    await db.exec(`
      create role anon; create role authenticated; create role service_role bypassrls;
      grant usage on schema public to anon, authenticated, service_role;
      alter default privileges in schema public grant all on tables to anon, authenticated, service_role;
      alter default privileges in schema public grant all on sequences to anon, authenticated, service_role;
      alter default privileges in schema public grant execute on functions to anon, authenticated, service_role;
      create schema storage;
      create table storage.buckets (id text primary key, name text, public boolean,
        file_size_limit bigint, allowed_mime_types text[]);
      create table storage.objects (bucket_id text, name text);
      alter table storage.objects enable row level security;
      grant usage on schema storage to anon, authenticated, service_role;
      grant all on storage.objects to anon, authenticated, service_role;
    `);
    for (const file of (await readdir(migrations)).filter(f => f.endsWith('.sql')).sort()) {
      try { await db.exec(await readFile(new URL(file, migrations), 'utf8')); }
      catch (error) { throw new Error(`Migration failed: ${file}`, { cause: error }); }
    }

    const tables = (await db.query(`select tablename from pg_tables where schemaname = 'public'`)).rows;
    for (const role of ['anon', 'authenticated']) {
      for (const { tablename } of tables) {
        const publicTable = ['events', 'stories'].includes(tablename);
        const { rows: [grants] } = await db.query(`select
          has_table_privilege($1,$2,'SELECT') as read,
          has_table_privilege($1,$2,'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER') as write`,
          [role, `public.${tablename}`]);
        assert.equal(grants.read, publicTable, `${role} SELECT ${tablename}`);
        assert.equal(grants.write, false, `${role} write ${tablename}`);
        await assert.rejects(asRole(role, `truncate public.${tablename}`), { code: '42501' });
        if (publicTable) await asRole(role, `select * from public.${tablename}`);
        else await assert.rejects(asRole(role, `select * from public.${tablename}`), { code: '42501' });
      }
      const { rows } = await db.query(`select p.oid::regprocedure::text as name
        from pg_proc p join pg_namespace n on n.oid=p.pronamespace
        where n.nspname='public' and has_function_privilege($1,p.oid,'EXECUTE')`, [role]);
      assert.deepEqual(rows, [], `${role} must not execute application RPCs`);
      await assert.rejects(asRole(role, `select check_admin_login_rate_limit($1)`, ['a'.repeat(64)]), { code: '42501' });
      await assert.rejects(asRole(role, `insert into storage.objects values ('event-flyers','probe.jpg')`), { code: '42501' });
      await asRole(role, 'select * from storage.objects');
    }

    // Creating new objects must not silently reopen public access.
    await db.exec(`create table public.future_private (id integer);
      create function public.future_rpc() returns integer language sql as 'select 1';`);
    for (const role of ['anon', 'authenticated']) {
      await assert.rejects(asRole(role, 'select * from future_private'), { code: '42501' });
      await assert.rejects(asRole(role, 'select future_rpc()'), { code: '42501' });
    }
    await asRole('service_role', 'insert into future_private values (1)');
    await asRole('service_role', 'select future_rpc()');

    // Separate calls/clients use the same persisted count. The sixth is denied.
    const key = 'a'.repeat(64);
    for (let i = 1; i <= 6; i++) {
      const { rows } = await asRole('service_role', 'select check_admin_login_rate_limit($1) as result', [key]);
      assert.equal(rows[0].result.ok, i <= 5);
      assert.ok(i <= 5 ? rows[0].result.retry_after_seconds === 0 : rows[0].result.retry_after_seconds > 0);
    }
    const { rows } = await asRole('service_role', 'select check_admin_login_rate_limit($1) as result', ['b'.repeat(64)]);
    assert.equal(rows[0].result.ok, true);
    await asRole('service_role', `update admin_login_attempts set reset_at=now()-interval '1 second' where key=$1`, [key]);
    assert.equal((await asRole('service_role', 'select check_admin_login_rate_limit($1) as result', [key])).rows[0].result.ok, true);
    await assert.rejects(asRole('service_role', 'select check_admin_login_rate_limit($1)', ['invalid']), /Invalid rate limit key/);
    await asRole('service_role', `insert into storage.objects values ('event-flyers','allowed.jpg')`);
    // Triggers still execute after revoking the client function grants.
    await asRole('service_role', `insert into story_extractions (story_id,handle,status) values ('probe','test','no_text')`);
    await asRole('service_role', `update story_extractions set handle='updated' where story_id='probe'`);
  } finally { await db.close(); }
});
