-- Retire a small oldest-first batch. Keep source/OCR caches and notification
-- memory so replay neither pays again nor treats old events as new alerts.
create or replace function public.retire_old_events()
returns integer
language plpgsql security invoker set search_path = public
as $$
declare retired text[]; affected integer;
begin
  perform pg_advisory_xact_lock(hashtextextended('source_assessments_publication', 0));
  select coalesce(array_agg(id), '{}') into retired from (
    select id from events
    where greatest(starts_at, ends_at) < now() - interval '30 days'
      and not is_locked and source <> 'manual'
    order by greatest(starts_at, ends_at), id limit 50 for update
  ) old;
  update source_assessments set
    event_ids = array(select unnest(event_ids) except select unnest(retired))
  where event_ids && retired;
  delete from events where id = any(retired);
  get diagnostics affected = row_count;
  return affected;
end;
$$;

-- Unknown, malformed and failed assessments are ineligible. A post's age is
-- never substituted for an event date; every session must have finished.
create or replace function public.retention_source_finished(payload jsonb, cutoff timestamptz)
returns boolean
language plpgsql stable security invoker set search_path = public
as $$
declare result jsonb; occurrence jsonb; finish timestamptz;
begin
  if payload->>'status' is distinct from 'complete' then return false; end if;
  result := payload->'result';
  if result->>'kind' in ('announcement', 'application') then return true; end if;
  if result->>'kind' not in ('activity', 'deadline', 'service_schedule')
     or result->>'kind' is null then return false; end if;
  if jsonb_typeof(result->'schedule') = 'object' then
    finish := ((result->'schedule'->>'last_day')::date + 1)::timestamp
      at time zone 'America/Los_Angeles';
    return coalesce(finish < cutoff, false);
  end if;
  if jsonb_typeof(result->'occurrences') is distinct from 'array'
     or jsonb_array_length(result->'occurrences') = 0 then return false; end if;
  for occurrence in select value from jsonb_array_elements(result->'occurrences') loop
    if occurrence->>'starts_at' is null then return false; end if;
    finish := greatest((occurrence->>'starts_at')::timestamptz,
                       (occurrence->>'ends_at')::timestamptz);
    if finish is null or finish >= cutoff then return false; end if;
  end loop;
  return true;
exception when invalid_datetime_format or datetime_field_overflow then
  return false;
end;
$$;

-- Read Storage metadata only. The worker must remove physical files through
-- the Storage API, never DELETE FROM storage.objects.
create or replace function public.old_event_flyers()
returns table(name text, bytes bigint)
language sql stable security definer set search_path = public
as $$
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
    and not exists (select 1 from events e where
      e.id = any(s.event_ids || s.known_event_ids)
      or e.image_url like '%/storage/v1/object/public/event-flyers/' || o.name)
    and not exists (select 1 from submissions x where
      x.image_url like '%/storage/v1/object/public/event-flyers/' || o.name)
    and not exists (select 1 from stories x where
      x.image_url like '%/storage/v1/object/public/event-flyers/' || o.name)
  order by o.created_at, o.name
  limit 500;
$$;

revoke all on function public.retire_old_events() from public, anon, authenticated;
revoke all on function public.retention_source_finished(jsonb, timestamptz) from public, anon, authenticated;
revoke all on function public.old_event_flyers() from public, anon, authenticated;
grant execute on function public.retire_old_events() to service_role;
grant execute on function public.retention_source_finished(jsonb, timestamptz) to service_role;
grant execute on function public.old_event_flyers() to service_role;
