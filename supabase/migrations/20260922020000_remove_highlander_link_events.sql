-- Remove all remaining Highlander Link events and source assessments.
-- Ingestion was retired in 20260916000000_instagram_only_publication.sql, and
-- events.reconcile (20260922010000_reconcile_legacy_duplicates.sql) has already
-- merged every Highlander Link listing that duplicated an Instagram post. What
-- remains is campus-only, which is intentionally dropped.
-- Highlander Link imports always used the highlander_link_ id prefix, and every
-- campus_website row carries it; matching by source or source_url is unnecessary
-- and could delete rows that only cite a campus page.
-- discord_notifications is left alone: it has no foreign key, and its
-- title-day keys keep already-sent free food alerts from repeating.

delete from public.events
where starts_with(id, 'highlander_link_');

delete from public.source_assessments
where origin = 'highlander_link'
   or starts_with(source_key, 'highlander_link:');

-- Clean up legacy Highlander Link tombstones since it can no longer be ingested.
delete from public.deleted_events
where starts_with(event_id, 'highlander_link_');
