const STORAGE_KEY = "highlanderhub.returnScroll";
export type SavedScrollPosition = {
  path: string;
  scrollY: number;
  detailPath: string;
  eventId?: string;
  eventTop?: number;
  loadedCount?: number;
};

function currentPath() {
  return `${window.location.pathname}${window.location.search}`;
}

export function saveScrollPosition(
  detailPath: string,
  target?: {
    eventId?: string;
    eventTop?: number;
    loadedCount?: number;
  }
) {
  if (typeof window === "undefined") return;

  window.sessionStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({
      path: currentPath(),
      scrollY: window.scrollY,
      detailPath,
      ...target,
    })
  );
}

function readSavedScrollPosition() {
  const saved = window.sessionStorage.getItem(STORAGE_KEY);
  if (!saved) return null;

  try {
    const parsed = JSON.parse(saved) as {
      path?: unknown;
      scrollY?: unknown;
      detailPath?: unknown;
      eventId?: unknown;
      eventTop?: unknown;
      loadedCount?: unknown;
    };
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

export function getSavedScrollPosition() {
  if (typeof window === "undefined") return null;
  return readSavedScrollPosition();
}

export function getSavedReturnPath() {
  if (typeof window === "undefined") return null;

  const saved = readSavedScrollPosition();
  if (!saved || saved.detailPath !== currentPath()) return null;

  return saved.path;
}

export function clearSavedScrollPosition() {
  if (typeof window === "undefined") return;
  window.sessionStorage.removeItem(STORAGE_KEY);
}

export function restoreScrollPosition() {
  if (typeof window === "undefined") return false;

  const saved = readSavedScrollPosition();

  if (!saved || saved.path !== currentPath()) {
    return false;
  }

  if (saved.eventId && saved.path.startsWith("/events")) {
    return false;
  }

  const root = document.scrollingElement ?? document.documentElement;
  root.scrollTop = saved.scrollY;
  clearSavedScrollPosition();

  return true;
}
