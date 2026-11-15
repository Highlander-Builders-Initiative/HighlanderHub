-- Publication now stores only the slide each event shows, and uploads any
-- slide a row names that is not stored (missing_event_flyers). So the other
-- slides of a live event's post no longer need protecting: on 2026-11-14 they
-- held 282 MB that no listing showed.
--
-- unused_event_flyers() is 20261114010000's without the live-post clause:
--   * no events/submissions/stories row points at the file, and
--   * the post's assessment is complete and the file is 2+ days old, or the
--     file is 14+ days old whatever its post's state.
-- The 2-day floor covers a file uploaded moments before its event row is
-- written. A reassessment that picks a deleted slide uploads it again from
-- Instagram, or publishes without an image once Instagram's copy has expired.
--
-- Safe to apply before or after the pipeline change: the deployed worker
-- still uploads every slide at extraction and calls old_event_flyers().
create or replace function public.unused_event_flyers(max_rows integer default 500)
returns table(name text, bytes bigint)
language sql stable security definer set search_path = public
as $$
  -- Not MATERIALIZED: the planner needs row estimates to hash these anti-joins.
  with referenced(name) as (
    -- The greedy leading .* takes the last marker, as the suffix LIKE did.
    select substring(u from '^.*/storage/v1/object/public/event-flyers/(.+)$')
    from (
      select image_url from events
      union all select image_url from submissions
      union all select image_url from stories
    ) refs(u)
    where u like '%/storage/v1/object/public/event-flyers/%'
  ),
  files as (
    select o.name, o.created_at, coalesce((o.metadata->>'size')::bigint, 0) as bytes,
      greatest(o.created_at, o.updated_at) as touched,
      case when o.name ~ '^instagram/[^/]+/posts/[^/]+/[^/]+[.]jpg$'
           then split_part(o.name, '/', 4) end as media_id
    from storage.objects o
    where o.bucket_id = 'event-flyers'
      and greatest(o.created_at, o.updated_at) < now() - interval '2 days'
  )
  select f.name, f.bytes
  from files f
  left join source_assessments s on s.source_key = 'instagram:post:' || f.media_id
  where not exists (select 1 from referenced r where r.name = f.name)
    and ((f.media_id is not null and s.assessment->>'status' = 'complete')
         or f.touched < now() - interval '14 days')
  order by f.created_at, f.name
  limit greatest(0, least(coalesce(max_rows, 500), 1000));
$$;

revoke all on function public.unused_event_flyers(integer) from public, anon, authenticated;
grant execute on function public.unused_event_flyers(integer) to service_role;
