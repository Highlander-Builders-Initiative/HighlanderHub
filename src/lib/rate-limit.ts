import { isIP } from "node:net";

type HeaderGetter = { get(name: string): string | null };

/**
 * Production runs behind Vercel, which overwrites these headers with the
 * connecting client's address. Other hosts must provide the same trusted-proxy
 * boundary. Missing/invalid addresses share a bucket instead of bypassing limits.
 */
export function clientIp(headers: HeaderGetter): string {
  const forwarded = headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  if (forwarded && isIP(forwarded)) return forwarded;
  const real = headers.get("x-real-ip")?.trim();
  if (real && isIP(real)) return real;
  return "unknown";
}
