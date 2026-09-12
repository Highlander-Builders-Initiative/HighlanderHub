import type { Metadata } from "next";
import { notFound } from "next/navigation";
import {
  EventDetailView,
} from "@/components/events/EventDetailView";
import { getEventById } from "@/lib/events";
import { SITE_NAME, SITE_PREVIEW_IMAGE, absoluteUrl } from "@/lib/seo";
import { normalizeHttpUrl } from "@/lib/events/validation";
import { isPublicContentKind } from "@/lib/events/content-kind";
import type { CampusEvent } from "@/types/event";

// Rendered per request: the no-store Supabase client (see lib/supabase.ts) bars
// static prerendering. getEventById reads through the Data Cache (see lib/events)
// so repeat views skip the round-trip; admin edits bust it via revalidateTag.
export const dynamic = "force-dynamic";

function jsonLdHtml(data: Record<string, unknown>): string {
  return JSON.stringify(data).replace(/</g, "\\u003c");
}

function eventLocationJsonLd(location: string): Record<string, unknown> {
  const name = location.trim() || "UC Riverside";
  return {
    "@type": "Place",
    name,
    address: {
      "@type": "PostalAddress",
      addressLocality: "Riverside",
      addressRegion: "CA",
      addressCountry: "US",
    },
  };
}

function eventJsonLd(
  event: CampusEvent,
  registrationUrl: string | null
): Record<string, unknown> {
  const url = absoluteUrl(`/events/${event.id}`);
  const offers =
    event.isFree || registrationUrl
      ? {
          "@type": "Offer",
          url: registrationUrl ?? url,
          ...(event.isFree
            ? {
                price: "0",
                priceCurrency: "USD",
                availability: "https://schema.org/InStock",
              }
            : {}),
        }
      : undefined;

  return {
    "@context": "https://schema.org",
    "@type": "Event",
    "@id": `${url}#event`,
    name: event.title,
    description: event.description.trim() || event.title,
    url,
    startDate: event.startsAt,
    ...(event.endsAt ? { endDate: event.endsAt } : {}),
    eventAttendanceMode: "https://schema.org/OfflineEventAttendanceMode",
    eventStatus: "https://schema.org/EventScheduled",
    location: eventLocationJsonLd(event.location),
    ...(event.imageUrl ? { image: [absoluteUrl(event.imageUrl)] } : {}),
    organizer: {
      "@type": "Organization",
      name: event.host || SITE_NAME,
      ...(event.sourceUrl ? { url: event.sourceUrl } : {}),
    },
    ...(offers ? { offers } : {}),
  };
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const event = await getEventById(id);
  if (!event) return { title: "Event not found · Highlander Hub" };
  const title = event.title;
  const description = event.description.slice(0, 160);
  const url = `/events/${event.id}`;
  const image = event.imageUrl ?? SITE_PREVIEW_IMAGE;

  return {
    title,
    description,
    alternates: {
      canonical: url,
    },
    openGraph: {
      type: "article",
      siteName: SITE_NAME,
      title,
      description,
      url,
      images: [
        {
          url: image,
          alt: `${event.title} event preview`,
        },
      ],
    },
    twitter: {
      card: event.imageUrl ? "summary_large_image" : "summary",
      title,
      description,
      images: [absoluteUrl(image)],
    },
  };
}

export default async function EventDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const event = await getEventById(id);
  if (!event) notFound();

  const primaryUrl =
    normalizeHttpUrl(event.rsvpUrl) ?? normalizeHttpUrl(event.sourceUrl);
  const structuredData = isPublicContentKind(event.contentKind)
    ? eventJsonLd(event, primaryUrl)
    : null;

  return (
    <>
      {structuredData && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: jsonLdHtml(structuredData) }}
        />
      )}
      <EventDetailView event={event} variant="modal" />
    </>
  );
}
