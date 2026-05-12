import { promises as fs } from "fs";
import path from "path";
import type { CampusEvent, EventCategory } from "@/types/event";

const PIPELINE_OUTPUT = path.join(
  process.cwd(),
  "pipeline",
  "output",
  "stories.json"
);

// Hosts whose links are reliably "this is an event" signals on a story.
// A story with a CTA pointing at one of these is treated as an event even
// without a caption.
const EVENT_HOST_PATTERNS = [
  /(^|\.)lu\.ma$/i,
  /(^|\.)eventbrite\.com$/i,
  /(^|\.)highlanderlink\.ucr\.edu$/i,
  /(^|\.)events\.ucr\.edu$/i,
  /(^|\.)partiful\.com$/i,
];

type PipelineCategory = "campus" | "academic" | "club" | "sports" | "career";

interface RawStory {
  id: string;
  handle: string;
  account_label: string | null;
  account_category: PipelineCategory | null;
  is_video: boolean;
  posted_at: string;
  expires_at: string | null;
  image_url: string;
  video_url: string | null;
  caption: string | null;
  caption_mentions: string[];
  story_cta_url: string | null;
  permalink: string;
}

interface PipelineOutput {
  generatedAt: string;
  count: number;
  stories: RawStory[];
}

function mapCategory(c: PipelineCategory | null): EventCategory {
  switch (c) {
    case "academic":
      return "academic";
    case "club":
      return "club";
    case "sports":
      return "sports";
    case "career":
      return "career";
    case "campus":
    default:
      return "community";
  }
}

function looksLikeEvent(s: RawStory): boolean {
  if (s.caption && s.caption.trim().length > 0) return true;
  if (!s.story_cta_url) return false;
  try {
    const host = new URL(s.story_cta_url).hostname;
    return EVENT_HOST_PATTERNS.some((re) => re.test(host));
  } catch {
    return false;
  }
}

function toEvent(s: RawStory, generatedAt: string): CampusEvent {
  const host = s.account_label ?? `@${s.handle}`;
  const title = s.caption?.split("\n")[0]?.trim() || `${host} — story`;
  return {
    id: `ig_story_${s.id}`,
    title: title.slice(0, 140),
    description: s.caption ?? "",
    startsAt: s.posted_at, // best we have without OCR/LLM extraction
    location: "See story",
    host,
    hostHandle: `@${s.handle}`,
    category: mapCategory(s.account_category),
    tags: s.caption_mentions.map((m) => `@${m}`),
    source: "instagram",
    sourceUrl: s.story_cta_url ?? s.permalink,
    imageUrl: s.image_url,
    isFree: true,
    rsvpRequired: false,
    rsvpUrl: s.story_cta_url ?? undefined,
    scrapedAt: generatedAt,
  };
}

/**
 * Reads the pipeline's output and returns event-like stories.
 * Returns [] if the pipeline hasn't run yet (file missing), so the app
 * still renders during local dev.
 */
export async function getInstagramEvents(): Promise<CampusEvent[]> {
  let raw: string;
  try {
    raw = await fs.readFile(PIPELINE_OUTPUT, "utf-8");
  } catch (e: unknown) {
    if ((e as NodeJS.ErrnoException).code === "ENOENT") return [];
    throw e;
  }
  const parsed = JSON.parse(raw) as PipelineOutput;
  return parsed.stories
    .filter(looksLikeEvent)
    .map((s) => toEvent(s, parsed.generatedAt));
}
