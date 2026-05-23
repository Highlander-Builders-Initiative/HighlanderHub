import {
  categoryLabel,
  dayWindowPhrase,
  type CategoryValue,
  type DayWindow,
} from "@/components/events/events-filters";

export type EmptyFeedCopy = {
  headline: string;
  nudge: string;
};

export type EmptyFeedCopyFilters = {
  query: string;
  hasQuery: boolean;
  category: CategoryValue;
  hasCategory: boolean;
  dayWindow: DayWindow;
  hasDayWindow: boolean;
};

type EmptyFeedCopyContext = {
  cat: string;
  win: string;
  quoted: string;
  dayWindow: DayWindow;
};

type EmptyFeedCopyFactory = (context: EmptyFeedCopyContext) => EmptyFeedCopy;

const EMPTY_HAS_QUERY = 1;
const EMPTY_HAS_CATEGORY = 2;
const EMPTY_HAS_WINDOW = 4;

const EMPTY_COPY_BY_MASK: Record<number, EmptyFeedCopyFactory> = {
  [EMPTY_HAS_QUERY | EMPTY_HAS_CATEGORY | EMPTY_HAS_WINDOW]: ({
    cat,
    win,
    quoted,
  }) => ({
    headline: `Nothing in ${cat} ${win} matches ${quoted}.`,
    nudge:
      "Clearing the search opens this up faster than loosening the category or window.",
  }),
  [EMPTY_HAS_QUERY | EMPTY_HAS_CATEGORY]: ({ cat, quoted }) => ({
    headline: `Nothing in ${cat} matches ${quoted}.`,
    nudge: "Clear the search first; the category is usually the smaller change.",
  }),
  [EMPTY_HAS_QUERY | EMPTY_HAS_WINDOW]: ({ win, quoted }) => ({
    headline: `Nothing ${win} matches ${quoted}.`,
    nudge: "Widen the window past " + win + ", or shorten the search.",
  }),
  [EMPTY_HAS_CATEGORY | EMPTY_HAS_WINDOW]: ({ cat, win }) => ({
    headline: `No ${cat} ${win}.`,
    nudge: `Try opening the window past ${win}; ${cat} is a smaller pool than the date.`,
  }),
  [EMPTY_HAS_QUERY]: ({ quoted }) => ({
    headline: `Nothing on the bulletin matches ${quoted}.`,
    nudge:
      "Shorter or different words usually do it; titles, hosts, and tags are all searched.",
  }),
  [EMPTY_HAS_CATEGORY]: ({ cat }) => ({
    headline: `No ${cat} queued right now.`,
    nudge: "Switch back to All to see everything that's up.",
  }),
  [EMPTY_HAS_WINDOW]: ({ win, dayWindow }) => ({
    headline: `Nothing on the calendar ${win}.`,
    nudge:
      dayWindow === "today"
        ? "Try This week or Weekend instead."
        : "Open the window to Anytime to see what's queued.",
  }),
  0: () => ({
    headline: "The bulletin's quiet right now.",
    nudge: "Check back later, or be the first to put something up.",
  }),
};

export function getEmptyFeedCopy(filters: EmptyFeedCopyFilters): EmptyFeedCopy {
  const cat = categoryLabel(filters.category);
  const win = dayWindowPhrase(filters.dayWindow);
  const quoted = `“${filters.query}”`;
  const mask =
    (filters.hasQuery ? EMPTY_HAS_QUERY : 0) |
    (filters.hasCategory ? EMPTY_HAS_CATEGORY : 0) |
    (filters.hasDayWindow ? EMPTY_HAS_WINDOW : 0);

  return EMPTY_COPY_BY_MASK[mask]({
    cat,
    win,
    quoted,
    dayWindow: filters.dayWindow,
  });
}
