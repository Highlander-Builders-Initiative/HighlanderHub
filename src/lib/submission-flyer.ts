import type { SupabaseClient } from "@supabase/supabase-js";

export type UploadStatus =
  | { kind: "idle" }
  | { kind: "uploading" }
  | { kind: "uploaded"; url: string }
  | { kind: "error"; message: string };

const FLYER_BUCKET = "submission-flyers";
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
  const { data, error } = await supabase.storage
    .from(FLYER_BUCKET)
    .upload(path, file, {
      contentType: file.type,
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
    .from(FLYER_BUCKET)
    .getPublicUrl(data.path);

  return {
    ok: true,
    status: { kind: "uploaded", url: publicData.publicUrl },
  };
}
