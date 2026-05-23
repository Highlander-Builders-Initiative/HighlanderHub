"use client";

import { useCallback, useState } from "react";
import { track } from "@/lib/analytics";
import { supabase } from "@/lib/supabase";
import {
  uploadSubmissionFlyer,
  type UploadStatus,
} from "@/lib/submission-flyer";

export type { UploadStatus };

export function useFlyerUpload() {
  const [status, setStatus] = useState<UploadStatus>({ kind: "idle" });

  const clearUpload = useCallback(() => {
    setStatus({ kind: "idle" });
  }, []);

  const uploadFlyer = useCallback(async (file: File) => {
    setStatus({ kind: "uploading" });
    const result = await uploadSubmissionFlyer(supabase, file);

    if (!result.ok) {
      if (result.trackMessage) {
        track("flyer_upload_error", { message: result.trackMessage });
      }
      setStatus(result.status);
      return;
    }

    track("flyer_uploaded", { size: file.size, type: file.type });
    setStatus(result.status);
  }, []);

  return { status, uploadFlyer, clearUpload };
}
