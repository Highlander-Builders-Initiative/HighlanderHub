"use client";

import { useCallback, useRef, useState } from "react";
import { track } from "@/lib/analytics";
import { supabase } from "@/lib/supabase";
import {
  deleteSubmissionFlyer,
  uploadSubmissionFlyer,
  type UploadStatus,
} from "@/lib/submission-flyer";

export type { UploadStatus };

type UploadedStatus = Extract<UploadStatus, { kind: "uploaded" }>;

export function useFlyerUpload() {
  const [status, setStatus] = useState<UploadStatus>({ kind: "idle" });
  const uploadedRef = useRef<UploadedStatus | null>(null);

  const setUploadStatus = useCallback((nextStatus: UploadStatus) => {
    uploadedRef.current =
      nextStatus.kind === "uploaded" ? nextStatus : null;
    setStatus(nextStatus);
  }, []);

  const clearUpload = useCallback(async () => {
    const uploadToDelete = uploadedRef.current;
    setUploadStatus({ kind: "idle" });

    if (!uploadToDelete) return;

    const result = await deleteSubmissionFlyer(uploadToDelete);
    if (!result.ok) {
      track("flyer_delete_error", { message: result.message });
    }
  }, [setUploadStatus]);

  const uploadFlyer = useCallback(async (file: File) => {
    const previousUpload = uploadedRef.current;
    setUploadStatus({ kind: "uploading" });
    const result = await uploadSubmissionFlyer(supabase, file);

    if (!result.ok) {
      if (result.trackMessage) {
        track("flyer_upload_error", { message: result.trackMessage });
      }
      setUploadStatus(result.status);
      if (previousUpload) {
        const deleteResult = await deleteSubmissionFlyer(previousUpload);
        if (!deleteResult.ok) {
          track("flyer_delete_error", { message: deleteResult.message });
        }
      }
      return;
    }

    track("flyer_uploaded", { size: file.size, type: file.type });
    setUploadStatus(result.status);
    if (previousUpload) {
      const deleteResult = await deleteSubmissionFlyer(previousUpload);
      if (!deleteResult.ok) {
        track("flyer_delete_error", { message: deleteResult.message });
      }
    }
  }, [setUploadStatus]);

  return { status, uploadFlyer, clearUpload };
}
