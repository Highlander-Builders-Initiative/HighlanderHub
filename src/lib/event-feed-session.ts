import {
  EVENT_CATEGORIES,
  type CampusEvent,
  type EventCategory,
} from "@/types/event";
import { DAY_WINDOWS, type DayWindow } from "@/types/events-feed";

const FEED_SESSION_KEY = "highlanderhub.eventFeed";
const RETURN_SCROLL_KEY = "highlanderhub.returnScroll";
const FEED_SESSION_TTL_MS = 10 * 60 * 1000;

export type SavedEventFeedSnapshot = {
  path: string;
  scrollY: number;
  events: CampusEvent[];
  hasMore: boolean;
  nextOffset: number;
  category: EventCategory | "all";
  query: string;
  dayWindow: DayWindow;
  loadedCount: number;
  eventId?: string;
  eventTop?: number;
  savedAt: number;
};

type SavedEventFeedSnapshotInput = Omit<SavedEventFeedSnapshot, "savedAt">;
type SavedScrollPositionInput = {
  eventId?: string;
  eventTop?: number;
  loadedCount?: number;
};

export type SavedScrollPosition = {
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

function readSavedScrollPositionRaw() {
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

function writeSavedScrollPosition(
  detailPath: string,
  target?: SavedScrollPositionInput
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

function clearSavedScrollPosition() {
  window.sessionStorage.removeItem(RETURN_SCROLL_KEY);
}

function isExpired(savedAt: number) {
  return Date.now() - savedAt > FEED_SESSION_TTL_MS;
}

function isSavedDayWindow(value: unknown): value is DayWindow {
  return DAY_WINDOWS.some((window) => window.value === value);
}

function isSavedCategory(value: unknown): value is EventCategory | "all" {
  return (
    value === "all" || EVENT_CATEGORIES.includes(value as EventCategory)
  );
}

function readSessionSnapshot() {
  const raw = window.sessionStorage.getItem(FEED_SESSION_KEY);
  if (!raw) return null;

  try {
    const parsed = JSON.parse(raw) as Partial<SavedEventFeedSnapshot> & {
      view?: unknown;
    };
    if (
      typeof parsed.path !== "string" ||
      typeof parsed.scrollY !== "number" ||
      typeof parsed.savedAt !== "number" ||
      !Array.isArray(parsed.events) ||
      typeof parsed.hasMore !== "boolean" ||
      typeof parsed.nextOffset !== "number" ||
      (Object.prototype.hasOwnProperty.call(parsed, "view") &&
        parsed.view !== "list") ||
      !isSavedDayWindow(parsed.dayWindow) ||
      !isSavedCategory(parsed.category) ||
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

    const { view: _view, ...snapshot } = parsed;
    return snapshot as SavedEventFeedSnapshot;
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

export function getSavedEventFeedSnapshotForRestore() {
  if (typeof window === "undefined") return null;

  const returnScroll = readSavedScrollPositionRaw();
  if (!returnScroll || returnScroll.path !== currentPath()) return null;

  return readSnapshot();
}

export function getSavedScrollPosition() {
  if (typeof window === "undefined") return null;
  return readSavedScrollPositionRaw();
}

export function getSavedReturnPath() {
  if (typeof window === "undefined") return null;

  const saved = readSavedScrollPositionRaw();
  if (!saved || saved.detailPath !== currentPath()) return null;

  return saved.path;
}

export function saveEventFeedReturn(
  detailPath: string,
  target?: SavedScrollPositionInput
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
  writeSavedScrollPosition(detailPath, {
    eventId: target?.eventId,
    eventTop: target?.eventTop,
    loadedCount: target?.loadedCount ?? snapshot?.loadedCount,
  });
}

export function clearEventFeedReturnState() {
  // Restore success only clears the return-scroll marker.
  // The feed snapshot is intentionally left to TTL-based expiry.
  clearSavedScrollPosition();
}
