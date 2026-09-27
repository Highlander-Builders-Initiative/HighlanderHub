import type { Metadata } from "next";
import { cookies } from "next/headers";
import { Masthead } from "@/components/layout/Masthead";
import { EventsBrowser } from "@/components/events/EventsBrowser";
import {
  FEED_VIEW_COOKIE,
  coerceCategoryParam,
  coerceDayWindowParam,
  coerceFeedView,
} from "@/components/events/events-filters";
import { Footer } from "@/components/layout/Footer";
import { getEventsPage } from "@/lib/events";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Events",
  description:
    "Browse and filter campus and club events at UC Riverside.",
};

type SearchParam = string | string[] | undefined;
function firstParam(raw: SearchParam): string | undefined {
  return Array.isArray(raw) ? raw[0] : raw;
}

type EventsPageProps = {
  searchParams: Promise<{ [key: string]: SearchParam }>;
};

export default async function EventsPage({ searchParams }: EventsPageProps) {
  const params = await searchParams;
  const initialView = coerceFeedView((await cookies()).get(FEED_VIEW_COOKIE)?.value);
  const initialFilters = {
    category: coerceCategoryParam(firstParam(params.cat)),
    query: firstParam(params.q) ?? "",
    dayWindow: coerceDayWindowParam(firstParam(params.when)),
  };
  // The calendar and filter counts come from the events layout, which a
  // filter change does not re-render.
  const initialPage = await getEventsPage(initialFilters);

  return (
    <main className="min-h-screen bg-surface">
      <Masthead position="static" variant="solid" />

      <EventsBrowser
        events={initialPage.events}
        initialHasMore={initialPage.hasMore}
        initialCursor={initialPage.cursor}
        initialFilters={initialFilters}
        initialView={initialView}
      />

      {/* Page-edge softener: a quiet fade at the very bottom of the
          viewport so the long-scroll feed never ends on a hard line.
          Page-edge structural treatment, not decorative chrome; scoped
          to /events where the long scroll warrants it. */}
      <div
        aria-hidden
        className="pointer-events-none fixed inset-x-0 bottom-0 z-10 h-10 bg-gradient-to-t from-surface via-surface/30 to-transparent sm:h-12"
        style={{
          backdropFilter: "blur(1.25px)",
          WebkitBackdropFilter: "blur(1.25px)",
          maskImage:
            "linear-gradient(to top, black 40%, transparent 100%)",
          WebkitMaskImage:
            "linear-gradient(to top, black 40%, transparent 100%)",
        }}
      />

      <Footer />
    </main>
  );
}
