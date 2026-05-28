import { NextResponse } from "next/server";
import { notifyNewSubmission } from "@/lib/discord";
import { pickSubmissionFields } from "@/lib/submissions";
import { supabase } from "@/lib/supabase";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

function isObjectPayload(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  if (!isObjectPayload(body)) {
    return NextResponse.json(
      { error: "Invalid submission payload." },
      { status: 400 }
    );
  }

  const row = pickSubmissionFields(body);
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
