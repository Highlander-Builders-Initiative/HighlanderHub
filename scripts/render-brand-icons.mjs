#!/usr/bin/env node
/**
 * Render the existing Bricolage wordmark as h/h on a white square.
 * Pass a local Bricolage Grotesque Latin WOFF2 (from a Next build) to work offline:
 * node scripts/render-brand-icons.mjs /path/to/bricolage-latin.woff2
 */
import { chromium } from "@playwright/test";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import sharp from "sharp";

const root = new URL("../public/", import.meta.url);
if (!process.argv[2]) throw new Error("Pass the Bricolage Grotesque Latin WOFF2 path.");
const font = (await readFile(process.argv[2])).toString("base64");
const browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL || undefined });
try {
  const page = await browser.newPage({ viewport: { width: 1024, height: 1024 } });
  await page.setContent(`<!doctype html><style>
    @font-face { font-family: Bricolage; src: url(data:font/woff2;base64,${font}); font-weight: 100 900; }
    html, body { margin: 0; width: 1024px; height: 1024px; background: #fff; }
    body { display: grid; place-items: center; }
    .mark { font-family: Bricolage; font-size: 520px; font-weight: 600;
      font-optical-sizing: auto; letter-spacing: -0.04em; line-height: 1; color: #0f1115; }
    .mark span { color: #6b7280; }
  </style><div class="mark">h<span>/</span>h</div>`);
  await page.evaluate(() => document.fonts.ready);
  if (!(await page.evaluate(() => document.fonts.check("600 520px Bricolage")))) {
    throw new Error("Bricolage failed to load.");
  }
  await mkdir(new URL("brand/", root), { recursive: true });
  // Size from the visible glyphs, not the font's line box. Keep only 3% side
  // padding so the wide h/h mark remains legible at browser-tab sizes.
  const png = await sharp(await page.screenshot())
    .trim({ background: "#ffffff", threshold: 8 })
    .resize(960, 960, { fit: "contain", background: "#ffffff" })
    .extend({ top: 32, bottom: 32, left: 32, right: 32, background: "#ffffff" })
    .png()
    .toBuffer();
  await writeFile(new URL("brand/highlanderhub-icon.png", root), png);
  for (const [name, size] of [["icon-192.png", 192], ["icon-512.png", 512], ["apple-touch-icon.png", 180]]) {
    await sharp(png).resize(size, size).png().toFile(fileURLToPath(new URL(name, root)));
  }

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
  console.log("Rendered h/h thumbnail, app icons, and favicon.");
} finally {
  await browser.close();
}
