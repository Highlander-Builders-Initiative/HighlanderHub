/** The pipeline's cron hours (.github/workflows/scrape.yml: `0 *\/8 * * *`). */
const RUN_HOURS_UTC = [0, 8, 16];

const campusClock = new Intl.DateTimeFormat("en-US", {
  timeZone: "America/Los_Angeles",
  hour: "numeric",
  minute: "numeric",
  hourCycle: "h23",
});
const campusHourLabel = new Intl.DateTimeFormat("en-US", {
  timeZone: "America/Los_Angeles",
  hour: "numeric",
});

/**
 * The day's runs on campus time, earliest first ("1 AM", "9 AM", "5 PM" while
 * daylight saving is on). Worked out per call, so the clock change moves
 * them. GitHub starts scheduled jobs late as often as not, so copy should say
 * "around".
 */
export function campusRunTimes(now: Date = new Date()): string[] {
  return RUN_HOURS_UTC.map((hour) => {
    const run = new Date(
      Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), hour)
    );
    const parts = campusClock.formatToParts(run);
    const get = (type: string) =>
      Number(parts.find((part) => part.type === type)?.value ?? 0);
    return { label: campusHourLabel.format(run), at: get("hour") * 60 + get("minute") };
  })
    .sort((a, b) => a.at - b.at)
    .map((run) => run.label);
}
