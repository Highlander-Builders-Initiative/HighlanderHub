import { NextResponse } from "next/server";
import { notifyNewSubmission } from "@/lib/discord";
import { parseSubmissionInsert } from "@/lib/submissions";
import { supabase } from "@/lib/supabase";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function POST(request: Request) {
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
