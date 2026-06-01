import { NextResponse } from "next/server";
import { notifyNewSubmission } from "@/lib/discord";
import { parseSubmissionInsert } from "@/lib/submissions";
import { supabase } from "@/lib/supabase";
import {
  SUBMISSION_RATE_LIMIT,
  clientIp,
  rateLimit,
  rateLimitHeaders,
} from "@/lib/rate-limit";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function POST(request: Request) {
  // Throttle before doing any work: each submission writes a DB row and fires a
  // Discord webhook, so an unthrottled endpoint floods both.
  const limit = rateLimit(
    `submissions:${clientIp(request.headers)}`,
    SUBMISSION_RATE_LIMIT
  );
  if (!limit.ok) {
    return NextResponse.json(
      { error: "Too many submissions. Please try again in a few minutes." },
      { status: 429, headers: rateLimitHeaders(limit) }
    );
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const parsed = parseSubmissionInsert(body);
  if (!parsed.ok) {
    return NextResponse.json({ error: parsed.error }, { status: 400 });
  }

  const row = parsed.row;
  const { error } = await supabase.from("submissions").insert(row);

  if (error) {
    return NextResponse.json(
      { error: "Could not save submission." },
      { status: 500 }
    );
  }

  await notifyNewSubmission(row);

  return NextResponse.json({ ok: true });
}
