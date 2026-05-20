import type { CampusEvent } from "@/types/event";

export const E2E_FIXTURE_EVENT: CampusEvent = {
  id: "e2e-highlander-hub-showcase",
  title: "E2E Test: Highlander Hub Showcase",
  description:
    "A deterministic event used by Playwright to verify the browse and detail flow.",
  startsAt: "2026-05-20T18:30:00.000-07:00",
  endsAt: "2026-05-20T20:00:00.000-07:00",
  location: "HUB 302",
  host: "Highlander Hub QA",
  hostHandle: "@highlanderhub",
  category: "social",
  tags: ["e2e", "qa"],
  source: "manual",
  sourceUrl: "https://example.com/e2e-event",
  imageUrl: undefined,
  isFree: true,
  rsvpRequired: false,
  rsvpUrl: undefined,
  scrapedAt: "2026-05-18T12:00:00.000Z",
};

export function useE2eFixtures(): boolean {
  return process.env.HIGHLANDERHUB_E2E_FIXTURES === "1";
}
