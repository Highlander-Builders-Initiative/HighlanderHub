-- Retire the legacy categories on rows the pipeline will not rewrite.
--
-- Run after 20260928000000_activity_categories.sql has committed. Every
-- publication run rebuilds each current listing's category, so this only
-- settles what that leaves behind: locked (admin-edited) rows and listings the
-- run withholds. 'social' was already an activity; 'club' and 'community'
-- were not, so those rows wait under All for an admin or the next rewrite.

-- Legacy free-food rows carried the fact only in their category.
update events set has_free_food = true
  where category = 'free_food' and not has_free_food;

update events
  set category = case category when 'social' then 'hangout' else 'other' end::event_category
  where category in ('club', 'social', 'community', 'free_food');

alter table events alter column category set default 'other';
