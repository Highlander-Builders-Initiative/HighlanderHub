import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';

const { PGlite } = await import(process.env.PGLITE_MODULE || '@electric-sql/pglite');
const migrations = new URL('../../supabase/migrations/', import.meta.url);
const submission = `insert into public.submissions
  (title, starts_at, host, submitter_name, submitter_email)
  values ('Policy probe', '2027-01-01T12:00:00Z', 'Test club', 'Test', 'test@example.com')`;
const upload = `insert into storage.objects (bucket_id, name)
  values ('submission-flyers', 'policy-probe.png')`;

test('retired submissions reject client writes while preserving reads and service access', async () => {
  const db = new PGlite();
  const migrate = async name => db.exec(await readFile(new URL(name, migrations), 'utf8'));
  const asRole = async (role, sql) => {
    await db.exec(`set role ${role}`);
    try { return await db.query(sql); }
    finally { await db.exec('reset role'); }
  };
  try {
    await db.exec(`
      create role anon;
      create role authenticated;
      create role service_role bypassrls;
      create schema storage;
      create table storage.buckets (
        id text primary key, name text, public boolean,
        file_size_limit bigint, allowed_mime_types text[]
      );
      create table storage.objects (bucket_id text, name text);
      alter table storage.objects enable row level security;
      grant usage on schema public, storage to anon, authenticated, service_role;
      grant select, insert on storage.objects to anon, authenticated;
      grant all on storage.objects to service_role;
    `);
    for (const name of [
      '20260513073310_init_schema.sql',
      '20260513073955_fix_submissions_grants.sql',
      '20260513074118_fix_submissions_policy.sql',
      '20260523000000_storage_submission_flyers.sql',
      '20260528020000_restrict_submission_insert.sql',
    ]) await migrate(name);
    await db.exec('grant all on public.submissions to service_role');

    // Reproduce both obsolete write paths under actual PostgreSQL roles/RLS.
    for (const role of ['anon', 'authenticated']) {
      await asRole(role, submission);
      await asRole(role, upload);
    }
    // An inherited PUBLIC grant must not leave INSERT available either.
    await db.exec('grant insert on public.submissions to public');
    await migrate('20260915000000_disable_public_submissions.sql');
    await migrate('20260915000000_disable_public_submissions.sql');

    for (const role of ['anon', 'authenticated']) {
      await assert.rejects(asRole(role, submission), { code: '42501' });
      await assert.rejects(asRole(role, upload), { code: '42501' });
      const { rows } = await db.query(
        "select has_table_privilege($1, 'public.submissions', 'INSERT') as allowed", [role]
      );
      assert.equal(rows[0].allowed, false);
      assert.equal((await asRole(role, 'select * from storage.objects')).rows.length, 2);
    }
    assert.equal((await db.query(`select * from pg_policies where policyname in
      ('submissions_public_insert', 'submission_flyers_anon_insert')`)).rows.length, 0);
    assert.equal((await db.query('select * from public.submissions')).rows.length, 2);
    assert.equal((await db.query("select public from storage.buckets where id = 'submission-flyers'"))
      .rows[0].public, true);
    await asRole('service_role', submission);
    await asRole('service_role', upload);
  } finally {
    await db.close();
  }
});
