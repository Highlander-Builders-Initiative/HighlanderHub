"use client";

import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, type ReactNode } from "react";
import { EVENT_MODAL_TITLE_ID } from "@/components/events/EventDetailView";
import { useDialogFocusTrap } from "@/components/ui/useDialogFocusTrap";
import {
  clearEventFeedReturnState,
  getSavedReturnPath,
  syncEventFeedReturnHistory,
} from "@/lib/events/feed-session";

const EVENT_DETAIL_PATH = /^\/events\/[^/]+\/?$/;

/**
 * Shared by intercepted navigation and hard loads of /events/[id]. In-app
 * cards close onto their existing history entry; fresh links close to /events.
 */
export function EventModal({ children, standalone = false }: {
  children: ReactNode;
  standalone?: boolean;
}) {
  const pathname = usePathname();
  // A parallel slot keeps its last page through soft navigations it does not
  // match, so the overlay hides itself once the URL leaves the event.
  if (!pathname || !EVENT_DETAIL_PATH.test(pathname)) return null;
  return <EventModalDialog standalone={standalone}>{children}</EventModalDialog>;
}

function EventModalDialog({ children, standalone }: { children: ReactNode; standalone: boolean }) {
  const router = useRouter();
  const panelRef = useRef<HTMLDivElement>(null);
  const closingRef = useRef(false);
  const close = useCallback(() => {
    if (closingRef.current) return;
    closingRef.current = true;
    const returnPath = getSavedReturnPath();
    if (!standalone || (returnPath && window.history.length > 1)) {
      router.back();
    } else {
      router.replace(returnPath ?? "/events", { scroll: false });
    }
  }, [router, standalone]);

  useDialogFocusTrap({
    active: true,
    panelRef,
    initialFocusRef: panelRef,
    onClose: close,
  });

  useEffect(() => {
    syncEventFeedReturnHistory();
    const openedAt = window.location.pathname;
    return () => {
      // The list under the overlay never unmounted, so once the URL is back on
      // it the return-scroll marker the card saved is spent; left behind, it
      // would yank a later fresh visit to that card. A cleanup on the same path
      // (StrictMode remount) keeps it.
      // Hard loads must keep the marker until the returning feed restores
      // its loaded pages and scroll position.
      if (!standalone && window.location.pathname !== openedAt) clearEventFeedReturnState();
    };
  }, [standalone]);

  return (
    <div className="fixed inset-0 z-[60] flex items-end justify-center md:items-center md:p-8">
      <button
        type="button"
        aria-label="Close event"
        tabIndex={-1}
        onClick={close}
        className="event-modal-backdrop absolute inset-0 cursor-default bg-ink/40"
      />

      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={EVENT_MODAL_TITLE_ID}
        aria-label="Event details"
        tabIndex={-1}
        className="event-modal-panel relative flex max-h-[92dvh] w-full flex-col overflow-hidden rounded-t-2xl bg-canvas shadow-[0_-8px_28px_rgba(15,17,21,0.08)] outline-none md:max-h-[calc(100dvh-4rem)] md:max-w-4xl md:rounded-2xl md:shadow-[0_24px_40px_rgba(15,17,21,0.08)]"
      >
        <button
          type="button"
          onClick={close}
          aria-label="Close event"
          className="interactive-focus absolute right-3 top-3 z-20 inline-flex h-10 w-10 items-center justify-center rounded-full border border-ink/10 bg-canvas text-muted transition-colors hover:border-ink/30 hover:text-ink sm:right-4 sm:top-4"
        >
          <svg
            aria-hidden
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="h-5 w-5"
          >
            <path d="M6 6l12 12M6 18 18 6" />
          </svg>
        </button>

        <div className="relative flex-1 overflow-y-auto overscroll-contain">
          {children}
        </div>
      </div>

      <style jsx>{`
        .event-modal-backdrop {
          animation: event-modal-fade 200ms ease-out both;
        }
        .event-modal-panel {
          animation: event-modal-sheet-up 280ms cubic-bezier(0.16, 1, 0.3, 1)
            both;
        }
        @media (min-width: 768px) {
          .event-modal-panel {
            animation: event-modal-rise 220ms cubic-bezier(0.16, 1, 0.3, 1)
              both;
          }
        }
        @keyframes event-modal-fade {
          from {
            opacity: 0;
          }
          to {
            opacity: 1;
          }
        }
        @keyframes event-modal-sheet-up {
          from {
            transform: translateY(100%);
            opacity: 0.5;
          }
          to {
            transform: translateY(0);
            opacity: 1;
          }
        }
        @keyframes event-modal-rise {
          from {
            transform: translateY(12px) scale(0.985);
            opacity: 0;
          }
          to {
            transform: translateY(0) scale(1);
            opacity: 1;
          }
        }
      `}</style>
    </div>
  );
}
