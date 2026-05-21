import type { CampusEvent, EventCategory } from "@/types/event";

const FEED_SESSION_KEY = "highlanderhub.eventFeed";
const RETURN_SCROLL_KEY = "highlanderhub.returnScroll";
const FEED_SESSION_TTL_MS = 10 * 60 * 1000;

export type SavedEventFeedSnapshot = {
  path: string;
  scrollY: number;
  events: CampusEvent[];
  hasMore: boolean;
  nextOffset: number;
  view: "list" | "calendar";
  category: EventCategory | "all";
  query: string;
  loadedCount: number;
  eventId?: string;
  eventTop?: number;
  savedAt: number;
};

type SavedEventFeedSnapshotInput = Omit<SavedEventFeedSnapshot, "savedAt">;
type SavedScrollPosition = {
  path: string;
  scrollY: number;
  detailPath: string;
  eventId?: string;
  eventTop?: number;
  loadedCount?: number;
};

let memorySnapshot: SavedEventFeedSnapshot | null = null;

function currentPath() {
  return `${window.location.pathname}${window.location.search}`;
}

function saveScrollPosition(
  detailPath: string,
  target?: {
    eventId?: string;
    eventTop?: number;
    loadedCount?: number;
  }
) {
  window.sessionStorage.setItem(
    RETURN_SCROLL_KEY,
    JSON.stringify({
      path: currentPath(),
      scrollY: window.scrollY,
      detailPath,
      ...target,
    })
  );
}

function readSavedScrollPosition() {
  const raw = window.sessionStorage.getItem(RETURN_SCROLL_KEY);
  if (!raw) return null;

  try {
    const parsed = JSON.parse(raw) as Partial<SavedScrollPosition>;
    if (
      typeof parsed.path !== "string" ||
      typeof parsed.scrollY !== "number" ||
      typeof parsed.detailPath !== "string"
    ) {
      return null;
    }
    return parsed as SavedScrollPosition;
  } catch {
    return null;
  }
}

function clearSavedScrollPosition() {
  window.sessionStorage.removeItem(RETURN_SCROLL_KEY);
}

function isExpired(savedAt: number) {
  return Date.now() - savedAt > FEED_SESSION_TTL_MS;
}

function readSessionSnapshot() {
  const raw = window.sessionStorage.getItem(FEED_SESSION_KEY);
  if (!raw) return null;

  try {
    const parsed = JSON.parse(raw) as Partial<SavedEventFeedSnapshot>;
    if (
      typeof parsed.path !== "string" ||
      typeof parsed.scrollY !== "number" ||
      typeof parsed.savedAt !== "number" ||
      !Array.isArray(parsed.events) ||
      typeof parsed.hasMore !== "boolean" ||
      typeof parsed.nextOffset !== "number" ||
      (parsed.view !== "list" && parsed.view !== "calendar") ||
      (parsed.category !== "all" &&
        parsed.category !== "club" &&
        parsed.category !== "academic" &&
        parsed.category !== "social" &&
        parsed.category !== "career" &&
        parsed.category !== "sports" &&
        parsed.category !== "arts" &&
        parsed.category !== "community" &&
        parsed.category !== "free_food") ||
      typeof parsed.query !== "string" ||
      typeof parsed.loadedCount !== "number"
    ) {
      return null;
    }

    if (isExpired(parsed.savedAt)) {
      window.sessionStorage.removeItem(FEED_SESSION_KEY);
      if (memorySnapshot?.savedAt === parsed.savedAt) {
        memorySnapshot = null;
      }
      return null;
    }

    return parsed as SavedEventFeedSnapshot;
  } catch {
    return null;
  }
}

function readSnapshot() {
  if (memorySnapshot && !isExpired(memorySnapshot.savedAt)) {
    if (memorySnapshot.path === currentPath()) {
      return memorySnapshot;
    }
  }

  const saved = readSessionSnapshot();
  if (!saved) return null;

  memorySnapshot = saved;
  return saved.path === currentPath() ? saved : null;
}

export function saveEventFeedSnapshot(snapshot: SavedEventFeedSnapshotInput) {
  if (typeof window === "undefined") return;

  memorySnapshot = {
    ...snapshot,
    savedAt: Date.now(),
  };

  window.sessionStorage.setItem(FEED_SESSION_KEY, JSON.stringify(memorySnapshot));
}

export function getSavedEventFeedSnapshot() {
  if (typeof window === "undefined") return null;
  return readSnapshot();
}

export function getSavedScrollPosition() {
  if (typeof window === "undefined") return null;
  return readSavedScrollPosition();
}

export function saveEventFeedReturn(
  detailPath: string,
  target?: {
    eventId?: string;
    eventTop?: number;
    loadedCount?: number;
  }
) {
  if (typeof window === "undefined") return;

  const snapshot = readSnapshot();
  if (snapshot) {
    saveEventFeedSnapshot({
      ...snapshot,
      eventId: target?.eventId,
      eventTop: target?.eventTop,
    });
  }
  saveScrollPosition(detailPath, {
    eventId: target?.eventId,
    eventTop: target?.eventTop,
    loadedCount: target?.loadedCount ?? snapshot?.loadedCount,
  });
}

export function clearEventFeedSnapshot() {
  if (typeof window === "undefined") return;

  memorySnapshot = null;
  window.sessionStorage.removeItem(FEED_SESSION_KEY);
}

export function clearEventFeedReturnState() {
  clearSavedScrollPosition();
}
