-- old_event_flyers() hit the ~8s PostgREST statement timeout on 2026-11-14.
-- The original checked each candidate file with `image_url like '%…' || name`
-- against events, submissions and stories (plus an OR on events), which is a
-- full scan of all three tables per file. Collect the referenced flyer names
-- once instead and exclude them with a hashed anti-join; the event_ids check
-- alone can use the events primary key. Same eligibility rules as before.
create or replace function public.old_event_flyers()
returns table(name text, bytes bigint)
language sql stable security definer set search_path = public
as $$
  -- Not MATERIALIZED: an opaque CTE has no row estimate, and the planner
  -- then anti-joins it with a nested loop instead of a hash.
  with referenced(name) as (
    -- The greedy leading .* takes the last marker, matching the old suffix
    -- test `like '%/storage/v1/object/public/event-flyers/' || name`.
    select substring(u from '^.*/storage/v1/object/public/event-flyers/(.+)$')
    from (
      select image_url from events
      union all select image_url from submissions
      union all select image_url from stories
    ) refs(u)
    where u like '%/storage/v1/object/public/event-flyers/%'
  )
  select o.name, coalesce((o.metadata->>'size')::bigint, 0)
  from storage.objects o
  join instagram_posts p on p.media_id = split_part(o.name, '/', 4)
  join source_assessments s on s.source_key = 'instagram:post:' || p.media_id
  where o.bucket_id = 'event-flyers'
    and o.name ~ '^instagram/[^/]+/posts/[^/]+/[^/]+[.]jpg$'
    and greatest(o.created_at, o.updated_at) < now() - interval '14 days'
    and p.posted_at < now() - interval '14 days'
    and retention_source_finished(s.assessment, now() - interval '30 days')
    -- Protect all slides when an event from this source is still retained,
    -- including locked rows and canonical rows shared with another source.
    and not exists (select 1 from events e
      where e.id = any(s.event_ids || s.known_event_ids))
    and not exists (select 1 from referenced r where r.name = o.name)
  order by o.created_at, o.name
  limit 500;
$$;

revoke all on function public.old_event_flyers() from public, anon, authenticated;
grant execute on function public.old_event_flyers() to service_role;
