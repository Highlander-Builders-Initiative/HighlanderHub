export type AdminPendingAction =
  | { type: "update"; id: string }
  | { type: "delete"; id: string }
  | { type: "merge"; id: string }
  | { type: "distinct"; id: string }
  | { type: "logout" };

/** A failed action and what to tell the admin, shown where they acted. */
export type AdminActionError = { action: AdminPendingAction; message: string };

export function isEventActionPending(
  pending: AdminPendingAction | null,
  eventId: string
): boolean {
  if (!pending) return false;
  return (
    (pending.type === "update" || pending.type === "delete") && pending.id === eventId
  );
}

export function isEventUpdatePending(
  pending: AdminPendingAction | null,
  eventId: string
): boolean {
  return pending?.type === "update" && pending.id === eventId;
}

/** The message for an error raised by one of `types` on `id`, if any. */
export function actionErrorFor(
  error: AdminActionError | null,
  types: AdminPendingAction["type"][],
  id?: string
): string | null {
  if (!error || !types.includes(error.action.type)) return null;
  if (id !== undefined && (!("id" in error.action) || error.action.id !== id)) return null;
  return error.message;
}
