import { EventModal } from "@/components/events/EventModal";

/**
 * The overlay shell lives in a layout so it stays mounted while loading.tsx
 * hands off to page.tsx: one open animation, one focus move.
 */
export default function EventModalLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <EventModal>{children}</EventModal>;
}
