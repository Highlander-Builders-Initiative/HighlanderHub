'use client';

import {
  Accordion,
  AccordionItem,
  AccordionTrigger,
  AccordionContent,
} from '@/components/ui/accordion';

export type AboutFaqItem = {
  id: string;
  q: string;
  a: string;
};

export function AboutFaq({ items }: { items: readonly AboutFaqItem[] }) {
  return (
    <Accordion className="mt-8 flex w-full flex-col divide-y divide-ink/10">
      {items.map((f) => (
        <AccordionItem key={f.id} value={f.id}>
          <AccordionTrigger className="interactive-focus flex w-full items-center justify-between gap-6 py-5 text-left">
            <span className="font-display text-base font-semibold tracking-[-0.01em] text-ink md:text-lg">
              {f.q}
            </span>
            <span
              aria-hidden
              className="grid h-8 w-8 shrink-0 place-items-center rounded-full border border-ink/15 text-ink transition-transform group-data-[expanded]:rotate-45"
            >
              <svg
                viewBox="0 0 20 20"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="h-4 w-4"
              >
                <path d="M10 4v12M4 10h12" />
              </svg>
            </span>
          </AccordionTrigger>
          <AccordionContent>
            <p className="pb-5 pr-14 text-sm leading-relaxed text-ink/75 md:text-base">
              {f.a}
            </p>
          </AccordionContent>
        </AccordionItem>
      ))}
    </Accordion>
  );
}
