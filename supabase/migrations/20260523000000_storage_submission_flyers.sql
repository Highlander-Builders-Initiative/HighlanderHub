-- Storage bucket for public-submitted flyer images.
--
-- Submissions previously accepted only a pasted image_url. To let club
-- officers upload a flyer JPEG from their phone, we need a public bucket
-- that anon can write to (mirroring the submissions table's anon-insert
-- policy) and that the public bulletin can read from for rendering.
--
-- Bucket: submission-flyers
--   public read   — bulletin renders flyer URLs directly
--   anon insert   — submit form uploads from the browser
--   no update     — uploaded blobs are immutable; no one can overwrite
--   no delete     — moderator cleanup goes through service_role

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'submission-flyers',
  'submission-flyers',
  true,
  5242880, -- 5MB
  array['image/jpeg', 'image/png', 'image/webp']
)
on conflict (id) do update
  set public            = excluded.public,
      file_size_limit   = excluded.file_size_limit,
      allowed_mime_types = excluded.allowed_mime_types;

create policy "submission_flyers_anon_insert"
  on storage.objects for insert
  to anon, authenticated
  with check (bucket_id = 'submission-flyers');

create policy "submission_flyers_public_read"
  on storage.objects for select
  to public
  using (bucket_id = 'submission-flyers');
