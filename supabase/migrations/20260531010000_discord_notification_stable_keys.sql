-- Keep Discord notification memory even when imported event row IDs change.
-- The bot dedupes free-food alerts by the public event identity, not only by
-- the generated events.id value.

alter table discord_notifications
  add column if not exists notification_key text;

alter table discord_notifications
  drop constraint if exists discord_notifications_event_id_fkey;

update discord_notifications as dn
set notification_key = 'free_food:v2:title-day:'
  || regexp_replace(lower(trim(e.title)), '\s+', ' ', 'g')
  || '|'
  || to_char(e.starts_at at time zone 'America/Los_Angeles', 'YYYYMMDD')
from events as e
where dn.event_id = e.id
  and dn.kind = 'free_food'
  and coalesce(dn.notification_key, '') = '';

update discord_notifications
set notification_key = 'free_food:v2:id:' || event_id
where coalesce(notification_key, '') = '';

alter table discord_notifications
  alter column notification_key set not null;

create unique index if not exists discord_notifications_kind_notification_key_idx
  on discord_notifications (kind, notification_key);

-- Treat already-indexed has_free_food rows as old news too. The original
-- migration only saw legacy category='free_food' rows.
insert into discord_notifications (event_id, kind, notification_key)
select
  id,
  'free_food',
  'free_food:v2:title-day:'
    || regexp_replace(lower(trim(title)), '\s+', ' ', 'g')
    || '|'
    || to_char(starts_at at time zone 'America/Los_Angeles', 'YYYYMMDD')
from events
where has_free_food or category = 'free_food'
on conflict (kind, notification_key) do nothing;
