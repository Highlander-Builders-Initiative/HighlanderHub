import type { CampusEvent } from "@/types/event";

// PLACEHOLDER DATA - replace with scraped data from:
// - Instagram (@ucriverside, club accounts)
// - Highlander Link (highlanderlink.ucr.edu)
// - UCR campus calendar (events.ucr.edu)
// - Individual club websites
//
// Each event below shows the expected shape. Scraper output should
// conform to the CampusEvent type defined in src/types/event.ts.

const today = new Date();
const daysFromNow = (n: number, hour = 18): string => {
  const d = new Date(today);
  d.setDate(d.getDate() + n);
  d.setHours(hour, 0, 0, 0);
  return d.toISOString();
};

export const PLACEHOLDER_EVENTS: CampusEvent[] = [
  {
    id: "evt_001",
    title: "ACM General Meeting — Intro to System Design",
    description:
      "Kickoff GM for the quarter. Pizza, intros, and a short talk on system design fundamentals. New members welcome.",
    startsAt: daysFromNow(1, 19),
    endsAt: daysFromNow(1, 20),
    location: "Winston Chung Hall 205",
    host: "ACM at UCR",
    hostHandle: "@acm.ucr",
    category: "club",
    tags: ["cs", "tech", "free food"],
    source: "instagram",
    sourceUrl: "https://instagram.com/acm.ucr",
    isFree: true,
    rsvpRequired: false,
    scrapedAt: new Date().toISOString(),
  },
  {
    id: "evt_002",
    title: "Bioinformatics Research Showcase",
    description:
      "Undergrad and grad students present current research in computational biology, genomics, and NGS analysis.",
    startsAt: daysFromNow(3, 16),
    endsAt: daysFromNow(3, 18),
    location: "Genomics Building Auditorium",
    host: "UCR Genomics Institute",
    category: "academic",
    tags: ["research", "biology", "cs"],
    source: "campus_website",
    sourceUrl: "https://events.ucr.edu",
    isFree: true,
    rsvpRequired: true,
    rsvpUrl: "https://events.ucr.edu/rsvp/placeholder",
    scrapedAt: new Date().toISOString(),
  },
  {
    id: "evt_003",
    title: "Cybersecurity Club CTF Night",
    description:
      "Capture the Flag night. Beginner-friendly challenges in web, crypto, and reversing. Bring a laptop.",
    startsAt: daysFromNow(2, 18),
    endsAt: daysFromNow(2, 22),
    location: "Bourns Hall A265",
    host: "Cybersecurity @ UCR",
    hostHandle: "@cyberucr",
    category: "club",
    tags: ["security", "ctf", "cs"],
    source: "instagram",
    isFree: true,
    rsvpRequired: false,
    scrapedAt: new Date().toISOString(),
  },
  {
    id: "evt_004",
    title: "Career Fair: Tech & Engineering",
    description:
      "Recruiters from FAANG, defense, and local SoCal startups. Bring resumes. Business casual recommended.",
    startsAt: daysFromNow(5, 11),
    endsAt: daysFromNow(5, 15),
    location: "HUB 302",
    host: "Career Center",
    category: "career",
    tags: ["jobs", "internships", "networking"],
    source: "campus_website",
    isFree: true,
    rsvpRequired: true,
    rsvpUrl: "https://career.ucr.edu/placeholder",
    scrapedAt: new Date().toISOString(),
  },
  {
    id: "evt_005",
    title: "Free Tacos at the Bell Tower",
    description:
      "ASUCR is grilling. First 200 students. Vegetarian option available.",
    startsAt: daysFromNow(0, 12),
    endsAt: daysFromNow(0, 14),
    location: "Bell Tower Lawn",
    host: "ASUCR",
    hostHandle: "@asucr",
    category: "free_food",
    tags: ["free food", "social"],
    source: "instagram",
    isFree: true,
    rsvpRequired: false,
    scrapedAt: new Date().toISOString(),
  },
  {
    id: "evt_006",
    title: "NSBE General Body Meeting",
    description:
      "Discussion of upcoming regional conference, mentorship pairings, and a guest talk from an alum at Lockheed.",
    startsAt: daysFromNow(4, 19),
    endsAt: daysFromNow(4, 20),
    location: "Materials Science & Engineering 116",
    host: "NSBE UCR",
    hostHandle: "@nsbeucr",
    category: "club",
    tags: ["engineering", "professional"],
    source: "instagram",
    isFree: true,
    rsvpRequired: false,
    scrapedAt: new Date().toISOString(),
  },
  {
    id: "evt_007",
    title: "Mt. Rubidoux Sunrise Hike",
    description:
      "Outdoor Excursions hike up Mt. Rubidoux. Meet at the HUB at 5:45am. Easy 3-mile loop.",
    startsAt: daysFromNow(6, 6),
    endsAt: daysFromNow(6, 9),
    location: "Mt. Rubidoux, Riverside",
    host: "Outdoor Excursions",
    category: "community",
    tags: ["outdoors", "hiking", "riverside"],
    source: "campus_website",
    isFree: true,
    rsvpRequired: true,
    rsvpUrl: "https://recreation.ucr.edu/placeholder",
    scrapedAt: new Date().toISOString(),
  },
  {
    id: "evt_008",
    title: "Highlanders vs. UCI — Men's Basketball",
    description:
      "Big West conference matchup. Student tickets free with R'Card.",
    startsAt: daysFromNow(7, 19),
    endsAt: daysFromNow(7, 21),
    location: "SRC Arena",
    host: "UCR Athletics",
    category: "sports",
    tags: ["basketball", "big west"],
    source: "campus_website",
    isFree: true,
    rsvpRequired: false,
    scrapedAt: new Date().toISOString(),
  },
  {
    id: "evt_009",
    title: "Open Mic at the Barn",
    description:
      "Poetry, music, comedy. Sign up at the door starting 7pm. Drinks and snacks available.",
    startsAt: daysFromNow(2, 20),
    endsAt: daysFromNow(2, 23),
    location: "The Barn",
    host: "The Barn",
    hostHandle: "@thebarn.ucr",
    category: "arts",
    tags: ["music", "performance"],
    source: "instagram",
    isFree: true,
    rsvpRequired: false,
    scrapedAt: new Date().toISOString(),
  },
  {
    id: "evt_010",
    title: "Riverside Art Walk — First Thursday",
    description:
      "Downtown Riverside galleries open late. Free shuttle from UCR. Food trucks on Main St.",
    startsAt: daysFromNow(8, 18),
    endsAt: daysFromNow(8, 22),
    location: "Downtown Riverside, Main St",
    host: "City of Riverside",
    category: "community",
    tags: ["art", "downtown", "off-campus"],
    source: "club_website",
    isFree: true,
    rsvpRequired: false,
    scrapedAt: new Date().toISOString(),
  },
];
