export type AdminPendingAction =
  | { type: "update"; id: string }
  | { type: "delete"; id: string }
  | { type: "merge"; id: string }
  | { type: "distinct"; id: string }
  | { type: "logout" };

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
