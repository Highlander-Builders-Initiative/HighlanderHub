#!/usr/bin/env node
/**
 * Render the app icon: the h/h wordmark restacked to fit a square, one
 * Bricolage Grotesque "h" top-left and one bottom-right with the wordmark's
 * slash cutting the white tile edge to edge between them.
 * Pass a local Bricolage Grotesque Latin WOFF2 (from a Next build) to work offline:
 * node scripts/render-brand-icons.mjs /path/to/bricolage-latin.woff2
 */
import { chromium } from "@playwright/test";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import sharp from "sharp";

const SIZE = 1024;
const TILE = "#ffffff";
const INK = "#0f1115";
// The wordmark's muted gray.
const SLASH = "#6b7280";
// Bricolage's "/" leans 0.315 px right per px up; its stroke is about as wide
// horizontally as the h's stem.
const SLANT = 0.315;
const SLASH_WIDTH = 60;
const GLYPH_HEIGHT = 400;
const GLYPH_INSET = 140;
// How far the slash stops short of the tile edge; negative runs it edge to edge.
const SLASH_INSET = -10;

const root = new URL("../public/", import.meta.url);
if (!process.argv[2]) throw new Error("Pass the Bricolage Grotesque Latin WOFF2 path.");
const font = (await readFile(process.argv[2])).toString("base64");
const browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL || undefined });
try {
  const page = await browser.newPage({ viewport: { width: 1024, height: 1024 } });
  await page.setContent(`<!doctype html><style>
    @font-face { font-family: Bricolage; src: url(data:font/woff2;base64,${font}); font-weight: 100 900; }
    html, body { margin: 0; width: 1024px; height: 1024px; background: transparent; }
    body { display: grid; place-items: center; }
    .mark { font-family: Bricolage; font-size: 900px; font-weight: 700;
      font-optical-sizing: auto; line-height: 1; color: ${INK}; }
  </style><div class="mark">h</div>`);
  await page.evaluate(() => document.fonts.ready);
  if (!(await page.evaluate(() => document.fonts.check("700 900px Bricolage")))) {
    throw new Error("Bricolage failed to load.");
  }
  // Size from the glyph's visible bounds, not the font's line box.
  const glyph = await sharp(await page.screenshot({ omitBackground: true }))
    .trim()
    .resize({ height: GLYPH_HEIGHT })
    .png()
    .toBuffer();
  const { width: gw, height: gh } = await sharp(glyph).metadata();

  const x = (y) => SIZE / 2 + (SIZE / 2 - y) * SLANT;
  const [y0, y1] = [SLASH_INSET, SIZE - SLASH_INSET];
  const slash = (w) => Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="${SIZE}" height="${SIZE}"><polygon points="${x(y0) - w / 2},${y0} ${x(y0) + w / 2},${y0} ${x(y1) + w / 2},${y1} ${x(y1) - w / 2},${y1}" fill="${SLASH}"/></svg>`);
  // The two h's alone, on transparent.
  const letters = await sharp({ create: { width: SIZE, height: SIZE, channels: 4, background: "#0000" } })
    .composite([
      { input: glyph, left: GLYPH_INSET, top: GLYPH_INSET },
      { input: glyph, left: SIZE - GLYPH_INSET - gw, top: SIZE - GLYPH_INSET - gh },
    ])
    .png()
    .toBuffer();
  const tile = (layers, rx = 0) =>
    sharp(Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="${SIZE}" height="${SIZE}"><rect width="${SIZE}" height="${SIZE}" rx="${rx}" fill="${TILE}"/></svg>`))
      .composite(layers.map((input) => ({ input, blend: rx ? "atop" : "over" })))
      .png()
      .toBuffer();

  // Rounded tile for browser tabs and desktop installs, where nothing masks it.
  const png = await tile([slash(SLASH_WIDTH), letters], Math.round(SIZE * 0.22));
  // Full-bleed square for iOS, which rounds the corners itself.
  const square = await tile([slash(SLASH_WIDTH), letters]);
  // Android masks to shapes as small as a circle 80% wide: shrink the letters
  // into it, but keep the slash running edge to edge.
  const inner = 820; // even, so the padding splits evenly
  const pad = (SIZE - inner) / 2;
  const maskable = await tile([
    slash(SLASH_WIDTH * (inner / SIZE)),
    await sharp(letters).resize(inner, inner)
      .extend({ top: pad, bottom: pad, left: pad, right: pad, background: "#0000" })
      .png().toBuffer(),
  ]);

  await mkdir(new URL("brand/", root), { recursive: true });
  await writeFile(new URL("brand/highlanderhub-icon.png", root), png);
  for (const [name, size] of [["icon-192.png", 192], ["icon-512.png", 512]]) {
    await sharp(png).resize(size, size).png().toFile(fileURLToPath(new URL(name, root)));
  }
  await sharp(maskable).resize(512, 512).png().toFile(fileURLToPath(new URL("icon-maskable-512.png", root)));
  await sharp(square).resize(180, 180).flatten({ background: TILE }).png()
    .toFile(fileURLToPath(new URL("apple-touch-icon.png", root)));

  // Conventional 32-bit DIB frames for browser and OS ICO compatibility.
  const sizes = [16, 32, 48];
  const directory = Buffer.alloc(6 + sizes.length * 16);
  directory.writeUInt16LE(1, 2);
  directory.writeUInt16LE(sizes.length, 4);
  const frames = [];
  let offset = directory.length;
  for (const [index, size] of sizes.entries()) {
    const rgba = await sharp(png).resize(size, size).ensureAlpha().raw().toBuffer();
    const pixels = size * size * 4;
    const mask = Math.ceil(size / 32) * 4 * size;
    const frame = Buffer.alloc(40 + pixels + mask);
    frame.writeUInt32LE(40, 0);
    frame.writeInt32LE(size, 4);
    frame.writeInt32LE(size * 2, 8);
    frame.writeUInt16LE(1, 12);
    frame.writeUInt16LE(32, 14);
    frame.writeUInt32LE(pixels + mask, 20);
    for (let y = 0; y < size; y++) {
      for (let x = 0; x < size; x++) {
        const source = (y * size + x) * 4;
        const target = 40 + ((size - 1 - y) * size + x) * 4;
        frame[target] = rgba[source + 2];
        frame[target + 1] = rgba[source + 1];
        frame[target + 2] = rgba[source];
        frame[target + 3] = rgba[source + 3];
      }
    }
    const entry = 6 + index * 16;
    directory[entry] = size;
    directory[entry + 1] = size;
    directory.writeUInt16LE(1, entry + 4);
    directory.writeUInt16LE(32, entry + 6);
    directory.writeUInt32LE(frame.length, entry + 8);
    directory.writeUInt32LE(offset, entry + 12);
    frames.push(frame);
    offset += frame.length;
  }
  await writeFile(new URL("favicon.ico", root), Buffer.concat([directory, ...frames]));
  console.log("Rendered the h/h app icons and favicon.");
} finally {
  await browser.close();
}
