import "server-only";
import type { AdminEventRow, DuplicateReviewPair } from "./types";

/**
 * Admin deck data for HIGHLANDERHUB_E2E_FIXTURES runs, so the dashboard can be
 * rendered and tested without database credentials. Sign-in is unchanged: a
 * session must still verify against ADMIN_PASSWORD. Actions still call the
 * database, so in fixture mode they fail and show their errors.
 *
 * Times are relative to the request so every listing reads as upcoming.
 * `origin` serves the sample flyer from this app, which CSP img-src allows.
 */
export function adminFixtureDeck(origin: string): {
  events: AdminEventRow[];
  duplicatePairs: DuplicateReviewPair[];
} {
  const flyer = `${origin}/og-card.jpg`;
  const day = (offset: number, hour: number, minute = 0) => {
    const date = new Date();
    date.setUTCDate(date.getUTCDate() + offset);
    // Pacific is UTC-8 in winter and UTC-7 in summer; 8 keeps a local hour
    // on the intended day either way.
    date.setUTCHours(hour + 8, minute, 0, 0);
    return date.toISOString();
  };

  const base = (id: string, extra: Partial<AdminEventRow>): AdminEventRow => {
    const startsAt = extra.starts_at ?? day(3, 18);
    return {
      id,
      title: "",
      description: "",
      starts_at: startsAt,
      sort_at: startsAt,
      ends_at: null,
      all_day: false,
      location: "HUB 302",
      host: "Highlander Hub QA",
      host_handle: "highlanderhub",
      hosts: [],
      category: "hangout",
      content_kind: "student_event",
      tags: [],
      source: "instagram",
      source_url: null,
      image_url: null,
      has_free_food: false,
      rsvp_required: false,
      rsvp_url: null,
      scraped_at: day(-1, 12),
      is_locked: false,
      created_at: day(-2, 12),
      updated_at: day(-1, 12),
      ...extra,
    };
  };

  const quarterly = base("e2e-admin-quarterly", {
    title: "Wellness Wednesday: Bookmark Decorating",
    description: "Our bi-weekly events are back, Wellness Wednesday!",
    starts_at: day(8, 11),
    sort_at: day(8, 11),
    ends_at: day(8, 13),
    location: "Costo Hall 224",
    host: "Undocumented Student Programs",
    host_handle: "usp_ucr",
    category: "arts",
    source_url: "https://www.instagram.com/p/E2EQuarterly1/",
    image_url: flyer,
  });
  const single = base("e2e-admin-single", {
    title: "Undocumented Student Programs 10 Year Anniversary Bookmark Decorating",
    description: "The last wellness Wednesday event of the quarter.",
    starts_at: day(8, 11),
    sort_at: day(8, 11),
    location: "USP",
    host: "Undocumented Student Programs",
    host_handle: "usp_ucr",
    category: "arts",
    source_url: "https://www.instagram.com/p/E2ESingle1/",
  });
  const mixerA = base("e2e-admin-mixer-a", {
    title: "Engineering Mixer",
    starts_at: day(5, 17),
    sort_at: day(5, 17),
    ends_at: day(5, 19),
    location: "Bourns Hall A265",
    host: "Society of Women Engineers",
    host_handle: "swe.ucr",
    category: "career",
    source_url: "https://www.instagram.com/p/E2EMixerA1/",
    has_free_food: true,
  });
  const mixerB = base("e2e-admin-mixer-b", {
    title: "SWE x IEEE Engineering Mixer",
    starts_at: day(5, 17),
    sort_at: day(5, 17),
    location: "TBA",
    host: "IEEE at UCR",
    host_handle: "ieee.ucr",
    category: "career",
    source_url: "https://www.instagram.com/p/E2EMixerB1/",
    rsvp_url: "https://example.com/rsvp",
    rsvp_required: true,
  });

  const events: AdminEventRow[] = [
    base("e2e-admin-locked", {
      title: "Study Jam",
      starts_at: day(1, 19),
      sort_at: day(1, 19),
      ends_at: day(1, 22),
      location: "Orbach Library",
      host: "Associated Students",
      host_handle: "asucr",
      category: "academic",
      source_url: "https://www.instagram.com/p/E2ELocked1/",
      image_url: flyer,
      is_locked: true,
    }),
    base("e2e-admin-deadline", {
      title: "Spring Scholarship Applications Due",
      starts_at: day(2, 23, 59),
      sort_at: day(2, 23, 59),
      category: "academic",
      content_kind: "student_deadline",
      source: "campus_website",
      source_url: "https://example.com/scholarships",
    }),
    base("e2e-admin-fundraiser", {
      title: "Boba Benefit Night",
      starts_at: day(4, 18),
      sort_at: day(4, 18),
      location: "Kung Fu Tea",
      host: "Alpha Phi",
      host_handle: "alphaphi.ucr",
      category: "other",
      content_kind: "fundraiser",
      source_url: "https://www.instagram.com/p/E2EFundraiser/",
    }),
    mixerA,
    mixerB,
    quarterly,
    single,
  ];

  return {
    events,
    duplicatePairs: [
      { first: mixerA, second: mixerB },
      { first: quarterly, second: single },
    ],
  };
}
