import { Masthead } from "@/components/layout/Masthead";
import { Footer } from "@/components/layout/Footer";
import { EVENTS_NAV_LINKS } from "@/lib/site-nav";
import { EventsBrowserSkeleton } from "@/components/events/EventsBrowserSkeleton";

/**
 * Mirrors /events' own shell exactly (same masthead, same three-column grid),
 * so the only thing that changes when the data lands is the feed rows.
 */
export default function Loading() {
  return (
    <main className="min-h-screen bg-surface">
      <Masthead position="static" variant="solid" navLinks={EVENTS_NAV_LINKS} />
      <EventsBrowserSkeleton />
      <Footer />
    </main>
  );
}
