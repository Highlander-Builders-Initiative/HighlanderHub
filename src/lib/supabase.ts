import { createClient, SupabaseClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

if (!url || !anonKey) {
  throw new Error(
    "Missing NEXT_PUBLIC_SUPABASE_URL or NEXT_PUBLIC_SUPABASE_ANON_KEY. " +
      "Add them to .env.local."
  );
}

// Server-friendly singleton. We don't need session persistence — the public
// bulletin uses the anon key, which is read-only via RLS. Submissions also use
// the anon key (INSERT-only policy on the submissions table).
export const supabase: SupabaseClient = createClient(url, anonKey, {
  auth: { persistSession: false },
});
