-- Migration: Add is_locked column to events table to prevent automated pipeline overwriting manual corrections.
-- ===================================================

ALTER TABLE events ADD COLUMN is_locked BOOLEAN NOT NULL DEFAULT false;

-- Add a comment to the column for database schema documentation
COMMENT ON COLUMN events.is_locked IS 'If true, manual edits have lock priority and the automated scraper pipeline must not overwrite this event.';
