import Image from "next/image";
import skyline from "./campus-skyline.webp";

/* Campus skyline — the hero's sense of place.
 *
 * A single illustration: the Bell Tower against a low sun, the Box Springs
 * range with the Big C, and palms over a grove at its feet. It is anchored to
 * the hero's bottom edge, so the tree line and the tower's base stand on the
 * hairline above the flyer wall.
 *
 * The asset is a 2x AI upscale (Real-ESRGAN, anime model) of the original
 * 2000px art, so it stays sharp on Retina screens up to ~1940px wide.
 *
 * Sizing lives in globals.css (`.skyline-hero`). On phones the band keeps a
 * floor height and crops the sides; `object-position` holds the tower in frame.
 * Nothing here animates, so the scrolling wall below stays the only thing in
 * motion.
 *
 * In dark mode the art multiplies into a dusk gradient (`.skyline-root` in
 * globals.css): the sky meets the page's canvas at the top edge and lifts
 * toward the horizon, so the hero copy stays legible over it.
 */

// Rendered width once the height floor kicks in (240px x the art's 4000:1484
// ratio). Below that viewport width the image is wider than the screen.
const FLOOR_WIDTH = 647;

export function CampusSkyline() {
  return (
    <div
      aria-hidden
      className="skyline-root pointer-events-none absolute inset-x-0 bottom-0"
    >
      <Image
        src={skyline}
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
