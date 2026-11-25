"use client";

import { useCallback, useState } from "react";
import type { AdminActionError, AdminPendingAction } from "./pending-action";

// Actions report expected failures as { success: false }. A throw means the
// session expired (requireAdmin) or the request never completed; production
// hides the thrown message, so say what to do instead.
export const ADMIN_ACTION_FAILED_MESSAGE =
  "That didn't go through. Your session may have expired: refresh the page, sign in again if asked, and retry.";

export function useAdminActions() {
  const [pendingAction, setPendingAction] = useState<AdminPendingAction | null>(
    null
  );
  // Each error belongs to the action that raised it, so it shows where the
  // admin acted: in the drawer, on the pair card, or on the event's row.
  const [actionError, setActionError] = useState<AdminActionError | null>(null);

  /** Runs fn; returns false when it threw (the error is already set). */
  const runAction = useCallback(
    async (action: AdminPendingAction, fn: () => Promise<void>) => {
      setPendingAction(action);
      setActionError(null);
      try {
        await fn();
        return true;
      } catch (error) {
        console.error("Admin action failed:", error);
        setActionError({ action, message: ADMIN_ACTION_FAILED_MESSAGE });
        return false;
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
