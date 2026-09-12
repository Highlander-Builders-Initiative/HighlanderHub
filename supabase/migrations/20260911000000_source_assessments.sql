-- Source assessment is separate from its public event projection. Errors keep
-- the last support set; successful negative decisions retire only unsupported
-- imported rows. Retain source text and reasons for review and reprocessing.
create table public.source_assessments (
  source_key text primary key,
  origin text not null check (origin in ('instagram', 'localist', 'highlander_link')),
  assessment jsonb not null,
  last_complete_assessment jsonb,
  event_ids text[] not null default '{}',
  known_event_ids text[] not null default '{}',
  updated_at timestamptz not null default now()
);
create index source_assessments_event_ids_idx on public.source_assessments using gin(event_ids);
alter table public.source_assessments enable row level security;
revoke all on public.source_assessments from anon, authenticated;
grant all on public.source_assessments to service_role;

create function public.reconcile_source_assessments(updates jsonb)
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
       or item->>'source_key' is null then
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
    if exists(select 1 from deleted_events where event_id = any(aliases || supported))
       or exists(select 1 from events where id = any(aliases || supported) and is_locked) then
      supported := '{}';
    end if;
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
         or not (starts_with(typed.id, 'ig_') or starts_with(typed.id, 'ucr_events_') or starts_with(typed.id, 'highlander_link_')) then
        raise exception 'Only publishable imported event rows are accepted';
      end if;
      insert into events(id, title, description, starts_at, ends_at, location,
        host, host_handle, category, content_kind, tags, source, source_url,
        image_url, is_free, has_free_food, rsvp_required, rsvp_url, scraped_at)
      values(typed.id, typed.title, typed.description, typed.starts_at, typed.ends_at,
        typed.location, typed.host, typed.host_handle, typed.category, typed.content_kind,
        typed.tags, typed.source, typed.source_url, typed.image_url, typed.is_free,
        typed.has_free_food, typed.rsvp_required, typed.rsvp_url, typed.scraped_at)
      on conflict(id) do update set
        title=excluded.title, description=excluded.description,
        starts_at=excluded.starts_at, ends_at=excluded.ends_at, location=excluded.location,
        host=excluded.host, host_handle=excluded.host_handle, category=excluded.category,
        content_kind=excluded.content_kind, tags=excluded.tags, source=excluded.source,
        source_url=excluded.source_url, image_url=excluded.image_url,
        is_free=excluded.is_free, has_free_food=excluded.has_free_food,
        rsvp_required=excluded.rsvp_required, rsvp_url=excluded.rsvp_url, scraped_at=excluded.scraped_at
      where not events.is_locked
        and not exists(select 1 from deleted_events where event_id=excluded.id);
      get diagnostics affected = row_count;
      written := written + affected;
    end loop;
  end loop;
  delete from events e where e.id = any(retire) and not e.is_locked
    and (e.id like 'ig_%' or e.id like 'ucr_events_%' or e.id like 'highlander_link_%')
    and e.source <> 'manual'
    and not exists(select 1 from source_assessments s where s.event_ids @> array[e.id]);
  get diagnostics removed = row_count;
  return jsonb_build_object('written', written, 'deleted', removed);
end;
$$;
revoke all on function public.reconcile_source_assessments(jsonb) from public, anon, authenticated;
grant execute on function public.reconcile_source_assessments(jsonb) to service_role;

-- Cross-source deduplication must move ownership to the surviving row before
-- deleting a duplicate, otherwise a later reassessment could erase a listing
-- still supported by the duplicate's source.
create function public.remap_assessed_event_sources(removals jsonb)
returns integer
language plpgsql security invoker set search_path = public
as $$
declare item jsonb; replacement text; existing events%rowtype; removed integer := 0;
begin
  perform pg_advisory_xact_lock(hashtextextended('source_assessments_publication', 0));
  for item in select value from jsonb_array_elements(removals) loop
    select * into existing from events where id = item->>'id' for update;
    if not found or existing.is_locked then continue; end if;
    if not (starts_with(existing.id, 'ig_') or starts_with(existing.id, 'ucr_events_') or starts_with(existing.id, 'highlander_link_'))
       or existing.source = 'manual' then
      raise exception 'Only imported duplicates can be removed';
    end if;
    if item->>'updated_at' is not null and existing.updated_at <> (item->>'updated_at')::timestamptz then
      raise exception 'Event changed during source reconciliation: %', existing.id;
    end if;
    replacement := item->>'replacement_id';
    if replacement = existing.id then raise exception 'Cannot replace an event with itself'; end if;
    if replacement is not null and not exists(select 1 from events where id = replacement) then
      raise exception 'Canonical replacement is missing: %', replacement;
    end if;
    update source_assessments set
      event_ids = array(select distinct value from unnest(array_remove(event_ids, existing.id)
        || case when replacement is null then '{}'::text[] else array[replacement] end) as value),
      known_event_ids = array(select distinct value from unnest(known_event_ids
        || case when replacement is null then '{}'::text[] else array[replacement] end) as value),
      updated_at = now()
    where event_ids @> array[existing.id];
    delete from events where id = existing.id;
    removed := removed + 1;
  end loop;
  return removed;
end;
$$;
revoke all on function public.remap_assessed_event_sources(jsonb) from public, anon, authenticated;
grant execute on function public.remap_assessed_event_sources(jsonb) to service_role;
