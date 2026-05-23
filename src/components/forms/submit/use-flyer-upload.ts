"use client";

import { useCallback, useState } from "react";
import { track } from "@/lib/analytics";
import { supabase } from "@/lib/supabase";
import {
  deleteSubmissionFlyer,
  uploadSubmissionFlyer,
  type UploadStatus,
} from "@/lib/submission-flyer";

export type { UploadStatus };

export function useFlyerUpload() {
  const [status, setStatus] = useState<UploadStatus>({ kind: "idle" });

  const clearUpload = useCallback(async () => {
    const uploadToDelete = status.kind === "uploaded" ? status : null;
    setStatus({ kind: "idle" });

    if (!uploadToDelete) return;

    const result = await deleteSubmissionFlyer(uploadToDelete);
    if (!result.ok) {
      track("flyer_delete_error", { message: result.message });
    }
  }, [status]);

  const uploadFlyer = useCallback(async (file: File) => {
    const previousUpload = status.kind === "uploaded" ? status : null;
    setStatus({ kind: "uploading" });
    const result = await uploadSubmissionFlyer(supabase, file);

    if (!result.ok) {
      if (result.trackMessage) {
        track("flyer_upload_error", { message: result.trackMessage });
      }
      setStatus(result.status);
      if (previousUpload) {
        const deleteResult = await deleteSubmissionFlyer(previousUpload);
        if (!deleteResult.ok) {
          track("flyer_delete_error", { message: deleteResult.message });
        }
      }
      return;
    }

    track("flyer_uploaded", { size: file.size, type: file.type });
    setStatus(result.status);
    if (previousUpload) {
      const deleteResult = await deleteSubmissionFlyer(previousUpload);
      if (!deleteResult.ok) {
        track("flyer_delete_error", { message: deleteResult.message });
      }
    }
  }, [status]);

  return { status, uploadFlyer, clearUpload };
}
