/** Day headers at or above this line (px from viewport top) become the active day while scrolling. */
export const SCROLL_SPY_OFFSET_PX = 96;

/** Prefer a day whose header has crossed the spy line over one that is only peeking in. */
const HEADER_CROSSED_BONUS = 1_000_000;

type ResolveObservedDayKeyArgs = {
  dayKeys: string[];
  headerTopByKey: Map<string, number>;
  sectionBottomByKey?: Map<string, number>;
  viewportHeight: number;
};

/**
 * Picks the day section most in view. Headers that have scrolled past the spy
 * offset win; otherwise the section with the largest visible area wins (covers
 * short final days with one event whose header never reaches the top band).
 */
export function resolveObservedDayKey({
  dayKeys,
  headerTopByKey,
  sectionBottomByKey,
  viewportHeight,
}: ResolveObservedDayKeyArgs): string | null {
  if (dayKeys.length === 0) return null;

  let active = dayKeys[0];
  let bestScore = -1;

  for (const key of dayKeys) {
    const top = headerTopByKey.get(key);
    if (top === undefined) continue;

    const sectionBottom = sectionBottomByKey?.get(key) ?? top;
    const visibleTop = Math.max(top, SCROLL_SPY_OFFSET_PX);
    const visibleBottom = Math.min(sectionBottom, viewportHeight);
    const visible = visibleBottom - visibleTop;
    if (visible <= 0) continue;

    const headerCrossed = top <= SCROLL_SPY_OFFSET_PX;
    const score = (headerCrossed ? HEADER_CROSSED_BONUS : 0) + visible;

    if (score > bestScore) {
      bestScore = score;
      active = key;
    }
  }

  return active;
}
