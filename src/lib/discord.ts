type AlertRow = Record<string, unknown>;

const MESSAGE_LIMIT = 1900;

function text(value: unknown, fallback = ""): string {
  return typeof value === "string" && value.trim() ? value.trim() : fallback;
}

function formatWhen(value: unknown): string {
  if (typeof value !== "string") return "Time TBD";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Time TBD";

  return new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Los_Angeles",
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function compact(parts: Array<string | null | undefined>): string {
  return parts.filter(Boolean).join("\n").slice(0, MESSAGE_LIMIT);
}

export function buildSubmissionDiscordMessage(row: AlertRow): string {
  const title = text(row.title, "Untitled submission");
  const host = text(row.host);
  const location = text(row.location);

  return compact([
    "New Highlander Hub submission needs review",
    `**${title}**`,
    formatWhen(row.starts_at),
    host ? `Hosted by ${host}` : null,
    location || null,
    "Review: /admin",
  ]);
}

export async function postDiscordWebhook(content: string): Promise<boolean> {
  const webhookUrl = process.env.DISCORD_WEBHOOK_URL;
  if (!webhookUrl) return false;

  try {
    const response = await fetch(webhookUrl, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ content, allowed_mentions: { parse: [] } }),
    });

    if (!response.ok) {
      console.warn(`Discord webhook failed with status ${response.status}`);
      return false;
    }

    return true;
  } catch (error) {
    console.warn("Discord webhook failed", error);
    return false;
  }
}

export async function notifyNewSubmission(row: AlertRow): Promise<boolean> {
  return postDiscordWebhook(buildSubmissionDiscordMessage(row));
}
