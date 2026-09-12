import {
  EVENT_MODAL_CONTAINER_CLASS,
  EVENT_MODAL_TITLE_ID,
  EventDetailView,
} from "@/components/events/EventDetailView";
import { getEventById } from "@/lib/events";

// Same per-request rendering as the canonical route (see events/[id]/page.tsx).
export const dynamic = "force-dynamic";

/**
 * /events/[id] as an overlay, for in-app navigation from a card. Metadata and
 * JSON-LD stay on the canonical route used by refreshes and shared links.
 */
export default async function EventModalPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const event = await getEventById(id);

  if (!event) {
    return (
      <div className={EVENT_MODAL_CONTAINER_CLASS}>
        <h2
          id={EVENT_MODAL_TITLE_ID}
          className="pr-12 font-display text-[24px] font-semibold tracking-[-0.02em] text-ink"
        >
          This event is no longer listed.
        </h2>
        <p className="mt-3 text-[15px] text-ink/75">
          It may have been removed or rescheduled by the host.
        </p>
      </div>
    );
  }

  return <EventDetailView event={event} variant="modal" />;
}
