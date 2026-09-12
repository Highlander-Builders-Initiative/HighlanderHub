"use client";

import { useEffect, type RefObject } from "react";

const FOCUSABLE_SELECTOR = [
  "button:not([disabled])",
  "[href]",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "summary",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

type UseDialogFocusTrapArgs = {
  active: boolean;
  panelRef: RefObject<HTMLElement | null>;
  onClose: () => void;
  /** Receives focus on open. Defaults to the first tabbable in the panel. */
  initialFocusRef?: RefObject<HTMLElement | null>;
};

/**
 * Modal plumbing shared by overlay surfaces: locks page scroll, moves focus
 * into the panel, keeps Tab inside it, closes on Escape, and hands focus back
 * to whatever opened it.
 */
export function useDialogFocusTrap({
  active,
  panelRef,
  onClose,
  initialFocusRef,
}: UseDialogFocusTrapArgs) {
  useEffect(() => {
    if (!active) return;

    const opener = document.activeElement as HTMLElement | null;
    const { body, documentElement } = document;
    const previousOverflow = body.style.overflow;
    const previousPaddingRight = body.style.paddingRight;
    // Hiding the scrollbar widens the viewport; pad by its width so the page
    // underneath does not jump sideways on platforms with classic scrollbars.
    const scrollbarWidth = window.innerWidth - documentElement.clientWidth;
    body.style.overflow = "hidden";
    if (scrollbarWidth > 0) body.style.paddingRight = `${scrollbarWidth}px`;

    // Elements hidden at this breakpoint (display: none) have no client rects
    // and cannot take focus, so they must not anchor the wrap-around.
    const tabbables = () =>
      Array.from(
        panelRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR) ?? []
      ).filter(
        (el) =>
          !el.hasAttribute("disabled") &&
          el.tabIndex !== -1 &&
          el.getClientRects().length > 0
      );

    (initialFocusRef?.current ?? tabbables()[0] ?? panelRef.current)?.focus({ preventScroll: true });

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }

      if (e.key !== "Tab") return;

      const items = tabbables();
      if (items.length === 0) {
        e.preventDefault();
        panelRef.current?.focus();
        return;
      }

      const first = items[0];
      const last = items[items.length - 1];
      const current = document.activeElement as HTMLElement | null;
      const inside = !!current && !!panelRef.current?.contains(current);

      if (e.shiftKey) {
        if (!inside || current === first || current === panelRef.current) {
          e.preventDefault();
          last.focus();
        }
      } else if (!inside || current === last) {
        e.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", onKey);

    return () => {
      body.style.overflow = previousOverflow;
      body.style.paddingRight = previousPaddingRight;
      window.removeEventListener("keydown", onKey);
      opener?.focus?.({ preventScroll: true });
    };
  }, [active, panelRef, onClose, initialFocusRef]);
}
