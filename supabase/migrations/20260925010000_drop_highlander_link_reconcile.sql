-- Highlander Link rows are gone. Duplicate removal no longer accepts that id prefix.
-- Localist (ucr_events_) listings remain eligible to reconcile into Instagram.

create or replace function public.remap_assessed_event_sources(removals jsonb)
returns integer
language plpgsql security invoker set search_path = public
as $$
declare item jsonb; replacement text; existing events%rowtype; removed integer := 0;
begin
  perform pg_advisory_xact_lock(hashtextextended('source_assessments_publication', 0));
  for item in select value from jsonb_array_elements(removals) loop
    select * into existing from events where id = item->>'id' for update;
    if not found or existing.is_locked then continue; end if;
    if not ((starts_with(existing.id, 'ig_') and existing.source = 'instagram')
       or (starts_with(existing.id, 'ucr_events_') and existing.source = 'campus_website')) then
      raise exception 'Only imported duplicates can be removed';
    end if;
    if item->>'updated_at' is not null and existing.updated_at <> (item->>'updated_at')::timestamptz then
      raise exception 'Event changed during source reconciliation: %', existing.id;
    end if;
    replacement := item->>'replacement_id';
    if existing.source = 'campus_website'
       and (replacement is null or not exists(
         select 1 from events where id = replacement and source = 'instagram'
           and starts_with(id, 'ig_'))) then
      raise exception 'Retired campus listings must reconcile into Instagram';
    end if;
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

do $$
declare constraint_name text;
begin
  if exists (select 1 from public.events where source::text = 'highlander_link') then
    raise exception 'highlander_link events still exist';
  end if;
  select con.conname into constraint_name
  from pg_constraint con
  join pg_class rel on rel.oid = con.conrelid
  join pg_namespace nsp on nsp.oid = rel.relnamespace
  where nsp.nspname = 'public'
    and rel.relname = 'source_assessments'
    and con.contype = 'c'
    and pg_get_constraintdef(con.oid) like '%highlander_link%';
  if constraint_name is not null then
    execute format('alter table public.source_assessments drop constraint %I', constraint_name);
    alter table public.source_assessments
      add constraint source_assessments_origin_check
      check (origin in ('instagram', 'localist'));
  end if;
end $$;

alter type public.event_source rename to event_source_old;
create type public.event_source as enum (
  'instagram', 'campus_website', 'club_website', 'manual'
);
alter table public.events
  alter column source type public.event_source
  using source::text::public.event_source;
drop type public.event_source_old;
