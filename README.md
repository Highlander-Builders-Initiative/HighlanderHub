# The Highlander Daily

A campus & club events bulletin for UC Riverside and the city of Riverside.

> ⚠️ **Bare-bones scaffold.** Currently displays placeholder events. The
> scraping layer (Instagram, Highlander Link, UCR events calendar, club
> sites) is **not wired up yet** — that's the next step.

## Stack

- **Next.js 14** (App Router, server components by default)
- **TypeScript**
- **Tailwind CSS** with custom palette
- **Fraunces / Instrument Serif / DM Mono** for that editorial newspaper feel

## Getting started

```bash
npm install
npm run dev
```

Then open [http://localhost:3000](http://localhost:3000).

## Project structure

```
src/
├── app/
│   ├── api/events/route.ts    # GET /api/events — stub, returns placeholders
│   ├── globals.css            # Tailwind + custom CSS (fonts, grain, etc.)
│   ├── layout.tsx
│   └── page.tsx               # Home / events bulletin
├── components/
│   ├── CategoryBadge.tsx
│   ├── EventCard.tsx
│   ├── EventsBrowser.tsx      # Client component — filtering + grouping by day
│   ├── Footer.tsx
│   ├── Marquee.tsx
│   └── Masthead.tsx
├── data/
│   └── placeholder-events.ts  # 👈 Sample events shaped like real ones
├── lib/
│   ├── dates.ts
│   └── events.ts              # getEvents() — swap this when scrapers are ready
└── types/
    └── event.ts               # CampusEvent interface — the source of truth
```

## Wiring up real data later

The whole app reads from one function: `getEvents()` in `src/lib/events.ts`.
Right now it returns the placeholder array. When scrapers are ready, replace
its body with a `fetch("/api/events")` or a direct DB query.

The UI doesn't need to change — as long as scraper output conforms to the
`CampusEvent` type in `src/types/event.ts`, it'll render correctly.

### Suggested scraper layout

```
src/lib/scrapers/
├── instagram.ts      # Pulls posts from club Instagram accounts
├── highlander.ts     # Scrapes highlanderlink.ucr.edu
├── ucr-events.ts     # Scrapes events.ucr.edu
└── club-sites.ts     # Hits individual club websites
```

Each returns `Promise<CampusEvent[]>`. A coordinator (cron job, or a
separate `/api/scrape` route) calls them all and writes to a data store
(Postgres / Supabase / a JSON file / Redis — your call).

### CampusEvent shape

See `src/types/event.ts`. Every event needs at minimum:
`id`, `title`, `description`, `startsAt`, `location`, `host`, `category`,
`source`, `scrapedAt`. Optional fields cover RSVP, images, social handles, etc.

## Design notes

The aesthetic is **sun-bleached newspaper bulletin** — warm bone background,
ink-black serif headlines (Fraunces), italic Instrument Serif for editorial
runs, DM Mono for metadata. Subtle paper grain via radial-gradient dots.
Hover-lift cards with hard shadow on hover.

Tweak everything in `tailwind.config.ts` (palette) and `src/app/globals.css`
(typography + texture).

## Scripts

| Script | What it does |
| --- | --- |
| `npm run dev` | Start the dev server on :3000 |
| `npm run build` | Production build |
| `npm run start` | Run the production build |
| `npm run lint` | ESLint |

## License

MIT or whatever you want — it's your project.
