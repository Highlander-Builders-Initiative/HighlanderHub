import type { CampusEvent } from "@/types/event";
import { isPublicContentKind } from "@/lib/events/content-kind";

/** Canonical student-event fixture (the showcase used across browse specs). */
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
  contentKind: "student_event",
  tags: ["e2e", "qa"],
  source: "manual",
  sourceUrl: "https://example.com/e2e-event",
  imageUrl: undefined,
  isFree: true,
  hasFreeFood: false,
  rsvpRequired: false,
  rsvpUrl: undefined,
  scrapedAt: "2026-05-18T12:00:00.000Z",
};

/** One fixture per content_kind so e2e can prove the public visibility rule. */
export const E2E_FIXTURE_EVENTS: CampusEvent[] = [
  E2E_FIXTURE_EVENT,
  {
    ...E2E_FIXTURE_EVENT,
    id: "e2e-student-deadline",
    title: "E2E Deadline: Scholarship Applications Due",
    description:
      "A deterministic student deadline used by Playwright to verify deadline labeling.",
    startsAt: "2026-05-21T23:59:00.000-07:00",
    endsAt: undefined,
    category: "academic",
    contentKind: "student_deadline",
    tags: ["e2e", "scholarship"],
  },
  {
    ...E2E_FIXTURE_EVENT,
    id: "e2e-fundraiser",
    title: "E2E Fundraiser: Boba Benefit Night",
    description:
      "A deterministic fundraiser used by Playwright to verify it is excluded from browse.",
    startsAt: "2026-05-22T18:00:00.000-07:00",
    endsAt: undefined,
    category: "community",
    contentKind: "fundraiser",
    tags: ["e2e", "fundraiser"],
  },
  {
    ...E2E_FIXTURE_EVENT,
    id: "e2e-other",
    title: "E2E Other: Campus Facilities Notice",
    description:
      "A deterministic non-student official item used to verify it is excluded from browse.",
    startsAt: "2026-05-23T09:00:00.000-07:00",
    endsAt: undefined,
    category: "community",
    contentKind: "other",
    tags: ["e2e"],
  },
];

/** Fixtures the public surfaces are allowed to show. */
export const E2E_PUBLIC_FIXTURE_EVENTS: CampusEvent[] =
  E2E_FIXTURE_EVENTS.filter((event) => isPublicContentKind(event.contentKind));

export function e2eFixturesEnabled(): boolean {
  return process.env.HIGHLANDERHUB_E2E_FIXTURES === "1";
}
