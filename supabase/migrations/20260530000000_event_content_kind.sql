-- content_kind: one inclusion contract shared by the pipeline, API, admin,
-- submissions, and UI.
--
--   student_event    — attendable student-relevant event (default).
--   student_deadline — student-relevant deadline/application (shown, labeled).
--   fundraiser       — donation / benefit drive (hidden from public browse).
--   other            — official/unrelated item, not student-relevant (hidden).
--
-- Public /events shows only student_event + student_deadline. fundraiser and
-- other stay queryable for admins (correction/audit) but never appear in the
-- public feed, counts, calendar, or home surfaces.

create type event_content_kind as enum (
  'student_event', 'student_deadline', 'fundraiser', 'other'
);

-- Existing rows predate classification; default them (and manual rows) to
-- student_event so nothing currently live disappears on deploy.
alter table events
  add column content_kind event_content_kind not null default 'student_event';

create index events_content_kind_idx on events (content_kind);

-- The public submit form only offers Event / Deadline, but keep the column on
-- submissions so the chosen kind survives review and copies into events on
-- approval.
alter table submissions
  add column content_kind event_content_kind not null default 'student_event';
