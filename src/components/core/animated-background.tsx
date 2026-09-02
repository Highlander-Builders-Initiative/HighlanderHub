"use client";

import { cn } from "@/lib/utils";
import { AnimatePresence, motion, type Transition } from "motion/react";
import {
  Children,
  cloneElement,
  isValidElement,
  useEffect,
  useId,
  useState,
  type MouseEvent as ReactMouseEvent,
  type ReactElement,
  type ReactNode,
} from "react";

type AnimatedBackgroundChild = ReactElement<{
  "data-id": string;
  className?: string;
  children?: ReactNode;
}>;

export type AnimatedBackgroundProps = {
  children: AnimatedBackgroundChild[] | AnimatedBackgroundChild;
  defaultValue?: string;
  onValueChange?: (newActiveId: string | null) => void;
  /**
   * Highlight classes. Pass a function to tint the highlight per active item
   * (e.g. a per-category color); it receives the currently-active `data-id`.
   */
  className?: string | ((activeId: string | null) => string);
  transition?: Transition;
  enableHover?: boolean;
};

/**
 * Slides a single shared background between its children. With `enableHover`
 * the highlight follows the pointer (and clears on leave); otherwise it tracks
 * the clicked/selected child. From motion-primitives; imports adapted to this
 * repo's `cn`.
 */
export function AnimatedBackground({
  children,
  defaultValue,
  onValueChange,
  className,
  transition,
  enableHover = false,
}: AnimatedBackgroundProps) {
  const [activeId, setActiveId] = useState<string | null>(
    defaultValue ?? null
  );
  const uniqueId = useId();

  const handleSetActiveId = (id: string | null) => {
    setActiveId(id);
    onValueChange?.(id);
  };

  useEffect(() => {
    if (defaultValue !== undefined) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- defaultValue is a parent-controlled reset
      setActiveId(defaultValue);
    }
  }, [defaultValue]);

  return Children.map(children, (child, index) => {
    if (!isValidElement(child)) return child;

    const props = child.props as {
      "data-id": string;
      className?: string;
      children?: ReactNode;
    };
    const dataId = props["data-id"];
    // Hover mode follows the pointer for a preview, then rests back on the
    // selected item (`defaultValue`) on leave, rather than clearing entirely.
    // It does not fire `onValueChange` (hover never changes the selection);
    // children own their click handlers. Click mode tracks the clicked item.
    const interactionProps = enableHover
      ? {
          onMouseEnter: () => setActiveId(dataId),
          onMouseLeave: (event: ReactMouseEvent<HTMLElement>) => {
            // Only fall back to the selected item when the pointer leaves the
            // whole group. Moving between sibling items (or across the gaps
            // between them) keeps the highlight tracking, so it never darts
            // back to the selected item mid-traverse.
            const group = event.currentTarget.parentElement;
            const next = event.relatedTarget as Node | null;
            if (group && next && group.contains(next)) return;
            setActiveId(defaultValue ?? null);
          },
        }
      : {
          onClick: () => handleSetActiveId(dataId),
        };

    return cloneElement(
      child as ReactElement<Record<string, unknown>>,
      {
        key: index,
        className: cn("relative inline-flex", props.className),
        "data-checked": activeId === dataId ? "true" : "false",
        ...interactionProps,
      },
      <>
        <AnimatePresence initial={false}>
          {activeId === dataId && (
            <motion.div
              layoutId={`background-${uniqueId}`}
              className={cn(
                "absolute inset-0",
                typeof className === "function" ? className(activeId) : className
              )}
              transition={transition}
              initial={{ opacity: defaultValue ? 1 : 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            />
          )}
        </AnimatePresence>
        <span className="relative z-10 flex w-full items-center justify-center">
          {props.children}
        </span>
      </>
    );
  });
}
