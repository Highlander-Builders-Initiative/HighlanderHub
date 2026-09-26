import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { test } from "node:test";

const sourceFile = (path) => new URL(`../${path}`, import.meta.url);
const read = (path) => readFileSync(sourceFile(path), "utf8");
const walk = (dir) =>
  readdirSync(sourceFile(dir), { recursive: true }).map((file) => `${dir}/${file}`);

test("event browser paginates the list instead of rendering every event at once", () => {
  const browser = read("src/components/events/EventsBrowser.tsx");
  const navigation = read("src/components/events/useEventFeedNavigation.ts");
  const loader = read("src/components/events/useInfiniteEventFeedLoader.ts");
  const data = read("src/lib/events/index.ts");
  const eventsApi = read("src/lib/events/api.ts");
  const api = read("src/app/api/events/route.ts");

  assert.match(data, /EVENTS_PAGE_SIZE/);
  assert.match(data, /\.range\(/);
  assert.match(api, /searchParams/);
  assert.match(eventsApi, /fetch\(`\/api\/events\?\$\{params\}`\)/);
  assert.match(eventsApi, /params\.set\("limit"/);
  assert.match(loader, /IntersectionObserver/);
  assert.match(loader, /scheduleRetry/);
  assert.match(loader, /setTimeout/);
  assert.match(loader, /isWithinLoadMargin/);
  assert.match(loader, /LOAD_ROOT_MARGIN_PX/);
  const observedDayHook = read("src/components/events/useObservedDayKey.ts");
  assert.match(observedDayHook, /addEventListener\("scroll"/);
  assert.doesNotMatch(observedDayHook, /IntersectionObserver/);
  assert.match(observedDayHook, /dayKeys\[0\]\s*\?\?\s*initialDayKey/);
  const observedDayKey = read("src/lib/events/observed-day-key.ts");
  assert.match(observedDayKey, /HEADER_CROSSED_BONUS/);
  assert.match(observedDayKey, /visibleBottom - visibleTop/);
  assert.match(observedDayKey, /resolveObservedDayKey/);
  assert.match(browser, /useEventFeedNavigation/);
  assert.match(navigation, /loadMoreRef/);
  assert.match(navigation, /fetchEventsPage\(nextOffset, undefined, requested\)/);
  assert.doesNotMatch(browser, /Load more/);
  assert.match(browser, /hasMore/);
});

test("events page header uses full upcoming event totals", () => {
  const page = read("src/app/events/page.tsx");
  const feedColumn = read("src/components/events/EventsFeedColumn.tsx");
  const data = read("src/lib/events/index.ts");

  assert.match(data, /getEventsSummary/);
  assert.match(data, /head: true/);
  assert.match(data, /count:/);
  assert.match(page, /getEventsUpcomingThisWeek/);
  assert.match(page, /summary=\{\{ upcomingThisWeek \}\}/);
  // The events header requests only the count it displays.
  assert.match(feedColumn, /summary\.upcomingThisWeek/);
  assert.doesNotMatch(page, /events\.length/);
  // "This week" counts what the Week filter lists, not a rolling 7 days.
  assert.match(data, /dayWindowRange\("week"\)/);
  assert.doesNotMatch(data, /inSevenDays/);
});

test("home page leads from the wall and hero words into the feed", () => {
  const homePage = read("src/app/page.tsx");
  const highlights = read("src/components/home/hero-highlights.tsx");

  assert.match(homePage, /\/events\?when=week/);
  assert.match(homePage, /See all \$\{weekCount\} this week/);
  assert.match(highlights, /href=\{`\/events\?cat=\$\{item\.category\}`\}/);
  // The editors' note counts tracked accounts from the pipeline's list.
  assert.match(homePage, /TRACKED_ACCOUNT_COUNT/);
  assert.doesNotMatch(homePage, /instead of \d+/);
});

test("calendar loads its own month-range events outside feed pagination", () => {
  const page = read("src/app/events/page.tsx");
  const browser = read("src/components/events/EventsBrowser.tsx");
  const navigation = read("src/components/events/useEventFeedNavigation.ts");
  const calendarHook = read("src/components/events/useCalendarMonthEvents.ts");
  const restoreHook = read("src/components/events/useEventFeedRestore.ts");
  const filters = read("src/components/events/useEventFeedFilters.ts");
  const feedColumn = read("src/components/events/EventsFeedColumn.tsx");
  const calendar = read("src/components/events/EventsMiniCalendar.tsx");
  const data = read("src/lib/events/index.ts");
  const supabase = read("src/lib/supabase.ts");
  const eventsApi = read("src/lib/events/api.ts");
  const calendarApi = read("src/app/api/events/calendar/route.ts");

  assert.match(data, /export const getCalendarEvents = cachePublicRead\(/);
  assert.match(data, /\.gte\("starts_at", startIso\)/);
  assert.match(data, /\.lt\("starts_at", endIso\)/);
  assert.match(data, /parsePacificDateTimeInput\(`\$\{startDayKey\}T00:00`\)/);
  assert.doesNotMatch(data, /calendar events"[\s\S]*activeEventFilter/);
  assert.match(supabase, /cache: "no-store"/);
  assert.match(supabase, /global: \{ fetch: uncachedFetch \}/);
  assert.match(page, /getCalendarEvents/);
  assert.match(page, /calendarEvents=\{calendarEvents\}/);
  assert.match(calendarApi, /getCalendarEvents/);
  assert.match(calendarApi, /searchParams/);
  assert.match(eventsApi, /fetchCalendarEvents/);
  assert.match(browser, /useCalendarMonthEvents/);
  assert.match(browser, /isCalendarLoading/);
  assert.match(browser, /useEventFeedRestore/);
  assert.match(browser, /useEventFeedNavigation/);
  assert.match(navigation, /mergeUniqueEventsByStart\(current, eventsToMerge\)/);
  assert.match(navigation, /key >= lastLoadedDay && key <= dayKey/);
  assert.match(navigation, /calendarJumpSuppressUntilRef/);
  assert.match(navigation, /calendarJumpEndsAtLoadedBoundary/);
  assert.match(browser, /hideLoadMoreHint=\{hideLoadMoreHint\}/);
  assert.match(navigation, /pendingLoadAnchorRef/);
  assert.match(navigation, /getBoundingClientRect\(\)\.top/);
  assert.match(navigation, /root\.scrollTop \+= delta/);
  assert.doesNotMatch(navigation, /setHasMore\(false\)[\s\S]*calendarJumpEndsAtLoadedBoundary/);
  const calendarPagination = read("src/lib/events/calendar-feed-pagination.ts");
  assert.match(calendarPagination, /calendarEventsInMonth/);
  assert.match(calendarPagination, /monthKeyFromDayKey\(dayKey\)/);
  assert.match(calendarPagination, /eventsOnTargetDay/);
  assert.doesNotMatch(
    navigation,
    /handleCalendarSelect[\s\S]*setNextOffset\(merged\.length\)/
  );
  assert.match(
    navigation,
    /handleCalendarSelect[\s\S]*setObservedDayKey\(dayKey\)/
  );
  assert.match(feedColumn, /scroll-mt-24/);
  assert.match(filters, /calendarEvents\?: CampusEvent\[\]/);
  assert.match(filters, /of \$\{feedTotal\}/);
  assert.match(feedColumn, /upcomingTotal/);
  assert.match(filters, /const calendarGrouped = useMemo/);
  assert.match(filters, /for \(const \[key, evs\] of calendarGrouped\)/);
  assert.match(calendar, /pacificCalendarGridRange/);
  assert.match(calendar, /aria-busy=\{isLoading\}/);
  assert.match(calendar, /heatClass/);
  assert.match(calendar, /countsByDay\.get\(key\)/);
  assert.match(calendar, /!isLoading && !error && inMonth \? heatClass\(count\) : ""/);
  // Empty days fade once the month's counts are in.
  assert.match(calendar, /!isLoading && !error && count === 0 \? "text-faint" : "text-ink"/);
  assert.match(calendarHook, /fetchCalendarEvents\(calendarRange\.start, calendarRange\.end\)/);
  assert.match(calendarHook, /isCalendarLoading/);
  assert.match(calendarHook, /useEffect/);
  assert.match(restoreHook, /restoreSavedEventFeedSpot/);
  assert.match(restoreHook, /useLayoutEffect/);
  assert.doesNotMatch(browser, /fetchCalendarEvents\(calendarRange\.start, calendarRange\.end\)/);
  assert.doesNotMatch(browser, /restoreSavedEventFeedSpot/);
});

test("app routes expose loading UI while server data resolves", () => {
  const sharedLoading = read("src/components/ui/RouteLoadingPage.tsx");
  const routeLoaders = [
    "src/app/about/loading.tsx",
  ];

  assert.match(sharedLoading, /aria-busy="true"/);
  assert.match(sharedLoading, /RouteLoadingPage/);

  for (const route of routeLoaders) {
    const source = read(route);
    assert.match(source, /RouteLoadingPage/);
  }

  // The landing page has no loading route on purpose: it is the site's front
  // door, and a full-page interstitial there reads as a stall, not as progress.
  assert.equal(existsSync(sourceFile("src/app/loading.tsx")), false);
});

test("event detail loading renders handed-off events inside the card layout", () => {
  const loader = read("src/app/@modal/(.)events/[id]/loading.tsx");
  const loading = read("src/components/events/EventDetailLoading.tsx");
  const view = read("src/components/events/EventDetailView.tsx");
  const page = read("src/app/events/[id]/page.tsx");
  const card = read("src/components/events/EventCard.tsx");

  // Same shell as the page, not the generic interstitial.
  assert.doesNotMatch(loader, /RouteLoadingPage/);
  assert.match(loader, /EventModalDetailLoading/);
  assert.match(read("src/app/events/[id]/layout.tsx"), /<EventModal standalone>/);

  // Opened from a list card: the card's event renders the real view at once.
  assert.match(card, /stashEventForDetail\(event\)/);
  assert.match(loading, /peekEventForDetail/);
  assert.match(loading, /<EventDetailView event=\{handedOff\} variant="modal" \/>/);
  assert.match(page, /<EventDetailView event=\{event\} variant="modal" \/>/);

  // Opened cold: the skeleton borrows the view's layout classes, not copies.
  for (const layout of [
    "EVENT_MODAL_CONTAINER_CLASS",
    "EVENT_MODAL_FLYER_GRID_CLASS",
    "EVENT_MODAL_ASIDE_CLASS",
  ]) {
    assert.match(view, new RegExp(`export const ${layout}`));
    assert.match(loading, new RegExp(`className=\\{${layout}\\}`));
  }
});

test("event cards use the same overlay on soft navigation and direct loads", () => {
  const layout = read("src/app/layout.tsx");
  const slotDefault = read("src/app/@modal/default.tsx");
  const modalLayout = read("src/app/@modal/(.)events/[id]/layout.tsx");
  const modalPage = read("src/app/@modal/(.)events/[id]/page.tsx");
  const modalLoading = read("src/app/@modal/(.)events/[id]/loading.tsx");
  const loading = read("src/components/events/EventDetailLoading.tsx");
  const shell = read("src/components/events/EventModal.tsx");
  const card = read("src/components/events/EventCard.tsx");
  const tile = read("src/components/home/FlyerTile.tsx");
  const page = read("src/app/events/[id]/page.tsx");

  // Root layout renders the slot; it is empty unless a card intercepted.
  assert.match(layout, /modal: React\.ReactNode/);
  assert.match(layout, /\{modal\}/);
  assert.match(slotDefault, /return null/);
  assert.equal(existsSync(sourceFile("src/app/@modal/(.)events/[id]/error.tsx")), true);

  // Overlay reuses the page body; shell lives in the layout so loading hands
  // off to page without remounting.
  assert.match(modalLayout, /<EventModal>/);
  assert.match(modalPage, /<EventDetailView event=\{event\} variant="modal" \/>/);
  assert.match(modalPage, /force-dynamic/);
  assert.match(modalLoading, /EventModalDetailLoading/);
  assert.match(loading, /<EventDetailView event=\{handedOff\} variant="modal" \/>/);

  // Every close path is history-back; dialog semantics and marker cleanup.
  assert.match(shell, /router\.back\(\)/);
  assert.match(shell, /role="dialog"/);
  assert.match(shell, /aria-modal="true"/);
  assert.match(shell, /useDialogFocusTrap/);
  assert.match(shell, /clearEventFeedReturnState/);

  // Cards stay real links (crawlable) and do not scroll the list.
  for (const source of [card, tile]) {
    assert.match(source, /href=\{href\}/);
    assert.match(source, /scroll=\{false\}/);
    assert.match(source, /stashEventForDetail\(event\)/);
  }

  // Direct loads keep the SEO metadata and structured data inside the card route.
  assert.match(page, /generateMetadata/);
  assert.match(page, /application\/ld\+json/);
  assert.doesNotMatch(modalPage, /generateMetadata/);
});

test("/events and direct event loads paint whole, with no streamed skeleton", () => {
  // A route loading state is a Suspense fallback, and on a document load the
  // server streams it first, so every refresh flashed skeletons over data the
  // page was about to have. Direct loads wait for the data and paint once.
  assert.equal(existsSync(sourceFile("src/app/events/loading.tsx")), false);
  assert.equal(existsSync(sourceFile("src/app/events/[id]/loading.tsx")), false);
  const detailLayout = read("src/app/events/[id]/layout.tsx");
  assert.match(detailLayout, /<EventsPage searchParams=/);
  assert.doesNotMatch(detailLayout, /Suspense/);

  // In-app opens still get an instant overlay (see the @modal loading route).
  assert.equal(existsSync(sourceFile("src/app/@modal/(.)events/[id]/loading.tsx")), true);
});

test("in-app links to /events open it the way Luma does: prefetched, else its skeleton at once", () => {
  const link = read("src/components/events/EventsFeedLink.tsx");
  const overlay = read("src/components/events/EventsNavSkeleton.tsx");
  const css = read("src/app/globals.css");
  const skeleton = read("src/components/events/EventsBrowserSkeleton.tsx");
  const browser = read("src/components/events/EventsBrowser.tsx");

  // The bare feed is prefetched in full from anywhere but the feed itself, so
  // a click usually lands at once without a skeleton.
  assert.match(link, /prefetch=\{!onFeed && href === "\/events" \? true : undefined\}/);

  // Otherwise the link's pending status holds the feed's skeleton up, and it
  // lifts in the same commit as the page (a layout effect, not a timer).
  assert.match(link, /useLinkStatus\(\)/);
  assert.match(link, /useLayoutEffect\(\(\) => \{\s*if \(pending\) return holdEventsNavSkeleton\(\);/);
  assert.match(read("src/app/layout.tsx"), /<EventsNavSkeleton \/>/);
  assert.match(overlay, /useEventsNavPending\(\)/);
  assert.match(overlay, /<Masthead position="static" variant="solid" activePath="\/events" \/>/);
  assert.match(overlay, /<EventsBrowserSkeleton \/>/);

  // A beat before it shows, so a near-instant navigation never flashes it.
  assert.match(css, /\.nav-skeleton \{[^}]*animation: nav-skeleton-in [^;]* 100ms both/);

  // Every in-app way onto the feed uses it.
  assert.match(read("src/components/layout/Masthead.tsx"), /link\.href === "\/events" \? EventsFeedLink : Link/);
  assert.match(read("src/components/layout/Footer.tsx"), /l\.href === "\/events" \? EventsFeedLink : Link/);
  assert.equal((read("src/app/page.tsx").match(/<EventsFeedLink/g) ?? []).length, 2);
  assert.match(read("src/app/not-found.tsx"), /<EventsFeedLink\s+href="\/events"/);

  // Same shell as the real page, so when it lands only the rows change.
  assert.match(skeleton, /EventsLeftRail/);
  assert.match(skeleton, /EventsRightRail/);
  assert.match(skeleton, /countsPending/);
  const grid = /lg:grid-cols-\[208px_minmax\(0,1fr\)_312px\]/;
  assert.match(skeleton, grid);
  assert.match(browser, grid);
});

test("flyers take their shape from the image, not from script", () => {
  const css = read("src/app/globals.css");
  const poster = read("src/components/events/FlyerPoster.tsx");
  const card = read("src/components/events/EventCard.tsx");

  // The frame shrink-wraps its image, which holds a 4:5 placeholder until it
  // loads and then takes its own shape; server HTML paints at its final shape.
  assert.match(css, /\.flyer-fit \{[^}]*width: fit-content/);
  assert.match(css, /\.flyer-fit > img \{[^}]*aspect-ratio: auto var\(--flyer-ratio\)/);
  assert.match(css, /\.flyer-fit > img \{[^}]*min-width: min\(var\(--flyer-max-w\), var\(--flyer-max-h\) \* var\(--flyer-ratio\)\)/);
  assert.match(css, /\.flyer-fit > img \{[^}]*position: relative/);
  assert.match(poster, /flyer-fit relative block/);
  assert.doesNotMatch(poster, /absolute inset-0/);

  // Reel covers narrow once their ratio is known; the image stays where the
  // slot pins the frame, so that never moves it.
  assert.match(css, /object-position: var\(--flyer-anchor, center\)/);
  assert.match(card, /\[--flyer-anchor:right_top\]/);
});

test("loading placeholders shimmer and flyers fade in over them", () => {
  const css = read("src/app/globals.css");
  const poster = read("src/components/events/FlyerPoster.tsx");
  const image = read("src/components/events/EventFlyerImage.tsx");
  const tile = read("src/components/home/FlyerTile.tsx");

  // One shared shimmer, transform-only, under any image painting into the slot.
  assert.match(css, /@keyframes skeleton-shimmer/);
  assert.match(css, /\.skeleton::before \{[^}]*animation: skeleton-shimmer/);
  assert.match(css, /\.skeleton::before \{[^}]*transform: translateX/);

  // Every skeleton bar and stubbed flyer slot carries it.
  for (const path of [
    "src/components/events/EventsBrowserSkeleton.tsx",
    "src/components/events/EventDetailLoading.tsx",
    "src/components/ui/RouteLoadingPage.tsx",
    "src/components/events/EventCategoryFilter.tsx",
  ]) {
    assert.match(read(path), /\bskeleton\b[^"`]*rounded-full bg-ink\/10/);
  }

  // Flyer slots shimmer until the image loads or fails, never forever.
  assert.match(poster, /pending \? "skeleton" : ""/);
  assert.match(poster, /setFailedSrc\(src\)/);
  assert.match(tile, /showImage && !loaded \? "skeleton" : ""/);

  // Only browser-mounted flyers wait to fade in; server HTML paints at once.
  assert.match(image, /useSyncExternalStore\(\s*subscribe,\s*\(\) => true,\s*\(\) => false\s*\)/);
  assert.match(image, /opacity-0/);
});

test("app routes expose 500-level error boundaries", () => {
  const sharedError = read("src/components/ui/RouteErrorPage.tsx");
  const routeErrors = [
    "src/app/error.tsx",
    "src/app/events/error.tsx",
    "src/app/events/[id]/error.tsx",
    "src/app/about/error.tsx",
  ];

  assert.match(sharedError, /"use client"/);
  assert.match(sharedError, /aria-live="polite"/);
  assert.match(sharedError, /console\.error/);
  assert.match(sharedError, /reset/);
  assert.match(sharedError, /Try again/);

  for (const route of routeErrors) {
    assert.equal(existsSync(sourceFile(route)), true, `${route} is missing`);
    const source = read(route);
    assert.match(source, /"use client"/);
    assert.match(source, /RouteErrorPage|EventDetailError/);
  }
});

test("event cards link to a detail page and stay accessible", () => {
  const source = read("src/components/events/EventCard.tsx");

  assert.match(source, /const href = `\/events\/\$\{event\.id\}`/);
  assert.match(source, /href=\{href\}/);
  assert.match(source, /saveEventFeedReturn/);
  assert.match(source, /data-event-id=\{event\.id\}/);
  assert.match(source, /aria-label=/);
  assert.match(source, /alt=\{eventFlyerAlt\(event\)\}/);
  assert.match(source, /interactive-focus card-hover/);
  assert.doesNotMatch(source, /group-hover:underline/);
  assert.doesNotMatch(source, /alt=""/);
});

test("event back navigation restores from a snapshot before falling back to pagination", () => {
  const browser = read("src/components/events/EventsBrowser.tsx");
  const restore = read("src/lib/events/feed-restore.ts");
  const session = read("src/lib/events/feed-session.ts");
  const restoreHook = read("src/components/events/useEventFeedRestore.ts");

  assert.match(session, /saveEventFeedSnapshot/);
  assert.match(session, /requireReturnScroll/);
  assert.match(session, /readEventFeedRestoreState/);
  assert.match(restoreHook, /readEventFeedRestoreState/);
  assert.match(session, /getSavedScrollPosition/);
  assert.match(session, /getSavedReturnPath/);
  assert.match(session, /sessionStorage/);
  assert.match(restoreHook, /useLayoutEffect/);
  assert.match(browser, /saveEventFeedSnapshot/);
  assert.match(restore, /restoreSavedEventFeedSpot/);
  assert.match(restore, /restoreEventsUntilTarget/);
  assert.match(restore, /deriveRestoreIntent/);
  assert.match(restore, /mergeUniqueEventsByStart/);
  assert.match(restore, /root\.style\.scrollBehavior = "auto"/);
  assert.match(restore, /const limitToFetch = Math\.max\(0, target\.loadedCount - current\.length\);/);
  assert.match(
    restore,
    /rootScroller\.scrollTop = intent\.scrollY;/
  );
  assert.match(restore, /fetchEventsPage/);
  assert.match(restore, /fetchPage\(next, limitToFetch, filters\)/);
  assert.match(restore, /fetchPage\(restoredNext, undefined, filters\)/);
  assert.match(restore, /restoreToEventCard/);
  assert.match(session, /highlanderhub\.returnScroll/);
});

test("home flyer mosaic tiles expose flyer alt text and keyboard focus", () => {
  const source = read("src/components/home/FlyerTile.tsx");

  assert.match(source, /alt=\{eventFlyerAlt\(event\)\}/);
  assert.match(source, /interactive-focus card-hover/);
  assert.doesNotMatch(source, /alt=""/);
});

test("home flyer marquee animates with wrapped transforms", () => {
  const source = read("src/components/home/FlyerMarquee.tsx");

  assert.match(source, /useMotionValue/);
  assert.match(source, /useAnimationFrame/);
  assert.match(source, /ResizeObserver/);
  assert.match(source, /wrapX\(x\.get\(\)/);
  assert.match(source, /drag="x"/);
  assert.match(source, /decorative/);
  assert.doesNotMatch(source, /scrollLeft/);
});

test("event detail page exposes RSVP / calendar / share actions", () => {
  // The page body lives in EventDetailView, shared with the loading state.
  const page = read("src/components/events/EventDetailView.tsx");
  const calendarMenu = read("src/components/events/EventCalendarMenu.tsx");

  assert.match(page, /EventCalendarMenu/);
  assert.match(page, /surface="desktop"/);
  assert.match(page, /surface="mobile"/);
  assert.match(calendarMenu, /Add to calendar|choose calendar app/);
  assert.match(calendarMenu, /FaApple/);
  assert.match(calendarMenu, /FcGoogle/);
  assert.match(calendarMenu, /Apple Calendar/);
  assert.match(calendarMenu, /Google Calendar/);
  assert.match(calendarMenu, /method="google"/);
  assert.match(calendarMenu, /method="ics"/);
  assert.doesNotMatch(calendarMenu, /Download \.ics/);
  assert.match(page, /Share|aria-label="Share"/);
  assert.match(page, /RSVP|View source/);
});

test("masthead keeps navigation reachable on mobile", () => {
  const source = read("src/components/layout/Masthead.tsx");
  const siteNav = read("src/lib/site-nav.ts");
  const eventsPage = read("src/app/events/page.tsx");
  const eventsBrowser = read("src/components/events/EventsBrowser.tsx");
  const feedColumn = read("src/components/events/EventsFeedColumn.tsx");
  const homePage = read("src/app/page.tsx");

  assert.match(source, /aria-label="Site"/);
  assert.doesNotMatch(source, /Mobile navigation/);
  assert.match(source, /SITE_NAV_LINKS\.map/);
  assert.match(source, /aria-current=\{active \? "page" : undefined\}/);
  assert.match(source, /@\/lib\/site-nav/);
  assert.match(siteNav, /SITE_NAV_LINKS/);
  assert.match(siteNav, /isNavLinkActive/);
  // No menu button: the links sit inline at every width, and the wordmark
  // is the way home.
  assert.doesNotMatch(source, /Toggle navigation menu/);
  assert.match(source, /<Link href="\/"/);
  assert.doesNotMatch(siteNav, /href: "\/",/);
  assert.match(siteNav, /href: "\/events"/);
  assert.doesNotMatch(siteNav, /saved/i);
  assert.match(siteNav, /href: "\/about"/);
  assert.doesNotMatch(siteNav, /href: "\/submit"/);
  assert.match(source, /hideOnScroll/);
  assert.match(source, /position = "sticky"/);
  assert.match(source, /position === "sticky"/);
  assert.match(source, /variant = "glass"/);
  assert.match(eventsPage, /<Masthead position="static" variant="solid" \/>/);
  assert.doesNotMatch(eventsPage, /hideOnScroll/);
  assert.match(feedColumn, /liquid-glass/);
  assert.match(feedColumn, /sticky top-0/);
  assert.match(feedColumn, /backdrop-blur-xl/);
  assert.match(homePage, /<Masthead \/>/);
});

test("event filters share category and day-window controls across layouts", () => {
  const leftRail = read("src/components/events/EventsLeftRail.tsx");
  const rightRail = read("src/components/events/EventsRightRail.tsx");
  const sheet = read("src/components/events/EventsMobileFilterSheet.tsx");
  const categoryFilter = read("src/components/events/EventCategoryFilter.tsx");
  const dayWindowFilter = read("src/components/events/EventDayWindowFilter.tsx");

  assert.match(leftRail, /<EventCategoryFilter/);
  assert.match(leftRail, /layout="rail"/);
  assert.match(sheet, /<EventCategoryFilter/);
  assert.match(sheet, /layout="grid"/);
  assert.match(rightRail, /<EventDayWindowFilter/);
  assert.match(rightRail, /layout="rail"/);
  assert.match(sheet, /<EventDayWindowFilter/);
  assert.match(sheet, /layout="sheet"/);
  assert.match(categoryFilter, /CATEGORIES\.map/);
  assert.match(dayWindowFilter, /DAY_WINDOWS\.map/);
});

test("event empty state copy stays outside the presentation column", () => {
  const feedColumn = read("src/components/events/EventsFeedColumn.tsx");
  const filters = read("src/components/events/useEventFeedFilters.ts");
  const emptyCopy = read("src/lib/events/empty-feed-copy.ts");
  const browser = read("src/components/events/EventsBrowser.tsx");

  assert.match(filters, /activeFilters = useMemo<EventFeedActiveFilters>/);
  assert.match(filters, /getEmptyFeedCopy\(activeFilters\)/);
  assert.match(filters, /emptyCopy/);
  assert.match(filters, /const hasActiveFilters = activeFilters\.hasAny/);
  assert.match(browser, /activeFilters=\{activeFilters\}/);
  assert.match(browser, /emptyCopy=\{emptyCopy\}/);
  assert.match(browser, /hasActiveFilters=\{hasActiveFilters\}/);
  assert.match(feedColumn, /emptyCopy: EmptyFeedCopy/);
  assert.match(feedColumn, /emptyCopy\.headline/);
  assert.match(feedColumn, /emptyCopy\.nudge/);
  assert.match(emptyCopy, /EMPTY_COPY_BY_MASK/);
  assert.match(emptyCopy, /const mask =/);
  assert.match(emptyCopy, /export function getEmptyFeedCopy/);
  assert.doesNotMatch(feedColumn, /diagnoseEmpty/);
  assert.doesNotMatch(feedColumn, /EMPTY_COPY_BY_MASK/);
  assert.doesNotMatch(feedColumn, /categoryLabelFor/);
  assert.doesNotMatch(feedColumn, /windowPhraseFor/);
  assert.doesNotMatch(feedColumn, /const mask =/);
  assert.doesNotMatch(feedColumn, /activeFilters\.hasAny/);
  assert.doesNotMatch(feedColumn, /hasQ &&/);
  assert.doesNotMatch(feedColumn, /hasC &&/);
  assert.doesNotMatch(feedColumn, /hasW\)/);
  assert.doesNotMatch(feedColumn, /query\.trim\(\)/);
  assert.doesNotMatch(feedColumn, /category !== "all"/);
  assert.doesNotMatch(feedColumn, /dayWindow !== "all"/);
});

test("motion and focus behavior have accessible fallbacks", () => {
  const source = read("src/app/globals.css");

  assert.match(source, /prefers-reduced-motion: reduce/);
  assert.match(source, /\.interactive-focus/);
  assert.match(source, /outline: 3px solid rgb\(var\(--color-ink\)\)/);
  assert.match(source, /\.card-hover:focus-visible/);
  assert.match(source, /touch-action: manipulation/);
});

test("dark mode follows the device setting through the shared palette", () => {
  const globals = read("src/app/globals.css");
  const tailwind = read("tailwind.config.ts");
  const layout = read("src/app/layout.tsx");

  // One palette, re-pointed under the media query: no class-based toggle.
  assert.match(globals, /@media \(prefers-color-scheme: dark\)/);
  assert.match(globals, /--color-ink: 236 238 241/);
  assert.match(tailwind, /darkMode: "media"/);
  // Dark-mode hairlines soften by an opacity curve; solid ink edges stay solid.
  assert.match(tailwind, /pow\(<alpha-value>, var\(--edge-alpha-curve\)\)/);
  assert.match(tailwind, /borderColor: \{ ink: edgeInk \}/);
  assert.match(globals, /--edge-alpha-curve: 1\.3/);
  // Cards answer hover with their edge; they do not move.
  assert.doesNotMatch(globals, /\.card-hover[^}]*translate/);
  assert.match(tailwind, /rgb\(var\(--color-\$\{name\}\) \/ <alpha-value>\)/);
  assert.match(layout, /colorScheme: "light dark"/);

  // `ink` turns light in dark mode, so nothing may assume it stays dark:
  // text on an ink fill is `text-canvas`, overlays on flyers and modal
  // backdrops use the always-dark `scrim`, and surfaces use canvas, not white.
  for (const file of walk("src")) {
    if (!/\.(tsx?|css)$/.test(file)) continue;
    const source = read(file);
    assert.doesNotMatch(source, /bg-ink\b[^"`]*\btext-white\b/, file);
    assert.doesNotMatch(source, /(from|via)-ink\/\d/, file);
    assert.doesNotMatch(source, /bg-white\//, file);
  }
});

test("badge colors avoid low-contrast accent text", () => {
  const source = read("src/lib/category-colors.ts");

  assert.doesNotMatch(source, /text-leaf/);
  assert.doesNotMatch(source, /text-coral/);
  assert.doesNotMatch(source, /text-sky/);
});

test("site exposes crawler and social preview metadata", () => {
  const layout = read("src/app/layout.tsx");
  const eventDetail = read("src/app/events/[id]/page.tsx");
  const seo = read("src/lib/seo.ts");
  const sitemap = read("src/app/sitemap.ts");
  const robots = read("src/app/robots.ts");
  const manifest = read("public/manifest.json");

  assert.match(layout, /metadataBase:/);
  assert.match(layout, /openGraph:/);
  assert.match(layout, /twitter:/);
  assert.match(layout, /manifest:/);
  assert.match(layout, /\/favicon\.ico/);
  assert.match(layout, /apple: "\/apple-touch-icon\.png"/);
  for (const icon of ["favicon.ico", "icon-192.png", "icon-512.png", "apple-touch-icon.png"]) {
    assert.equal(existsSync(sourceFile(`public/${icon}`)), true, icon);
  }
  assert.match(seo, /\/og-card\.jpg/);
  assert.match(layout, /images: \[SITE_SOCIAL_CARD\]/);
  assert.match(layout, /card: "summary_large_image"/);
  assert.equal(existsSync(sourceFile("public/og-card.jpg")), true);
  // The root title template appends the site name; routes must not repeat it.
  assert.match(layout, /template: `%s · \$\{SITE_NAME\}`/);
  for (const route of [
    "src/app/about/page.tsx",
    "src/app/events/page.tsx",
    "src/app/events/[id]/page.tsx",
    "src/app/privacy/page.tsx",
    "src/app/terms/page.tsx",
  ]) {
    assert.doesNotMatch(read(route), /title: "[^"]*· Highlander Hub"/, route);
  }

  assert.match(eventDetail, /openGraph:/);
  assert.match(eventDetail, /twitter:/);
  assert.match(eventDetail, /event\.imageUrl/);
  assert.match(eventDetail, /\/events\/\$\{event\.id\}/);
  assert.match(eventDetail, /type="application\/ld\+json"/);
  assert.match(eventDetail, /"@context": "https:\/\/schema\.org"/);
  assert.match(eventDetail, /"@type": "Event"/);
  assert.match(eventDetail, /EventScheduled/);
  assert.match(eventDetail, /OfflineEventAttendanceMode/);
  assert.match(eventDetail, /PostalAddress/);
  assert.match(eventDetail, /isPublicContentKind/);

  assert.match(sitemap, /MetadataRoute\.Sitemap/);
  assert.match(sitemap, /getSitemapEvents/);
  assert.match(sitemap, /absoluteUrl\(`\/events\/\$\{event\.id\}`\)/);
  assert.match(sitemap, /\/events/);
  assert.match(sitemap, /\/about/);
  assert.doesNotMatch(sitemap, /\/submit/);

  assert.match(robots, /MetadataRoute\.Robots/);
  assert.match(robots, /sitemap:/);

  assert.match(manifest, /Highlander Hub/);
  assert.match(manifest, /\/icon-192\.png/);
  assert.match(manifest, /\/icon-512\.png/);
  assert.match(manifest, /"start_url": "\/"/);
});

test("README documents the current Instagram ingestion path", () => {
  const readme = read("README.md");

  assert.match(readme, /Highlander Hub/);
  assert.match(readme, /Club Instagram posts/);
  assert.doesNotMatch(readme, /\/submit/);
  assert.doesNotMatch(readme, /on the roadmap/);
});

test("global error page keeps Highlander Hub fallback styling", () => {
  const source = read("src/app/global-error.tsx");

  assert.match(source, /Highlander Hub/);
  assert.match(source, /Campus events hit a snag/);
  assert.match(source, /--font-display/);
  assert.match(source, /#0f1115/);
  assert.match(source, /#ffffff/);
  assert.match(source, /aria-live="polite"/);
  assert.match(source, /Try again/);
  assert.doesNotMatch(source, /Fatal error/);
});
