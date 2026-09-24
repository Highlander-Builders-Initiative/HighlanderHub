// The time of day on campus, for the hero's day, golden-hour and night art.
//
// The sun's position comes from the US Naval Observatory's low-precision
// formulas (good to about a minute of sunrise/sunset through 2050), so the
// art turns with Riverside's actual sun through the year rather than at
// fixed hours.

export type CampusDaypart = "day" | "golden" | "night";

// The Bell Tower.
const UCR_LAT = 33.9737;
const UCR_LON = -117.3281;

// Golden hour: the sun from 4 degrees below the horizon to 6 above. In
// Riverside that runs about 45-55 minutes around both sunrise and sunset.
const GOLDEN_TOP_DEG = 6;
const GOLDEN_BOTTOM_DEG = -4;

const J2000_MS = Date.UTC(2000, 0, 1, 12);
const MS_PER_DAY = 24 * 60 * 60 * 1000;
const RAD = Math.PI / 180;

/** The sun's altitude above the horizon at a place and instant, in degrees. */
export function solarElevation(at: Date, lat: number, lon: number): number {
  const d = (at.getTime() - J2000_MS) / MS_PER_DAY;
  const g = (357.529 + 0.98560028 * d) * RAD; // mean anomaly
  const q = 280.459 + 0.98564736 * d; // mean longitude, degrees
  const L = (q + 1.915 * Math.sin(g) + 0.02 * Math.sin(2 * g)) * RAD; // ecliptic longitude
  const e = (23.439 - 0.00000036 * d) * RAD; // obliquity of the ecliptic

  const ra = Math.atan2(Math.cos(e) * Math.sin(L), Math.cos(L));
  const dec = Math.asin(Math.sin(e) * Math.sin(L));
  const gmstDeg = (18.697374558 + 24.06570982441908 * d) * 15;
  const hourAngle = (gmstDeg + lon) * RAD - ra;

  const phi = lat * RAD;
  return (
    Math.asin(
      Math.sin(phi) * Math.sin(dec) +
        Math.cos(phi) * Math.cos(dec) * Math.cos(hourAngle)
    ) / RAD
  );
}

/** Golden around sunrise and sunset, day above it, night below it. */
export function campusDaypart(at: Date = new Date()): CampusDaypart {
  const elevation = solarElevation(at, UCR_LAT, UCR_LON);
  if (elevation > GOLDEN_TOP_DEG) return "day";
  if (elevation > GOLDEN_BOTTOM_DEG) return "golden";
  return "night";
}
