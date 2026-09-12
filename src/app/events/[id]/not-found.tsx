import { EVENT_MODAL_CONTAINER_CLASS, EVENT_MODAL_TITLE_ID } from "@/components/events/EventDetailView";

export default function NotFound() {
  return (
    <div className={EVENT_MODAL_CONTAINER_CLASS}>
      <h2 id={EVENT_MODAL_TITLE_ID} className="pr-12 font-display text-[24px] font-semibold tracking-[-0.02em] text-ink">
        This event is no longer listed.
      </h2>
      <p className="mt-3 text-[15px] text-ink/75">
        It may have been removed or rescheduled by the host.
      </p>
    </div>
  );
}
