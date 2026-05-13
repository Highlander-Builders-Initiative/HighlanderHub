-- Anon role needs an explicit INSERT grant on submissions, on top of the RLS
-- policy. Supabase's default grants for new tables don't cover INSERT for
-- anon — the policy alone isn't enough.

grant insert on table submissions to anon, authenticated;
