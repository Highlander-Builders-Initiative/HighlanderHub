"use client";

import { useSyncExternalStore } from "react";
import {
  SAVED_EVENTS_KEY,
  parseSavedIds,
  serializeSavedIds,
  toggleSavedId,
} from "@/lib/saved-events";

// A single module-level store backs every SaveButton on the page, so toggling
// one heart updates all views of the same event in the same tab (plain
// `storage` events only fire in *other* tabs). useSyncExternalStore reads from
// it; the server snapshot is a stable empty list to keep hydration clean.
const EMPTY: string[] = [];
let cache: string[] | null = null;
const listeners = new Set<() => void>();
let wired = false;

function read(): string[] {
  if (cache) return cache;
  if (typeof window === "undefined") return EMPTY;
  cache = parseSavedIds(window.localStorage.getItem(SAVED_EVENTS_KEY));
  return cache;
}

function emit() {
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  if (!wired && typeof window !== "undefined") {
    wired = true;
    window.addEventListener("storage", (event) => {
      if (event.key !== SAVED_EVENTS_KEY) return;
      cache = parseSavedIds(event.newValue);
      emit();
    });
  }
  return () => listeners.delete(listener);
}

function toggle(id: string) {
  const next = toggleSavedId(read(), id);
  cache = next;
  if (typeof window !== "undefined") {
    window.localStorage.setItem(SAVED_EVENTS_KEY, serializeSavedIds(next));
  }
  emit();
}

export function useSavedEvents() {
  const savedIds = useSyncExternalStore(subscribe, read, () => EMPTY);
  return { savedIds, toggle };
}
