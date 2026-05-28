import { createClient, SupabaseClient } from "@supabase/supabase-js";
import crypto from "crypto";

const URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;

/**
 * Single source of truth for admin auth (login + session HMAC).
 * Fails closed when ADMIN_PASSWORD is unset.
 */
export function getAdminPassword(): string | null {
  return process.env.ADMIN_PASSWORD || null;
}

/**
 * Creates a server-side Supabase client using the service role key.
 * This client bypasses Row Level Security (RLS) policies and must NEVER
 * be exported to or used in client-side code.
 */
export function getAdminSupabase(): SupabaseClient {
  if (!URL || !SERVICE_KEY) {
    throw new Error(
      "Missing NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY. " +
        "Ensure they are set in your server environment."
    );
  }
  return createClient(URL, SERVICE_KEY, {
    auth: { persistSession: false },
    global: {
      fetch: (input, init) => fetch(input, { ...init, cache: "no-store" }),
    },
  });
}

/**
 * Signs an expiration timestamp using HMAC-SHA256 with the ADMIN_PASSWORD.
 * Returns a string formatted as "expiresAt.signature".
 */
export function signSession(expiresAt: number): string {
  const password = getAdminPassword();
  if (!password) {
    throw new Error("ADMIN_PASSWORD is not configured.");
  }
  const data = expiresAt.toString();
  const signature = crypto
    .createHmac("sha256", password)
    .update(data)
    .digest("hex");
  return `${data}.${signature}`;
}

/**
 * Verifies if a given session string is cryptographically valid and not expired.
 */
export function verifySession(sessionStr: string | undefined): boolean {
  if (!sessionStr) return false;

  const password = getAdminPassword();
  if (!password) return false;

  const parts = sessionStr.split(".");
  if (parts.length !== 2) return false;

  const [expiresAtStr, signature] = parts;
  const expiresAt = parseInt(expiresAtStr, 10);

  if (isNaN(expiresAt) || expiresAt < Date.now()) {
    return false; // Session is malformed or expired
  }

  // Generate the expected signature
  const expectedSignature = crypto
    .createHmac("sha256", password)
    .update(expiresAtStr)
    .digest("hex");

  // Constant-time comparison to prevent timing attacks
  try {
    const signatureBuffer = Buffer.from(signature, "hex");
    const expectedBuffer = Buffer.from(expectedSignature, "hex");

    if (signatureBuffer.length !== expectedBuffer.length) {
      return false;
    }

    return crypto.timingSafeEqual(signatureBuffer, expectedBuffer);
  } catch (err) {
    return false;
  }
}
