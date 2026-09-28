-- Topics are activities: what a student would be doing there.
--
-- 'club', 'social' and 'community' overlapped: "club" named the host, and
-- "community" was the keyword classifier's fallback, so it held nearly half the
-- feed. The pipeline now files an event as hangout, get_involved, career,
-- academic, sports, arts or volunteering, and 'other' when its text names no
-- activity (it then appears only under All). Who hosts is a separate filter,
-- read from the account directory, so no column is needed for it.
--
-- Run this file on its own, before the next file: Postgres cannot use an enum
-- value in the transaction that adds it. The legacy values stay in the type
-- (dropping one means rebuilding the enum) but nothing writes them.

alter type event_category add value if not exists 'hangout';
alter type event_category add value if not exists 'get_involved';
alter type event_category add value if not exists 'volunteering';
alter type event_category add value if not exists 'other';
