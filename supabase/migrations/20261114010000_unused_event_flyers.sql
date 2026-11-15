-- Storage reached 3.1 GB on the 1 GB Free plan (2026-11-14). Every slide of
-- every post is stored while it is read, but an event shows one of them, so
-- 2.4 GB were slides of posts with no live event and 71 MB were files from the
-- dropped stories pipeline. old_event_flyers() reaches neither in time.
--
-- unused_event_flyers() lists files no listing can show:
--   * no events/submissions/stories row points at the file, and
--   * no live event comes from its post (event_ids/known_event_ids also cover
--     locked rows and canonical rows shared with another source), and
--   * the post's assessment is complete and the file is 2+ days old, or the
--     file is 14+ days old whatever its post's state (failed or never assessed
--     posts, and legacy story files outside instagram/*/posts/).
-- Retention deletes them through the Storage API, never DELETE FROM
-- storage.objects. A deleted slide that a later assessment picks as an event's
-- flyer is uploaded again at publication (missing_event_flyers below).
--
-- old_event_flyers() stays so the deployed worker keeps working until this
-- change ships; unused_event_flyers() covers everything it returns.
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
  live(media_id) as (
    select split_part(s.source_key, ':', 3)
    from source_assessments s
    where s.source_key like 'instagram:post:%'
      and exists (select 1 from events e where e.id = any(s.event_ids || s.known_event_ids))
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
    and not exists (select 1 from live l where l.media_id = f.media_id)
    and ((f.media_id is not null and s.assessment->>'status' = 'complete')
         or f.touched < now() - interval '14 days')
  order by f.created_at, f.name
  limit greatest(0, least(coalesce(max_rows, 500), 1000));
$$;

-- The subset of these bucket paths with no stored file, in one round trip.
create or replace function public.missing_event_flyers(names text[])
returns table(name text)
language sql stable security definer set search_path = public
as $$
  select distinct n from unnest(names) n
  where not exists (select 1 from storage.objects o
                    where o.bucket_id = 'event-flyers' and o.name = n);
$$;

revoke all on function public.unused_event_flyers(integer) from public, anon, authenticated;
revoke all on function public.missing_event_flyers(text[]) from public, anon, authenticated;
grant execute on function public.unused_event_flyers(integer) to service_role;
grant execute on function public.missing_event_flyers(text[]) to service_role;
