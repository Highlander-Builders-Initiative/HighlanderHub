import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { test } from "node:test";

const sourceFile = (path) => new URL(`../${path}`, import.meta.url);
const read = (path) => readFileSync(sourceFile(path), "utf8");

test("event browser paginates the list instead of rendering every event at once", () => {
  const browser = read("src/components/events/EventsBrowser.tsx");
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
  assert.match(browser, /loadMoreRef/);
  assert.match(browser, /fetchEventsPage\(nextOffset\)/);
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
  assert.match(page, /getEventsSummary/);
  assert.match(page, /summary=\{summary\}/);
  assert.match(feedColumn, /summary\.total/);
  assert.match(feedColumn, /summary\.upcomingThisWeek/);
  assert.match(feedColumn, /summary\.freeFood/);
  assert.doesNotMatch(page, /events\.length/);
});

test("calendar loads its own month-range events outside feed pagination", () => {
  const page = read("src/app/events/page.tsx");
  const browser = read("src/components/events/EventsBrowser.tsx");
  const calendarHook = read("src/components/events/useCalendarMonthEvents.ts");
  const restoreHook = read("src/components/events/useEventFeedRestore.ts");
  const filters = read("src/components/events/useEventFeedFilters.ts");
  const calendar = read("src/components/events/EventsMiniCalendar.tsx");
  const data = read("src/lib/events/index.ts");
  const eventsApi = read("src/lib/events/api.ts");
  const calendarApi = read("src/app/api/events/calendar/route.ts");

  assert.match(data, /export async function getCalendarEvents/);
  assert.match(data, /\.gte\("starts_at", startIso\)/);
  assert.match(data, /\.lt\("starts_at", endIso\)/);
  assert.match(data, /parsePacificDateTimeInput\(`\$\{startDayKey\}T00:00`\)/);
  assert.doesNotMatch(data, /calendar events"[\s\S]*activeEventFilter/);
  assert.match(page, /getCalendarEvents/);
  assert.match(page, /calendarEvents=\{calendarEvents\}/);
  assert.match(calendarApi, /getCalendarEvents/);
  assert.match(calendarApi, /searchParams/);
  assert.match(eventsApi, /fetchCalendarEvents/);
  assert.match(browser, /useCalendarMonthEvents/);
  assert.match(browser, /isCalendarLoading/);
  assert.match(browser, /useEventFeedRestore/);
  assert.match(browser, /mergeUniqueEventsByStart\(current, eventsForDay\)/);
  assert.match(filters, /calendarEvents\?: CampusEvent\[\]/);
  assert.match(filters, /const calendarGrouped = useMemo/);
  assert.match(filters, /for \(const \[key, evs\] of calendarGrouped\)/);
  assert.match(calendar, /pacificCalendarGridRange/);
  assert.match(calendar, /role="status"/);
  assert.match(calendarHook, /fetchCalendarEvents\(calendarRange\.start, calendarRange\.end\)/);
  assert.match(calendarHook, /isCalendarLoading/);
  assert.match(calendarHook, /finally/);
  assert.match(calendarHook, /useEffect/);
  assert.match(restoreHook, /restoreSavedEventFeedSpot/);
  assert.match(restoreHook, /useLayoutEffect/);
  assert.doesNotMatch(browser, /fetchCalendarEvents\(calendarRange\.start, calendarRange\.end\)/);
  assert.doesNotMatch(browser, /restoreSavedEventFeedSpot/);
});

test("app routes expose loading UI while server data resolves", () => {
  const sharedLoading = read("src/components/ui/RouteLoadingPage.tsx");
  const routeLoaders = [
    "src/app/loading.tsx",
    "src/app/events/loading.tsx",
    "src/app/events/[id]/loading.tsx",
    "src/app/about/loading.tsx",
    "src/app/submit/loading.tsx",
  ];

  assert.match(sharedLoading, /aria-busy="true"/);
  assert.match(sharedLoading, /RouteLoadingPage/);

  for (const route of routeLoaders) {
    const source = read(route);
    assert.match(source, /RouteLoadingPage/);
  }
});

test("app routes expose 500-level error boundaries", () => {
  const sharedError = read("src/components/ui/RouteErrorPage.tsx");
  const routeErrors = [
    "src/app/error.tsx",
    "src/app/events/error.tsx",
    "src/app/events/[id]/error.tsx",
    "src/app/about/error.tsx",
    "src/app/submit/error.tsx",
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
    assert.match(source, /RouteErrorPage/);
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
  assert.match(restore, /restoreToEventCard/);
  assert.match(session, /highlanderhub\.returnScroll/);
});

test("home flyer mosaic tiles expose flyer alt text and keyboard focus", () => {
  const source = read("src/components/home/FlyerTile.tsx");

  assert.match(source, /alt=\{eventFlyerAlt\(event\)\}/);
  assert.match(source, /interactive-focus card-hover/);
  assert.doesNotMatch(source, /alt=""/);
});

test("event detail page exposes RSVP / calendar / share actions", () => {
  const source = read("src/app/events/[id]/page.tsx");

  assert.match(source, /Add to calendar|aria-label="Add to calendar"/);
  assert.match(source, /Share|aria-label="Share"/);
  assert.match(source, /RSVP|View source/);
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
  assert.match(source, /MASTHEAD_NAV_LINKS\.map/);
  assert.match(source, /@\/lib\/site-nav/);
  assert.match(siteNav, /SITE_NAV_LINKS/);
  assert.match(siteNav, /href: "\/"/);
  assert.match(siteNav, /href: "\/events"/);
  assert.match(siteNav, /href: "\/about"/);
  assert.match(siteNav, /href: "\/submit"/);
  assert.match(source, /hideOnScroll/);
  assert.match(source, /position = "sticky"/);
  assert.match(source, /position === "sticky"/);
  assert.match(source, /variant = "glass"/);
  assert.match(eventsPage, /<Masthead position="static" variant="solid" hideNavOnDesktop \/>/);
  assert.doesNotMatch(eventsPage, /hideOnScroll/);
  assert.match(feedColumn, /bg-white\/55/);
  assert.match(feedColumn, /style=\{\{ top: 0 \}\}/);
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

test("motion and focus behavior have accessible fallbacks", () => {
  const source = read("src/app/globals.css");

  assert.match(source, /prefers-reduced-motion: reduce/);
  assert.match(source, /\.interactive-focus/);
  assert.match(source, /outline: 3px solid #0f1115/);
  assert.match(source, /\.card-hover:focus-visible/);
  assert.match(source, /touch-action: manipulation/);
});

test("badge colors avoid low-contrast accent text", () => {
  const source = read("src/components/ui/CategoryBadge.tsx");

  assert.doesNotMatch(source, /text-leaf/);
  assert.doesNotMatch(source, /text-coral/);
  assert.doesNotMatch(source, /text-sky/);
});

test("submit form exposes client-side validation feedback accessibly", () => {
  const source = read("src/components/forms/submit/fields.tsx");
  const form = read("src/components/forms/submit/SubmitForm.tsx");
  const validation = read("src/components/forms/submit/submit-validation.ts");

  assert.match(form, /validateSubmissionFields/);
  assert.match(form, /fieldErrors\.starts_at/);
  assert.match(source, /aria-invalid=\{Boolean\(error\)\}/);
  assert.match(source, /aria-describedby=\{describedBy \|\| undefined\}/);
  assert.match(validation, /This field is required\./);
  assert.match(form, /bg-ink/);
  assert.match(form, /text-canvas/);
  assert.doesNotMatch(source, /placeholder:text-stone-400/);
});

test("submit form tracks page-view to completion funnel events", () => {
  const form = read("src/components/forms/submit/SubmitForm.tsx");
  const analytics = read("src/lib/analytics.ts");

  assert.match(analytics, /submit_page_view: Record<string, never>/);
  assert.match(form, /useEffect/);
  assert.match(form, /track\("submit_page_view", \{\}\)/);
  assert.match(form, /track\("submission_complete", \{\}\)/);
});

test("submit form validation and upload helpers live in focused modules", () => {
  const validation = read("src/components/forms/submit/submit-validation.ts");
  const datetime = read("src/lib/submit-datetime.ts");
  const flyer = read("src/lib/submission-flyer.ts");
  const upload = read("src/components/forms/submit/use-flyer-upload.ts");
  const picker = read("src/components/forms/submit/FlyerUpload.tsx");
  const deleteRoute = read("src/app/api/submission-flyers/delete/route.ts");

  assert.match(validation, /validateSubmissionFields/);
  assert.match(validation, /buildSubmissionRow/);
  assert.match(datetime, /computeSubmitEndsAtLocal/);
  assert.match(datetime, /submitUpcomingFridayDateInput/);
  assert.match(datetime, /pacificTodayKey/);
  assert.match(flyer, /uploadSubmissionFlyer/);
  assert.match(flyer, /submission-flyers/);
  assert.match(flyer, /cleanupToken/);
  assert.match(flyer, /deleteSubmissionFlyer/);
  assert.match(upload, /useFlyerUpload/);
  assert.match(upload, /uploadedRef/);
  assert.doesNotMatch(upload, /\[status\]/);
  assert.match(upload, /flyer_uploaded/);
  assert.match(upload, /flyer_delete_error/);
  assert.match(deleteRoute, /SUPABASE_SERVICE_ROLE_KEY/);
  assert.match(deleteRoute, /SUPABASE_SERVICE_KEY/);
  assert.match(deleteRoute, /bucket\.info\(body\.path\)/);
  assert.match(deleteRoute, /bucket\.remove\(\[body\.path\]\)/);
  assert.match(picker, /FlyerUploadedTile/);
  assert.match(picker, /or paste a URL/);
  assert.doesNotMatch(picker, /bg-stone-950/);
});

test("site exposes crawler and social preview metadata", () => {
  const layout = read("src/app/layout.tsx");
  const eventDetail = read("src/app/events/[id]/page.tsx");
  const submitPage = read("src/app/submit/page.tsx");
  const seo = read("src/lib/seo.ts");
  const sitemap = read("src/app/sitemap.ts");
  const robots = read("src/app/robots.ts");
  const manifest = read("public/manifest.json");

  assert.match(layout, /metadataBase:/);
  assert.match(layout, /openGraph:/);
  assert.match(layout, /twitter:/);
  assert.match(layout, /manifest:/);
  assert.match(layout, /SITE_PREVIEW_IMAGE/);
  assert.match(seo, /\/logo_icon\.png/);

  assert.match(eventDetail, /openGraph:/);
  assert.match(eventDetail, /twitter:/);
  assert.match(eventDetail, /event\.imageUrl/);
  assert.match(eventDetail, /\/events\/\$\{event\.id\}/);

  assert.match(submitPage, /title: "Submit an event · Highlander Hub"/);
  assert.match(submitPage, /description:/);

  assert.match(sitemap, /MetadataRoute\.Sitemap/);
  assert.match(sitemap, /\/events/);
  assert.match(sitemap, /\/about/);
  assert.match(sitemap, /\/submit/);

  assert.match(robots, /MetadataRoute\.Robots/);
  assert.match(robots, /sitemap:/);

  assert.match(manifest, /Highlander Hub/);
  assert.match(manifest, /\/logo_icon\.png/);
  assert.match(manifest, /"start_url": "\/"/);
});

test("README documents the current ingestion and submission paths", () => {
  const readme = read("README.md");

  assert.match(readme, /Highlander Hub/);
  assert.match(readme, /highlanderlink\.ucr\.edu/);
  assert.match(readme, /\/submit/);
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
