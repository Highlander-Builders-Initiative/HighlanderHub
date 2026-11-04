"use client";

import { useCallback, useState } from "react";
import type { AdminPendingAction } from "./pending-action";

// Actions report expected failures as { success: false }. A throw means the
// session expired (requireAdmin) or the request never completed; production
// hides the thrown message, so say what to do instead.
export const ADMIN_ACTION_FAILED_MESSAGE =
  "That didn't go through. Your session may have expired: refresh the page, sign in again if asked, and retry.";

export function useAdminActions() {
  const [pendingAction, setPendingAction] = useState<AdminPendingAction | null>(
    null
  );
  const [actionError, setActionError] = useState<string | null>(null);

  const runAction = useCallback(
    async (action: AdminPendingAction, fn: () => Promise<void>) => {
      setPendingAction(action);
      setActionError(null);
      try {
        await fn();
      } catch (error) {
        console.error("Admin action failed:", error);
        setActionError(ADMIN_ACTION_FAILED_MESSAGE);
      } finally {
        setPendingAction(null);
      }
    },
    []
  );

  return {
    pendingAction,
    actionError,
    setActionError,
    runAction,
  };
}
