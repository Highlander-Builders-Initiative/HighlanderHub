import {
  categoryLabel,
  dayWindowPhrase,
  type CategoryValue,
  type DayWindow,
} from "@/components/events/events-filters";
import { hostGroupPhrase, type HostGroupValue } from "@/lib/host-groups";

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
  freeFood: boolean;
  deadlines: boolean;
  hostGroup: HostGroupValue;
  hasHostGroup: boolean;
};

type EmptyFeedCopyContext = {
  what: string;
  win: string;
  quoted: string;
  dayWindow: DayWindow;
};

type EmptyFeedCopyFactory = (context: EmptyFeedCopyContext) => EmptyFeedCopy;

const EMPTY_HAS_QUERY = 1;
const EMPTY_HAS_FILTERS = 2;
const EMPTY_HAS_WINDOW = 4;

const EMPTY_COPY_BY_MASK: Record<number, EmptyFeedCopyFactory> = {
  [EMPTY_HAS_QUERY | EMPTY_HAS_FILTERS | EMPTY_HAS_WINDOW]: ({
    what,
    win,
    quoted,
  }) => ({
    headline: `No ${what} ${win} match ${quoted}.`,
    nudge:
      "Clearing the search opens this up faster than loosening the filters or the window.",
  }),
  [EMPTY_HAS_QUERY | EMPTY_HAS_FILTERS]: ({ what, quoted }) => ({
    headline: `No ${what} match ${quoted}.`,
    nudge: "Clear the search first; the filters are usually the smaller change.",
  }),
  [EMPTY_HAS_QUERY | EMPTY_HAS_WINDOW]: ({ win, quoted }) => ({
    headline: `Nothing ${win} matches ${quoted}.`,
    nudge: "Widen the window past " + win + ", or shorten the search.",
  }),
  [EMPTY_HAS_FILTERS | EMPTY_HAS_WINDOW]: ({ what, win }) => ({
    headline: `No ${what} ${win}.`,
    nudge: `Try opening the window past ${win}; the filters are a smaller pool than the date.`,
  }),
  [EMPTY_HAS_QUERY]: ({ quoted }) => ({
    headline: `Nothing on the bulletin matches ${quoted}.`,
    nudge:
      "Shorter or different words usually do it; titles, hosts, and tags are all searched.",
  }),
  [EMPTY_HAS_FILTERS]: ({ what }) => ({
    headline: `No ${what} queued right now.`,
    nudge: "Clear a filter to see more of what's up.",
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
    nudge: "Check back after the next refresh.",
  }),
};

/** "Hang out events with free food from faith groups", "Career & skills deadlines". */
function describeFilters(filters: EmptyFeedCopyFilters): string {
  const noun = filters.deadlines ? "deadlines" : "events";
  return [
    filters.hasCategory ? `${categoryLabel(filters.category)} ${noun}` : noun,
    filters.freeFood ? "with free food" : "",
    filters.hasHostGroup ? `from ${hostGroupPhrase(filters.hostGroup)}` : "",
  ]
    .filter(Boolean)
    .join(" ");
}

export function getEmptyFeedCopy(filters: EmptyFeedCopyFilters): EmptyFeedCopy {
  const hasFilters =
    filters.hasCategory || filters.freeFood || filters.deadlines || filters.hasHostGroup;
  const win = dayWindowPhrase(filters.dayWindow);
  const quoted = `“${filters.query}”`;
  const mask =
    (filters.hasQuery ? EMPTY_HAS_QUERY : 0) |
    (hasFilters ? EMPTY_HAS_FILTERS : 0) |
    (filters.hasDayWindow ? EMPTY_HAS_WINDOW : 0);

  return EMPTY_COPY_BY_MASK[mask]({
    what: describeFilters(filters),
    win,
    quoted,
    dayWindow: filters.dayWindow,
  });
}
