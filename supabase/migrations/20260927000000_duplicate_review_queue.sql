-- Admin review of likely duplicates that no reconciliation rule merged.
-- Reconciliation queues each pair; an admin merges it or marks it different.
-- Both decisions bind later runs: publication withholds a merged repost and
-- reconciliation never merges a pair judged different.

create table public.event_duplicate_reviews (
  -- Byte order, so the pipeline and the admin order a pair the same way.
  event_id        text collate "C" not null,
  other_event_id  text collate "C" not null,
  status          text not null default 'pending'
                  check (status in ('pending', 'duplicate', 'different')),
  kept_event_id   text collate "C",
  -- Both listings as the admin saw them, kept after a merge deletes one.
  event_snapshot  jsonb,
  other_snapshot  jsonb,
  flagged_at      timestamptz not null default now(),
  decided_at      timestamptz,
  primary key (event_id, other_event_id),
  check (event_id < other_event_id),
  check ((status = 'duplicate') = (kept_event_id is not null)),
  check (kept_event_id in (event_id, other_event_id)),
  check ((status = 'pending') = (decided_at is null))
);

comment on table public.event_duplicate_reviews is
  'Likely duplicate event pairs flagged by reconciliation, and the admin decision on each.';
comment on column public.event_duplicate_reviews.kept_event_id is
  'For a duplicate, the listing kept. The other was deleted and its sources now support this one.';

alter table public.event_duplicate_reviews enable row level security;
revoke all on public.event_duplicate_reviews from public, anon, authenticated;
grant select, insert, update, delete on public.event_duplicate_reviews to service_role;

-- Keep one listing and retire the other in a single transaction: combine the
-- details the caller chose, move the retired listing's sources and any
-- free-food alert already sent onto the kept one, then record the decision.
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
      'has_free_food', 'rsvp_required', 'hosts', 'ends_at', 'rsvp_url', 'image_url', 'location')) then
    raise exception 'A merge may only combine details into the kept event';
  end if;

  merged := jsonb_populate_record(kept, changes);
  if changes <> '{}'::jsonb then
    update events set has_free_food = merged.has_free_food, rsvp_required = merged.rsvp_required,
      hosts = merged.hosts, ends_at = merged.ends_at, rsvp_url = merged.rsvp_url,
      image_url = merged.image_url, location = merged.location
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
