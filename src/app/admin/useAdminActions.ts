"use client";

import { useCallback, useState } from "react";
import type { AdminPendingAction } from "./pending-action";

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
