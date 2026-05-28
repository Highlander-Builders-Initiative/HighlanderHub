-- Restrict anon submission inserts to the moderation-safe shape.
-- The previous policy used `with check (true)`, so any client holding the
-- public anon key (exposed in the browser) could POST straight to PostgREST
-- and set moderation columns directly — e.g. status = 'approved' to skip the
-- review queue, or write reviewed_at / review_notes. Constrain the check so
-- inserted rows must enter the queue pending and unreviewed. Column defaults
-- are applied before WITH CHECK runs, so normal submissions still pass.

drop policy if exists "submissions_public_insert" on submissions;

create policy "submissions_public_insert"
  on submissions for insert
  to anon, authenticated
  with check (
    status = 'pending'
    and reviewed_at is null
    and review_notes is null
  );
