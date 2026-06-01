// Dependency-free, in-memory rate limiter (fixed window per key).
//
// LIMITATION — serverless: state lives in a single process's memory. On Vercel
// each function instance keeps its own Map and instances are recycled, so this
// is best-effort: a distributed attacker spread across many instances is not
// fully throttled. It reliably stops a single client hammering one warm
// instance and raises the bar for casual abuse and password brute-force.
//
// To make limits durable and global, swap the `store` Map for Upstash/Redis
// (e.g. @upstash/ratelimit). No call site changes — keep the same return shape.

export type RateLimitConfig = {
  /** Max requests allowed per window. */
  limit: number;
  /** Window length in milliseconds. */
  windowMs: number;
};

export type RateLimitResult = {
  ok: boolean;
  limit: number;
  remaining: number;
  /** Epoch milliseconds when the current window resets. */
  resetAt: number;
  /** Seconds the client should wait before retrying (0 when allowed). */
  retryAfterSeconds: number;
};

type Entry = { count: number; resetAt: number };

const store = new Map<string, Entry>();

// Periodically evict expired entries so the Map can't grow without bound when
// many distinct keys (IPs) pass through. Cheap and amortized across calls.
const SWEEP_INTERVAL_MS = 60_000;
let lastSweep = 0;

function sweep(now: number): void {
  if (now - lastSweep < SWEEP_INTERVAL_MS) return;
  lastSweep = now;
  for (const [key, entry] of store) {
    if (entry.resetAt <= now) store.delete(key);
  }
}

/**
 * Records one hit against `key` and reports whether it is within the limit.
 * Atomic for a single process: check + increment happen together.
 */
export function rateLimit(key: string, config: RateLimitConfig): RateLimitResult {
  const { limit, windowMs } = config;
  const now = Date.now();
  sweep(now);

  const existing = store.get(key);

  // Fresh window: either no record, or the previous window already expired.
  if (!existing || existing.resetAt <= now) {
    const resetAt = now + windowMs;
    store.set(key, { count: 1, resetAt });
    return { ok: true, limit, remaining: limit - 1, resetAt, retryAfterSeconds: 0 };
  }

  if (existing.count >= limit) {
    return {
      ok: false,
      limit,
      remaining: 0,
      resetAt: existing.resetAt,
      retryAfterSeconds: Math.max(1, Math.ceil((existing.resetAt - now) / 1000)),
    };
  }

  existing.count += 1;
  return {
    ok: true,
    limit,
    remaining: limit - existing.count,
    resetAt: existing.resetAt,
    retryAfterSeconds: 0,
  };
}

type HeaderGetter = { get(name: string): string | null };

/**
 * Best-effort client IP from proxy headers. On Vercel `x-forwarded-for` is set
 * to the real client IP (leftmost entry); `x-real-ip` is a fallback. Returns
 * "unknown" when neither is present (e.g. local dev) — callers then share one
 * bucket, which is acceptable since production always has the forwarded header.
 */
export function clientIp(headers: HeaderGetter): string {
  const forwarded = headers.get("x-forwarded-for");
  if (forwarded) {
    const first = forwarded.split(",")[0]?.trim();
    if (first) return first;
  }
  const real = headers.get("x-real-ip");
  if (real && real.trim()) return real.trim();
  return "unknown";
}

/** Standard rate-limit response headers (incl. Retry-After when throttled). */
export function rateLimitHeaders(result: RateLimitResult): Record<string, string> {
  const headers: Record<string, string> = {
    "RateLimit-Limit": String(result.limit),
    "RateLimit-Remaining": String(result.remaining),
    "RateLimit-Reset": String(Math.ceil(result.resetAt / 1000)),
  };
  if (!result.ok) {
    headers["Retry-After"] = String(result.retryAfterSeconds);
  }
  return headers;
}

// --- Tunable limits (per IP) -------------------------------------------------

/** Public event submissions: deliberate, low-frequency human action. */
export const SUBMISSION_RATE_LIMIT: RateLimitConfig = {
  limit: 5,
  windowMs: 15 * 60_000, // 5 submissions / 15 min
};

/** Admin login: strict, to blunt password brute-force. */
export const ADMIN_LOGIN_RATE_LIMIT: RateLimitConfig = {
  limit: 5,
  windowMs: 10 * 60_000, // 5 attempts / 10 min
};
