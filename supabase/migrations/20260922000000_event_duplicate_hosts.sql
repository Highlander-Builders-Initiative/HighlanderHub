-- Preserve assessed time precision and all hosts of corroborated duplicates.
-- NULL means old/unassessed precision, never assumed to be date-only.
alter table public.events add column all_day boolean;
alter table public.events add column hosts jsonb not null default '[]'::jsonb
  check (jsonb_typeof(hosts) = 'array');

-- Backfill only the originating post, not sources remapped to another event.
with precision as (
  select e.id, (occurrence->>'all_day')::boolean as all_day
  from public.events e
  join public.source_assessments s
    on s.source_key = 'instagram:post:' || substring(e.id from '_p([0-9]+)$')
  cross join lateral (select coalesce(s.last_complete_assessment, s.assessment) as payload) p
  cross join lateral jsonb_array_elements(p.payload->'result'->'occurrences') occurrence
  where not e.is_locked and p.payload->>'status' = 'complete'
    and jsonb_array_length(p.payload->'result'->'occurrences') = 1
    and jsonb_typeof(occurrence->'all_day') = 'boolean'
    and (occurrence->>'starts_at')::timestamptz = e.starts_at
)
update public.events e set all_day = p.all_day from precision p where e.id = p.id;

-- Publication owns single-post fields; hosts are retained across importer reruns
-- and augmented by reconciliation before duplicates are removed.
create or replace function public.reconcile_source_assessments(updates jsonb)
returns jsonb
language plpgsql
security invoker
set search_path = public
as $$
declare
  item jsonb;
  candidate jsonb;
  typed events%rowtype;
  supported text[];
  aliases text[];
  retire text[] := '{}';
  written integer := 0;
  removed integer := 0;
  affected integer;
begin
  if jsonb_typeof(updates) <> 'array' then
    raise exception 'updates must be an array';
  end if;
  -- Competing importer batches must not observe half-updated ownership.
  perform pg_advisory_xact_lock(hashtextextended('source_assessments_publication', 0));
  for item in select value from jsonb_array_elements(updates) loop
    if item->'assessment'->>'status' is null
       or item->'assessment'->>'status' not in ('complete', 'error')
       or item->>'source_key' is null
       or item->>'origin' is distinct from 'instagram'
       or not starts_with(item->>'source_key', 'instagram:') then
      raise exception 'Invalid assessment update';
    end if;
    select coalesce(array_agg(distinct value), '{}') into aliases
      from jsonb_array_elements_text(coalesce(item->'known_event_ids', '[]'));
    if item->'assessment'->>'status' = 'error' then
      insert into source_assessments(source_key, origin, assessment, known_event_ids, event_ids)
      values(item->>'source_key', item->>'origin', item->'assessment', aliases, aliases)
      on conflict(source_key) do update set
        assessment = excluded.assessment,
        event_ids = array(select distinct unnest(source_assessments.event_ids || excluded.event_ids)),
        known_event_ids = array(select distinct unnest(source_assessments.known_event_ids || excluded.known_event_ids)),
        updated_at = now();
      continue;
    end if;

    select coalesce(array_agg(distinct value->>'id'), '{}') into supported
      from jsonb_array_elements(item->'rows');
    -- An override on an old identity applies to its replacements as well.
    select array(select distinct unnest(aliases || coalesce(
      (select known_event_ids || event_ids from source_assessments where source_key = item->>'source_key'), '{}')))
      into aliases;
    -- Overrides bind individual sessions. A protected identity that disappears
    -- may have been rekeyed: suppress new identities, but retain known siblings.
    -- If the protected ID is still proposed, unrelated new sessions are safe.
    select coalesce(array_agg(candidate_id), '{}') into supported
    from unnest(supported) as candidate_id
    where not exists(select 1 from deleted_events where event_id = candidate_id)
      and not exists(select 1 from events e where e.id = candidate_id and e.is_locked)
      and (candidate_id = any(aliases) or not exists (
        select 1 from unnest(aliases) as old_id
        where not (old_id = any(supported))
          and (exists(select 1 from deleted_events where event_id = old_id)
            or exists(select 1 from events e where e.id = old_id and e.is_locked))
      ));
    insert into source_assessments(source_key, origin, assessment, last_complete_assessment, event_ids, known_event_ids)
    values(item->>'source_key', item->>'origin', item->'assessment', item->'assessment', supported,
           array(select distinct unnest(aliases || supported)))
    on conflict(source_key) do update set
      assessment = excluded.assessment,
      last_complete_assessment = excluded.last_complete_assessment,
      event_ids = excluded.event_ids,
      known_event_ids = excluded.known_event_ids,
      updated_at = now();
    retire := retire || aliases;

    for candidate in select value from jsonb_array_elements(item->'rows') loop
      if not (candidate->>'id' = any(supported)) then continue; end if;
      typed := jsonb_populate_record(null::events, candidate);
      if typed.content_kind not in ('student_event', 'student_deadline')
         or not starts_with(typed.id, 'ig_')
         or typed.source is distinct from 'instagram' then
        raise exception 'Only publishable imported event rows are accepted';
      end if;
      insert into events(id, title, description, starts_at, ends_at, location,
        host, host_handle, all_day, category, content_kind, tags, source, source_url,
        image_url, has_free_food, rsvp_required, rsvp_url, scraped_at)
      values(typed.id, typed.title, typed.description, typed.starts_at, typed.ends_at,
        typed.location, typed.host, typed.host_handle, typed.all_day, typed.category, typed.content_kind,
        typed.tags, typed.source, typed.source_url, typed.image_url,
        typed.has_free_food, typed.rsvp_required, typed.rsvp_url, typed.scraped_at)
      on conflict(id) do update set
        title=excluded.title, description=excluded.description,
        starts_at=excluded.starts_at, ends_at=excluded.ends_at, location=excluded.location,
        host=excluded.host, host_handle=excluded.host_handle, all_day=excluded.all_day, category=excluded.category,
        content_kind=excluded.content_kind, tags=excluded.tags, source=excluded.source,
        source_url=excluded.source_url, image_url=excluded.image_url,
        has_free_food=excluded.has_free_food,
        rsvp_required=excluded.rsvp_required, rsvp_url=excluded.rsvp_url, scraped_at=excluded.scraped_at
      where not events.is_locked
        and not exists(select 1 from deleted_events where event_id=excluded.id);
      get diagnostics affected = row_count;
      written := written + affected;
    end loop;
  end loop;
  delete from events e where e.id = any(retire) and not e.is_locked
    and starts_with(e.id, 'ig_')
    and e.source = 'instagram'
    and not exists(select 1 from source_assessments s where s.event_ids @> array[e.id]);
  get diagnostics removed = row_count;
  return jsonb_build_object('written', written, 'deleted', removed);
end;
$$;
revoke all on function public.reconcile_source_assessments(jsonb) from public, anon, authenticated;
grant execute on function public.reconcile_source_assessments(jsonb) to service_role;

