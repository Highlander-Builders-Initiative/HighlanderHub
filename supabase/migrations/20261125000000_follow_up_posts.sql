-- A club's reel that follows its announcement shows a frame of the video,
-- not a flyer. Record which images are video covers so reconciliation keeps
-- the announcement's flyer and takes only details from the reel.
alter table public.events add column if not exists image_is_video boolean;
comment on column public.events.image_is_video is
  'True when image_url is the cover frame of a video (a reel) rather than a still image; null otherwise.';

-- Publication writes the flag with the image it describes.
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
        updated_at = now()
      where source_assessments.assessment is distinct from excluded.assessment
        or not source_assessments.event_ids @> excluded.event_ids
        or not source_assessments.known_event_ids @> excluded.known_event_ids;
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
      updated_at = now()
    where source_assessments.assessment is distinct from excluded.assessment
      or source_assessments.last_complete_assessment is distinct from excluded.last_complete_assessment
      or not (source_assessments.event_ids @> excluded.event_ids
              and source_assessments.event_ids <@ excluded.event_ids)
      or not (source_assessments.known_event_ids @> excluded.known_event_ids
              and source_assessments.known_event_ids <@ excluded.known_event_ids);
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
        image_url, image_is_video, has_free_food, rsvp_required, rsvp_url, scraped_at)
      values(typed.id, typed.title, typed.description, typed.starts_at, typed.ends_at,
        typed.location, typed.host, typed.host_handle, typed.all_day, typed.category, typed.content_kind,
        typed.tags, typed.source, typed.source_url, typed.image_url, typed.image_is_video,
        typed.has_free_food, typed.rsvp_required, typed.rsvp_url, typed.scraped_at)
      on conflict(id) do update set
        title=excluded.title, description=excluded.description,
        starts_at=excluded.starts_at, ends_at=excluded.ends_at, location=excluded.location,
        host=excluded.host, host_handle=excluded.host_handle, all_day=excluded.all_day, category=excluded.category,
        content_kind=excluded.content_kind, tags=excluded.tags, source=excluded.source,
        source_url=excluded.source_url, image_url=excluded.image_url,
        image_is_video=excluded.image_is_video,
        has_free_food=excluded.has_free_food,
        rsvp_required=excluded.rsvp_required, rsvp_url=excluded.rsvp_url, scraped_at=excluded.scraped_at
      where row(
          events.title, events.description, events.starts_at, events.ends_at, events.location, events.host, events.host_handle, events.all_day, events.category, events.content_kind, events.tags, events.source, events.source_url, events.image_url, events.image_is_video, events.has_free_food, events.rsvp_required, events.rsvp_url
        ) is distinct from row(
          excluded.title, excluded.description, excluded.starts_at, excluded.ends_at, excluded.location, excluded.host, excluded.host_handle, excluded.all_day, excluded.category, excluded.content_kind, excluded.tags, excluded.source, excluded.source_url, excluded.image_url, excluded.image_is_video, excluded.has_free_food, excluded.rsvp_required, excluded.rsvp_url
        )
        and not events.is_locked
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

-- A merge may now take the other listing's date and time (a rescheduled
-- event's follow-up post), and the flag travels with a flyer it takes.
-- It may also lock the kept listing: where the admin chose differently from
-- what reconciliation would (another flyer, venue, end or signup link, or
-- none of them), the kept listing's own post would undo that choice on the
-- next import. A merge can set the lock, never clear it.
create or replace function public.merge_duplicate_events(
  kept_id text, removed_id text, changes jsonb,
  kept_updated_at timestamptz, removed_updated_at timestamptz)
returns void
language plpgsql security invoker set search_path = public
as $$
declare kept events%rowtype; removed events%rowtype; merged events%rowtype;
begin
  -- Publication and reconciliation rewrite source ownership under this lock.
  perform pg_advisory_xact_lock(hashtextextended('source_assessments_publication', 0));
  if kept_id = removed_id then raise exception 'Cannot merge an event into itself'; end if;
  select * into kept from events where id = kept_id for update;
  if not found then raise exception 'Event no longer exists: %', kept_id; end if;
  select * into removed from events where id = removed_id for update;
  if not found then raise exception 'Event no longer exists: %', removed_id; end if;
  if kept.updated_at <> kept_updated_at or removed.updated_at <> removed_updated_at then
    raise exception 'Event changed since this review loaded';
  end if;
  if exists(select 1 from jsonb_object_keys(changes) as key where key not in (
      'has_free_food', 'rsvp_required', 'hosts', 'starts_at', 'all_day', 'ends_at', 'rsvp_url',
      'image_url', 'image_is_video', 'location', 'is_locked')) then
    raise exception 'A merge may only combine details into the kept event';
  end if;

  merged := jsonb_populate_record(kept, changes);
  if changes <> '{}'::jsonb then
    update events set has_free_food = merged.has_free_food, rsvp_required = merged.rsvp_required,
      hosts = merged.hosts, starts_at = merged.starts_at, all_day = merged.all_day,
      ends_at = merged.ends_at, rsvp_url = merged.rsvp_url, image_url = merged.image_url,
      image_is_video = merged.image_is_video, location = merged.location,
      -- The kept listing's own post still states the old time and would
      -- restore it on the next import. A time an admin chose is an admin edit.
      is_locked = is_locked or (changes ? 'starts_at')
        or coalesce((changes->>'is_locked')::boolean, false)
    where id = kept_id;
  end if;

  update source_assessments set
    event_ids = array(select distinct value from unnest(array_remove(event_ids, removed_id) || array[kept_id]) as value),
    known_event_ids = array(select distinct value from unnest(known_event_ids || array[kept_id]) as value),
    updated_at = now()
  where event_ids @> array[removed_id];

  -- A matching title/day key already protects both listings; keep that record.
  if not exists(select 1 from discord_notifications where event_id = kept_id and kind = 'free_food') then
    insert into discord_notifications(event_id, kind, notification_key, notified_at)
    select kept_id, 'free_food',
      'free_food:v2:title-day:' || regexp_replace(lower(trim(merged.title)), '\s+', ' ', 'g')
        || '|' || to_char(merged.starts_at at time zone 'America/Los_Angeles', 'YYYYMMDD'),
      notified_at
    from discord_notifications where event_id = removed_id and kind = 'free_food'
    on conflict (kind, notification_key) do nothing;
  end if;

  delete from events where id = removed_id;

  insert into event_duplicate_reviews(event_id, other_event_id, status, kept_event_id,
    event_snapshot, other_snapshot, decided_at)
  values (least(kept_id collate "C", removed_id), greatest(kept_id collate "C", removed_id),
    'duplicate', kept_id,
    to_jsonb(case when kept_id collate "C" < removed_id then kept else removed end),
    to_jsonb(case when kept_id collate "C" < removed_id then removed else kept end), now())
  on conflict (event_id, other_event_id) do update set
    status = excluded.status, kept_event_id = excluded.kept_event_id,
    event_snapshot = excluded.event_snapshot, other_snapshot = excluded.other_snapshot,
    decided_at = excluded.decided_at;
end;
$$;
revoke all on function public.merge_duplicate_events(text, text, jsonb, timestamptz, timestamptz)
  from public, anon, authenticated;
grant execute on function public.merge_duplicate_events(text, text, jsonb, timestamptz, timestamptz)
  to service_role;
