-- Tombstones for admin-deleted events so importer reruns do not recreate them.

create table deleted_events (
  event_id   text primary key,
  deleted_at timestamptz not null default now()
);

comment on table deleted_events is 'Event IDs deleted by admins. Pipeline imports must skip these IDs so deleted rows do not reappear.';
comment on column deleted_events.event_id is 'Primary ID from events.id that should not be imported again.';

alter table deleted_events enable row level security;
