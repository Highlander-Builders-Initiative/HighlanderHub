import Image from "next/image";
import type { CampusDaypart } from "@/lib/daylight";
import daySkyline from "./campus-skyline-day.webp";
import goldenSkyline from "./campus-skyline-golden.webp";
import nightSkyline from "./campus-skyline-night.webp";

/* Campus skyline — the hero's sense of place.
 *
 * A single illustration: the Bell Tower, the Box Springs range with the Big C,
 * and palms over a grove at its feet. It is anchored to the hero's bottom
 * edge, so the tree line and the tower's base stand on the hairline above the
 * flyer wall.
 *
 * It comes in three versions and follows the sun over campus (`campusDaypart`,
 * picked by the home page): the golden-hour art (the tower against a low sun)
 * around sunrise and sunset, the day art between, and the night art (a full
 * moon behind the tower, its belfry lit) after dark. The home page renders
 * per request, so the choice is made on the server and only that version
 * loads.
 *
 * All three are 2x AI upscales (Real-ESRGAN, anime model) of the original art
 * on a shared 4000x1484 canvas, so they stay sharp on Retina screens up to
 * ~1940px wide. Day and night have their sky cut out, so the page shows
 * through as the sky, and are graded down to the golden-hour art's softness
 * (less saturation, lifted shadows, haze on the mountains but not the tower)
 * so the scene backs the copy instead of competing with it. Golden hour keeps
 * its painted sky, whose glow is the sun, and the hero fades into it
 * (`.skyline-hero` in globals.css).
 *
 * Sizing lives in globals.css (`.skyline-hero`). On phones the band keeps a
 * floor height and crops the sides; `object-position` holds the tower in frame.
 * Nothing here animates, so the scrolling wall below stays the only thing in
 * motion.
 *
 * In dark mode every version multiplies into a dusk gradient (`.skyline-root`
 * in globals.css).
 */

const ART = { day: daySkyline, golden: goldenSkyline, night: nightSkyline };

// Rendered width once the height floor kicks in (240px x the art's 4000:1484
// ratio). Below that viewport width the image is wider than the screen.
const FLOOR_WIDTH = 647;

export function CampusSkyline({ daypart }: { daypart: CampusDaypart }) {
  return (
    <div
      aria-hidden
      className="skyline-root pointer-events-none absolute inset-x-0 bottom-0"
    >
      <Image
        src={ART[daypart]}
        alt=""
        fill
        preload
        quality={90}
        sizes={`(max-width: ${FLOOR_WIDTH}px) ${FLOOR_WIDTH}px, 100vw`}
        className="object-cover object-[78%_12%]"
      />
    </div>
  );
}
