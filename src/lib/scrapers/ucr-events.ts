import { promises as fs } from "fs";
import path from "path";
import type { CampusEvent, EventCategory, EventSource } from "@/types/event";

const PIPELINE_OUTPUT = path.join(
  process.cwd(),
  "pipeline",
  "output",
  "events.json"
);

// The pipeline already emits CampusEvent-shaped objects, so this adapter is
// mostly a "trust but verify" boundary: validate the enums, coerce nullables,
// and drop anything malformed rather than letting it crash the page.

const CATEGORIES: EventCategory[] = [
  "club",
  "academic",
  "social",
  "career",
  "sports",
  "arts",
  "community",
  "free_food",
];

const SOURCES: EventSource[] = [
  "instagram",
  "highlander_link",
  "campus_website",
  "club_website",
  "manual",
];

interface RawEvent {
  id: string;
  title: string;
  description: string;
  startsAt: string;
  endsAt: string | null;
  location: string;
  host: string;
  hostHandle?: string | null;
  category: string;
  tags: string[];
  source: string;
  sourceUrl?: string | null;
  imageUrl?: string | null;
  isFree: boolean;
  rsvpRequired: boolean;
  rsvpUrl?: string | null;
  scrapedAt: string;
}

interface PipelineOutput {
  generatedAt: string;
  count: number;
  events: RawEvent[];
}

function coerce(raw: RawEvent): CampusEvent | null {
  if (!raw?.id || !raw.title || !raw.startsAt) return null;
  const category: EventCategory = CATEGORIES.includes(
    raw.category as EventCategory
  )
    ? (raw.category as EventCategory)
    : "community";
  const source: EventSource = SOURCES.includes(raw.source as EventSource)
    ? (raw.source as EventSource)
    : "campus_website";

  return {
    id: raw.id,
    title: raw.title,
    description: raw.description ?? "",
    startsAt: raw.startsAt,
    endsAt: raw.endsAt ?? undefined,
    location: raw.location || "UC Riverside",
    host: raw.host || "UC Riverside",
    hostHandle: raw.hostHandle ?? undefined,
    category,
    tags: Array.isArray(raw.tags) ? raw.tags : [],
    source,
    sourceUrl: raw.sourceUrl ?? undefined,
    imageUrl: raw.imageUrl ?? undefined,
    isFree: raw.isFree ?? true,
    rsvpRequired: raw.rsvpRequired ?? false,
    rsvpUrl: raw.rsvpUrl ?? undefined,
    scrapedAt: raw.scrapedAt,
  };
}

/**
 * Reads pipeline/output/events.json (UCR Localist events, normalized).
 * Returns [] if the pipeline hasn't run yet (file missing), so the app
 * still renders during local dev.
 */
export async function getUcrEvents(): Promise<CampusEvent[]> {
  let raw: string;
  try {
    raw = await fs.readFile(PIPELINE_OUTPUT, "utf-8");
  } catch (e: unknown) {
    if ((e as NodeJS.ErrnoException).code === "ENOENT") return [];
    throw e;
  }
  const parsed = JSON.parse(raw) as PipelineOutput;
  const events: CampusEvent[] = [];
  for (const r of parsed.events ?? []) {
    const ev = coerce(r);
    if (ev) events.push(ev);
  }
  return events;
}
