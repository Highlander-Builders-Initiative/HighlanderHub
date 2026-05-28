-- Tracks Discord webhook alerts so pipeline reruns do not repost the same event.
create table if not exists discord_notifications (
  event_id    text not null references events(id) on delete cascade,
  kind        text not null check (kind in ('free_food')),
  notified_at timestamptz not null default now(),
  primary key (event_id, kind)
);

alter table discord_notifications enable row level security;

-- Treat already-indexed free food as old news when this feature is enabled.
insert into discord_notifications (event_id, kind)
select id, 'free_food'
from events
where category = 'free_food'
on conflict do nothing;
