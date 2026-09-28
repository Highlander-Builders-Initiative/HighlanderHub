-- Where a listing falls in time: when it starts, or when a deadline is due.
--
-- A deadline the source gives only a date for ("apply by Sep 27") is stored
-- like an all-day event, Pacific midnight to the midnight after, so its
-- starts_at is the midnight that opens the due date. It is due by the end of
-- that day, read as 11:59 PM. Every other listing sorts by its start, all-day
-- events included (they open their day).
--
-- The feed orders and pages by (sort_at, id), and a deadline shows its time
-- from sort_at. Generated, so no writer (the pipeline, an admin edit, a merge)
-- can leave it stale; writers name their columns, so none writes it. The due
-- date stays starts_at's Pacific day, so days still group by starts_at.
--
-- Apply before deploying the app that reads it.

alter table public.events add column sort_at timestamptz generated always as (
  case
    when content_kind = 'student_deadline'
      and ends_at > starts_at
      and (starts_at at time zone 'America/Los_Angeles')::time = time '00:00'
      and (ends_at at time zone 'America/Los_Angeles')::time = time '00:00'
    then (date_trunc('day', starts_at at time zone 'America/Los_Angeles') + interval '23 hours 59 minutes')
      at time zone 'America/Los_Angeles'
    else starts_at
  end
) stored;

create index events_sort_at_id_idx on public.events (sort_at, id);
