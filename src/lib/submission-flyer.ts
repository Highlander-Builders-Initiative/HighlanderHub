import type { SupabaseClient } from "@supabase/supabase-js";
import { sha256Hex } from "@/lib/crypto";

export type UploadStatus =
  | { kind: "idle" }
  | { kind: "uploading" }
  | { kind: "uploaded"; url: string; path: string; cleanupToken: string }
  | { kind: "error"; message: string };

export const SUBMISSION_FLYER_BUCKET = "submission-flyers";
const FLYER_MAX_BYTES = 5 * 1024 * 1024;
const FLYER_MIME_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);
const FLYER_EXT_BY_TYPE: Record<string, string> = {
  "image/jpeg": "jpg",
  "image/png": "png",
  "image/webp": "webp",
};

export type FlyerUploadResult =
  | { ok: true; status: Extract<UploadStatus, { kind: "uploaded" }> }
  | {
      ok: false;
      status: Extract<UploadStatus, { kind: "error" }>;
      trackMessage?: string;
    };

export type FlyerDeleteResult =
  | { ok: true }
  | { ok: false; message: string };

export async function uploadSubmissionFlyer(
  supabase: SupabaseClient,
  file: File
): Promise<FlyerUploadResult> {
  if (!FLYER_MIME_TYPES.has(file.type)) {
    return {
      ok: false,
      status: { kind: "error", message: "Use a JPG, PNG, or WebP image." },
    };
  }

  if (file.size > FLYER_MAX_BYTES) {
    return {
      ok: false,
      status: { kind: "error", message: "Image must be 5 MB or smaller." },
    };
  }

  const ext = FLYER_EXT_BY_TYPE[file.type] ?? "jpg";
  const path = `${crypto.randomUUID()}.${ext}`;
  const cleanupToken = crypto.randomUUID();
  const cleanupTokenHash = await sha256Hex(cleanupToken);
  const { data, error } = await supabase.storage
    .from(SUBMISSION_FLYER_BUCKET)
    .upload(path, file, {
      contentType: file.type,
      metadata: { cleanup_token_sha256: cleanupTokenHash },
      upsert: false,
    });

  if (error || !data) {
    return {
      ok: false,
      status: {
        kind: "error",
        message: "Couldn’t upload. Try again, or paste a URL below.",
      },
      trackMessage: error?.message ?? "unknown",
    };
  }

  const { data: publicData } = supabase.storage
    .from(SUBMISSION_FLYER_BUCKET)
    .getPublicUrl(data.path);

  return {
    ok: true,
    status: {
      kind: "uploaded",
      url: publicData.publicUrl,
      path: data.path,
      cleanupToken,
    },
  };
}

export async function deleteSubmissionFlyer({
  path,
  cleanupToken,
}: Extract<UploadStatus, { kind: "uploaded" }>): Promise<FlyerDeleteResult> {
  try {
    const response = await fetch("/api/submission-flyers/delete", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ path, cleanupToken }),
    });

    if (response.ok) return { ok: true };

    const body = (await response.json().catch(() => null)) as {
      error?: string;
    } | null;

    return {
      ok: false,
      message: body?.error ?? `delete failed with ${response.status}`,
    };
  } catch (error) {
    return {
      ok: false,
      message: error instanceof Error ? error.message : "unknown",
    };
  }
}
