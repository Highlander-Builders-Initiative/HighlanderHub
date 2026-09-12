import { Masthead } from "@/components/layout/Masthead";
import { Footer } from "@/components/layout/Footer";
import { EventDetailLoading } from "@/components/events/EventDetailLoading";
import { EVENT_DETAIL_MAIN_CLASS } from "@/components/events/EventDetailView";

/**
 * Same shell as the detail page. Opened from a list card, the body is the real
 * page (handed off from the card); opened cold, a skeleton of the same layout.
 */
export default function Loading() {
  return (
    <main className={EVENT_DETAIL_MAIN_CLASS} aria-busy="true">
      <Masthead />
      <EventDetailLoading />
      <Footer />
    </main>
  );
}
