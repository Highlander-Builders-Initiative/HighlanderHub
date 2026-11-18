-- The Free plan restricts a project that exceeds 500 MB of database or 1 GB of
-- file storage. Storage reached 3.1 GB unnoticed in November 2026 and the
-- project was restricted, so every pipeline run now reads both sizes and
-- fails loudly well before either limit (pipeline/project_usage.py).
--
-- Sizes only: no names, rows or file contents leave the database.
create or replace function public.project_usage()
returns table(database_bytes bigint, storage_bytes bigint, storage_files bigint)
language sql stable security definer set search_path = public
as $$
  select pg_database_size(current_database()),
         coalesce((select sum((o.metadata->>'size')::bigint) from storage.objects o), 0),
         (select count(*) from storage.objects);
$$;

revoke all on function public.project_usage() from public, anon, authenticated;
grant execute on function public.project_usage() to service_role;
