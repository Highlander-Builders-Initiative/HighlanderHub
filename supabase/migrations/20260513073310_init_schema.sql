-- HighlanderHub schema: events, stories, submissions
-- ===================================================
--
-- events      — canonical event bulletin (what the UI shows).
-- stories     — raw IG stories not yet event-shaped (for an optional story rail).
-- submissions — public-submitted events pending moderation; approved ones
--               are copied into events.
--
-- RLS policies:
--   events       SELECT public  | writes only via service_role
--   stories      SELECT public  | writes only via service_role
--   submissions  INSERT public  | reads + moderation only via service_role
--                (asymmetric: anyone can submit, no one but admins can read pending)

-- ---------- enums ----------

create type event_category as enum (
  'club', 'academic', 'social', 'career',
  'sports', 'arts', 'community', 'free_food'
);

create type event_source as enum (
  'instagram', 'highlander_link', 'campus_website',
  'club_website', 'manual'
);

create type submission_status as enum ('pending', 'approved', 'rejected');

-- ---------- events ----------

create table events (
  id              text primary key,
  title           text not null,
  description     text not null default '',
  starts_at       timestamptz not null,
  ends_at         timestamptz,
  location        text not null default 'UC Riverside',
  host            text not null default 'UC Riverside',
  host_handle     text,
  category        event_category not null default 'community',
  tags            text[] not null default '{}',
  source          event_source not null,
  source_url      text,
  image_url       text,
  is_free         boolean not null default true,
  rsvp_required   boolean not null default false,
  rsvp_url        text,
  scraped_at      timestamptz not null default now(),
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);

create index events_starts_at_idx     on events (starts_at);
create index events_category_idx      on events (category);
create index events_source_idx        on events (source);

-- ---------- stories ----------

create table stories (
  id                text primary key,
  handle            text not null,
  account_label     text,
  account_category  text,
  owner_userid      bigint,
  owner_username    text,
  typename          text,
  is_video          boolean not null default false,
  posted_at         timestamptz not null,
  expires_at        timestamptz,
  image_url         text,
  video_url         text,
  caption           text,
  caption_mentions  text[] not null default '{}',
  story_cta_url     text,
  permalink         text,
  created_at        timestamptz not null default now()
);

create index stories_handle_idx     on stories (handle);
create index stories_posted_at_idx  on stories (posted_at desc);

-- ---------- submissions ----------

create table submissions (
  id              uuid primary key default gen_random_uuid(),
  title           text not null,
  description     text not null default '',
  starts_at       timestamptz not null,
  ends_at         timestamptz,
  location        text not null default 'UC Riverside',
  host            text not null,
  host_handle     text,
  category        event_category not null default 'community',
  tags            text[] not null default '{}',
  source_url      text,
  image_url       text,
  is_free         boolean not null default true,
  rsvp_required   boolean not null default false,
  rsvp_url        text,
  submitter_name  text not null,
  submitter_email text not null,
  submitter_org   text,
  status          submission_status not null default 'pending',
  reviewed_at     timestamptz,
  review_notes    text,
  created_at      timestamptz not null default now()
);

create index submissions_status_idx     on submissions (status);
create index submissions_created_at_idx on submissions (created_at desc);

-- ---------- updated_at trigger ----------

create or replace function set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at := now();
  return new;
end $$;

create trigger events_set_updated_at
before update on events
for each row execute function set_updated_at();

-- ---------- RLS ----------

alter table events      enable row level security;
alter table stories     enable row level security;
alter table submissions enable row level security;

-- Anyone can read events + stories (public bulletin).
create policy "events_public_read"  on events  for select using (true);
create policy "stories_public_read" on stories for select using (true);

-- Anyone (anon) can submit. Reads/updates/deletes restricted to service_role,
-- which bypasses RLS automatically — so we just don't grant policies for those.
create policy "submissions_public_insert"
  on submissions for insert
  to anon, authenticated
  with check (
    -- Sanity checks at the DB layer so malformed submissions are rejected
    -- even if the frontend skips validation.
    char_length(title) between 3 and 200
    and char_length(submitter_name) between 1 and 100
    and submitter_email like '%@%.%'
    and starts_at > now() - interval '1 day'
  );
