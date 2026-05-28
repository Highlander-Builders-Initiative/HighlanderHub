export type AdminPendingAction =
  | { type: "approve"; id: string }
  | { type: "reject"; id: string }
  | { type: "update"; id: string }
  | { type: "delete"; id: string }
  | { type: "logout" };

export function isSubmissionActionPending(
  pending: AdminPendingAction | null,
  submissionId: string
): boolean {
  if (!pending) return false;
  return (
    (pending.type === "approve" || pending.type === "reject") &&
    pending.id === submissionId
  );
}

export function isEventActionPending(
  pending: AdminPendingAction | null,
  eventId: string
): boolean {
  if (!pending) return false;
  return (
    (pending.type === "update" || pending.type === "delete") && pending.id === eventId
  );
}

export function isRejectDialogPending(
  pending: AdminPendingAction | null,
  submissionId: string
): boolean {
  return pending?.type === "reject" && pending.id === submissionId;
}

export function isEventUpdatePending(
  pending: AdminPendingAction | null,
  eventId: string
): boolean {
  return pending?.type === "update" && pending.id === eventId;
}
