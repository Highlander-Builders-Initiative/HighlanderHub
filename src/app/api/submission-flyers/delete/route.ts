import { timingSafeEqual } from "node:crypto";
import { NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";
import { SUBMISSION_FLYER_BUCKET } from "@/lib/submission-flyer";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

type DeleteBody = {
  path?: unknown;
  cleanupToken?: unknown;
};

const PATH_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.(jpg|png|webp)$/i;

function readStorageConfig() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceRoleKey =
    process.env.SUPABASE_SERVICE_ROLE_KEY ?? process.env.SUPABASE_SERVICE_KEY;

  if (!url || !serviceRoleKey) return null;

  return { url, serviceRoleKey };
}

async function sha256Hex(value: string): Promise<string> {
  const bytes = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest("SHA-256", bytes);

  return Array.from(new Uint8Array(digest), (byte) =>
    byte.toString(16).padStart(2, "0")
  ).join("");
}

function isEqualHex(a: string, b: string): boolean {
  if (!/^[0-9a-f]{64}$/i.test(a) || !/^[0-9a-f]{64}$/i.test(b)) {
    return false;
  }

  return timingSafeEqual(Buffer.from(a, "hex"), Buffer.from(b, "hex"));
}

function readCleanupTokenHash(metadata: unknown): string | null {
  if (!metadata || typeof metadata !== "object") return null;

  const record = metadata as Record<string, unknown>;
  const value = record.cleanup_token_sha256 ?? record.cleanupTokenSha256;
  return typeof value === "string" ? value : null;
}

export async function POST(request: Request) {
  const config = readStorageConfig();
  if (!config) {
    return NextResponse.json(
      { error: "Storage cleanup is not configured." },
      { status: 503 }
    );
  }

  let body: DeleteBody;
  try {
    body = (await request.json()) as DeleteBody;
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  if (
    typeof body.path !== "string" ||
    typeof body.cleanupToken !== "string" ||
    !PATH_PATTERN.test(body.path)
  ) {
    return NextResponse.json(
      { error: "Invalid flyer cleanup request." },
      { status: 400 }
    );
  }

  const supabase = createClient(config.url, config.serviceRoleKey, {
    auth: { persistSession: false },
  });
  const bucket = supabase.storage.from(SUBMISSION_FLYER_BUCKET);
  const { data: info, error: infoError } = await bucket.info(body.path);

  if (infoError || !info) {
    return NextResponse.json({ error: "Flyer not found." }, { status: 404 });
  }

  const storedHash = readCleanupTokenHash(info.metadata);
  const requestHash = await sha256Hex(body.cleanupToken);

  if (!storedHash || !isEqualHex(storedHash, requestHash)) {
    return NextResponse.json(
      { error: "Flyer cleanup token mismatch." },
      { status: 403 }
    );
  }

  const { error: deleteError } = await bucket.remove([body.path]);

  if (deleteError) {
    return NextResponse.json(
      { error: "Could not delete flyer." },
      { status: 500 }
    );
  }

  return NextResponse.json({ ok: true });
}
