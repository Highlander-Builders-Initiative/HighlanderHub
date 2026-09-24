"use client";

import { useSyncExternalStore } from "react";

// How many in-app links to /events are waiting on their navigation. Links
// report here and the root layout draws the feed's skeleton while any are.
let holds = 0;
const listeners = new Set<() => void>();

function emit() {
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** Show the /events skeleton until the returned release is called. */
export function holdEventsNavSkeleton(): () => void {
  holds += 1;
  emit();
  let released = false;
  return () => {
    if (released) return;
    released = true;
    holds -= 1;
    emit();
  };
}

export function useEventsNavPending(): boolean {
  return useSyncExternalStore(
    subscribe,
    () => holds > 0,
    () => false
  );
}
