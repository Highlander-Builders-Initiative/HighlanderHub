-- RLS remains the row-level boundary. Grants should independently reflect the
-- public app's read-only contract; TRUNCATE in particular is not covered by RLS.
revoke all on table public.events, public.stories, public.submissions,
  public.deleted_events, public.discord_notifications, public.story_extractions,
  public.source_assessments, public.instagram_posts, public.post_extractions,
  public.instagram_post_checkpoints, public.vision_ocr_usage,
  public.event_duplicate_reviews from public, anon, authenticated;
grant select on table public.events, public.stories to anon, authenticated;

alter function public.set_updated_at() set search_path = '';
revoke all on function public.set_updated_at() from public, anon, authenticated;
grant execute on function public.set_updated_at() to service_role;

-- New application objects require deliberate client grants. Keep the existing
-- service_role defaults so ingestion and authenticated server actions work.
alter default privileges for role postgres in schema public
  revoke all on tables from anon, authenticated;
alter default privileges for role postgres in schema public
  revoke all on sequences from anon, authenticated;
alter default privileges for role postgres in schema public
  revoke execute on functions from anon, authenticated;
-- PUBLIC's built-in function default is global, not schema-specific.
alter default privileges for role postgres
  revoke execute on functions from public;
