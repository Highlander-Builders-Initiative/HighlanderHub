-- has_free_food: free food is an attribute of an event, not a kind of event.
--
-- Previously "free food" was jammed into the single-valued `category` enum, so
-- a club study session that hands out boba had to be EITHER 'club' OR
-- 'free_food' — the real category got erased. Split it into its own boolean so
-- category stays the event's actual type and free food is tracked independently.
--
-- Legacy rows with category = 'free_food' are intentionally left as-is (the enum
-- value is kept). They keep matching the Free Food filter via the category check
-- and phase out naturally as those events pass; no backfill.

alter table events
  add column has_free_food boolean not null default false;

alter table submissions
  add column has_free_food boolean not null default false;

-- Supports the home "free food this week" count and the browse filter.
create index events_has_free_food_idx on events (has_free_food)
  where has_free_food;
