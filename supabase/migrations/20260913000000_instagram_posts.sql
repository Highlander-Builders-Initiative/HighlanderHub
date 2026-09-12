-- Instagram feed posts: durable records, extraction cache, and per-account
-- collection checkpoints.
--
-- Posts are a separate acquisition channel from stories. They never enter the
-- frontend `stories` table; they publish through the existing
-- `source_assessments` ownership model under source keys of the form
-- `instagram:post:<media_id>` with origin 'instagram', so no change to that
-- table's origin constraint or to `reconcile_source_assessments` is required.

-- Durable copy of the raw post record. Unlike stories (which expire from
-- Instagram in 24h, making the local archive the only record), posts remain
-- refetchable — this table exists so losing the local cache does not repeat
-- paid extraction or re-run discovery from scratch.
--
-- `post_archive.hydrate_local_posts` is what makes that true: collection and
-- extraction both restore missing archive files from here before reading the
-- archive. `record` is the serialized archive file and `first_seen_at` the
-- column that keeps a restored post from looking newly discovered. Restoring
-- cannot re-admit history — every row here was already accepted past its
-- account's activation boundary.
create table public.instagram_posts (
  media_id          text primary key,
  handle            text not null,
  owner_username    text,
  shortcode         text,
  permalink         text,
  posted_at         timestamptz not null,
  typename          text,
  caption           text,
  has_video         boolean not null default false,
  media             jsonb not null default '[]'::jsonb,
  record            jsonb not null,
  first_seen_at     timestamptz not null default now(),
  fetched_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);
create index instagram_posts_handle_idx on public.instagram_posts (handle);
create index instagram_posts_posted_at_idx on public.instagram_posts (posted_at desc);
create trigger instagram_posts_set_updated_at
before update on public.instagram_posts
for each row execute function set_updated_at();
alter table public.instagram_posts enable row level security;
revoke all on public.instagram_posts from anon, authenticated;
grant all on public.instagram_posts to service_role;

-- Extraction cache. `images` holds per-slide OCR/QR results keyed by a
-- signature-free media key, so a caption edit reuses image OCR and a refreshed
-- CDN URL costs nothing. Successful slides are retained inside an `error`
-- payload: a partial media failure is retryable and must never discard the
-- OCR already paid for.
create table public.post_extractions (
  media_id           text primary key,
  handle             text not null,
  status             text not null check (
    status in ('ok', 'no_text', 'unsupported_media', 'no_media', 'error')
  ),
  fingerprint        text,
  extraction_version integer,
  caption            text,
  images             jsonb not null default '[]'::jsonb,
  result             jsonb,
  extracted_at       timestamptz not null default now(),
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now()
);
create index post_extractions_handle_idx on public.post_extractions (handle);
create index post_extractions_status_idx on public.post_extractions (status);
create trigger post_extractions_set_updated_at
before update on public.post_extractions
for each row execute function set_updated_at();
alter table public.post_extractions enable row level security;
revoke all on public.post_extractions from anon, authenticated;
grant all on public.post_extractions to service_role;

-- Per-account collection state. `activated_at` is written before an account's
-- first fetch and never moves afterwards: it is the boundary that keeps
-- historical posts (including an old post newly pinned to the profile) out of
-- the feed. `scanned_through` advances only after a successful scan whose raw
-- writes are durable, so an interrupted scan retries the remaining interval.
create table public.instagram_post_checkpoints (
  handle           text primary key,
  activated_at     timestamptz not null,
  scanned_through  timestamptz,
  last_scan_at     timestamptz,
  last_status      text,
  updated_at       timestamptz not null default now()
);
create trigger instagram_post_checkpoints_set_updated_at
before update on public.instagram_post_checkpoints
for each row execute function set_updated_at();
alter table public.instagram_post_checkpoints enable row level security;
revoke all on public.instagram_post_checkpoints from anon, authenticated;
grant all on public.instagram_post_checkpoints to service_role;

-- Activation is a one-way boundary. A rerun, a restored backup, or a lost
-- local cache must never move it later or earlier and re-admit history.
create function public.claim_post_activation(entries jsonb)
returns jsonb
language plpgsql security invoker set search_path = public
as $$
declare item jsonb;
begin
  if jsonb_typeof(entries) <> 'array' then
    raise exception 'entries must be an array';
  end if;
  for item in select value from jsonb_array_elements(entries) loop
    insert into instagram_post_checkpoints(handle, activated_at)
    values(item->>'handle', (item->>'activated_at')::timestamptz)
    on conflict(handle) do nothing;
  end loop;
  return coalesce((select jsonb_object_agg(handle, to_jsonb(c) - 'handle')
                   from instagram_post_checkpoints c
                   where handle in (select value->>'handle' from jsonb_array_elements(entries) as value)),
                  '{}'::jsonb);
end;
$$;
revoke all on function public.claim_post_activation(jsonb) from public, anon, authenticated;
grant execute on function public.claim_post_activation(jsonb) to service_role;
