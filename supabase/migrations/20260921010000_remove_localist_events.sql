-- Remove all historical Localist events and source assessments.
-- Ingestion of Localist was deprecated in 20260916000000_instagram_only_publication.sql;
-- this removes lingering historical rows from the database.
-- Localist imports always used the ucr_events_ id prefix, so a source_url match
-- is unnecessary and would also delete non-Localist rows that only cite events.ucr.edu.

delete from public.events
where starts_with(id, 'ucr_events_');

delete from public.source_assessments
where origin = 'localist'
   or starts_with(source_key, 'localist:');

-- Clean up any legacy Localist tombstones since Localist can no longer be ingested.
delete from public.deleted_events
where starts_with(event_id, 'ucr_events_');
