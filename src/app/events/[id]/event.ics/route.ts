import { getEventById } from "@/lib/events";
import { buildIcsContent } from "@/lib/events/actions";

export const dynamic = "force-dynamic";

function slugify(value: string) {
  return (
    value
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 60) || "event"
  );
}

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const event = await getEventById(id);
  if (!event) {
    return new Response("Event not found", { status: 404 });
  }

  return new Response(buildIcsContent(event), {
    headers: {
      "Content-Type": "text/calendar; charset=utf-8",
      "Content-Disposition": `attachment; filename="${slugify(event.title)}.ics"`,
    },
  });
}
