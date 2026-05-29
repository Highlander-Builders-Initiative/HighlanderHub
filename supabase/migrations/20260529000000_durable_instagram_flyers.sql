-- Durable public storage for Instagram story flyers captured during extraction.
--
-- The Instagram CDN URLs embedded in story metadata expire quickly. The
-- extraction worker already downloads each fresh story image once for OCR, so
-- it uploads those same bytes here and stores the resulting stable URL in the
-- extraction cache and events.image_url.

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'event-flyers',
  'event-flyers',
  true,
  5242880, -- 5MB
  array['image/jpeg']
)
on conflict (id) do update
  set public             = excluded.public,
      file_size_limit    = excluded.file_size_limit,
      allowed_mime_types = excluded.allowed_mime_types;

create policy "event_flyers_public_read"
  on storage.objects for select
  to public
  using (bucket_id = 'event-flyers');

alter table story_extractions
  add column if not exists image_url text;
