-- student_application — a program you enroll in (academy, fellowship, cohort),
-- not an occasion you attend.
--
-- These recruit over a long window and have no single start time, so they sit
-- in a chronological feed for weeks looking like a stale event. Classified in
-- pipeline/classify.py, below the dated-cutoff check so an explicit
-- "Applications Due Friday" stays a student_deadline.
--
-- Hidden from public browse for now, alongside fundraiser/other. Adding it to
-- PUBLIC_CONTENT_KINDS (src/lib/events/content-kind.ts) is what would surface
-- these on a dedicated Applications tab.
--
-- ADD VALUE must commit before the value can be used, so the backfill that
-- reclassifies existing rows lives in the next migration.
alter type event_content_kind add value if not exists 'student_application'
  after 'student_deadline';
