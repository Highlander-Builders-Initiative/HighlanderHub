import matcher from "next/dist/shared/lib/match-remote-pattern.js";
import nextConfig from "../../next.config.js";

export const remotePatterns = nextConfig.images?.remotePatterns ?? [];

export const supabaseOrigin = new URL(
  process.env.NEXT_PUBLIC_SUPABASE_URL ??
    "https://qyxlojftdtjasxhzyqil.supabase.co"
).origin;

export function optimizerAllows(url) {
  return matcher.hasRemoteMatch([], remotePatterns, new URL(url));
}
