-- The public submission flow has been removed. Close its database and
-- storage write paths while retaining existing flyers and service-role access.
drop policy if exists "submissions_public_insert" on public.submissions;
revoke insert on table public.submissions from public, anon, authenticated;

-- Storage grants are shared by all buckets; revoke this bucket's insert
-- policy rather than changing storage.objects privileges globally.
drop policy if exists "submission_flyers_anon_insert" on storage.objects;
