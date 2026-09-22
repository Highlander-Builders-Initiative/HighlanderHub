-- Retired campus listings remain visible and must participate in duplicate
-- cleanup. This does not re-enable campus ingestion or publication.
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
       or ((starts_with(existing.id, 'highlander_link_') or starts_with(existing.id, 'ucr_events_'))
           and existing.source = 'campus_website')) then
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
