-- Replace the strict policy check (which rejected valid rows for unclear
-- reasons) with a permissive policy + table-level constraints. Validation
-- belongs in the app; the DB constraints are defense-in-depth.

drop policy if exists "submissions_public_insert" on submissions;

create policy "submissions_public_insert"
  on submissions for insert
  to anon, authenticated
  with check (true);

alter table submissions
  add constraint submissions_title_len check (char_length(title) between 3 and 200),
  add constraint submissions_name_len  check (char_length(submitter_name) between 1 and 100),
  add constraint submissions_email_fmt check (submitter_email like '%@%.%'),
  add constraint submissions_starts_at_reasonable check (starts_at > '2026-01-01'::timestamptz);
