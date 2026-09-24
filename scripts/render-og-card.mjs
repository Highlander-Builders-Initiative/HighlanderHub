#!/usr/bin/env node
/**
 * Render public/og-card.jpg, the 1200x630 link-preview card: the wordmark and
 * the home headline over the campus skyline, composed like the hero.
 * Run via: node scripts/render-og-card.mjs (needs network for Google Fonts).
 *
 * JPEG, not PNG: the PNG is ~350 KB, and WhatsApp drops previews over ~300 KB.
 */
import { chromium } from "@playwright/test";
import { fileURLToPath } from "node:url";

const root = new URL("..", import.meta.url);
const skyline = new URL("src/components/home/campus-skyline-golden.webp", root).href;
const out = fileURLToPath(new URL("public/og-card.jpg", root));

// The sky seam matches .skyline-hero in globals.css: white into the art's
// sampled sky colour (#fff9f2), arriving where the picture begins.
const html = `<!doctype html>
<html>
<head>
<meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600&display=block" rel="stylesheet">
<style>
  html, body { margin: 0; }
  .card {
    position: relative;
    width: 1200px;
    height: 630px;
    overflow: hidden;
    background: linear-gradient(to bottom, #ffffff 0, #fff9f2 190px);
    font-family: "Bricolage Grotesque", ui-sans-serif, system-ui, sans-serif;
    color: #0f1115;
  }
  .art { position: absolute; left: -40px; bottom: 0; width: 1280px; display: block; }
  .copy { position: absolute; left: 72px; top: 60px; }
  .wordmark { font-size: 30px; font-weight: 600; letter-spacing: -0.04em; line-height: 1; }
  .wordmark span { color: #6b7280; }
  h1 { margin: 36px 0 0; font-size: 80px; font-weight: 600; line-height: 1.03; letter-spacing: -0.035em; }
</style>
</head>
<body>
  <div class="card">
    <img class="art" src="${skyline}" alt="">
    <div class="copy">
      <div class="wordmark">highlander<span>/</span>hub</div>
      <h1>Every UCR event,<br>one page.</h1>
    </div>
  </div>
</body>
</html>`;

const browser = await chromium.launch();
const page = await browser.newPage({
  viewport: { width: 1200, height: 630 },
  deviceScaleFactor: 1,
});
// A file: base URL so the page may load the local skyline art.
await page.goto(new URL("public/", root).href);
await page.setContent(html, { waitUntil: "networkidle" });
await page.evaluate(() => document.fonts.ready);
const loaded = await page.evaluate(() =>
  [...document.fonts].some(
    (font) => font.family.includes("Bricolage") && font.status === "loaded"
  )
);
if (!loaded) {
  await browser.close();
  throw new Error("Bricolage Grotesque did not load; check the network.");
}
await page
  .locator(".card")
  .screenshot({ path: out, type: "jpeg", quality: 88 });
await browser.close();
console.log(`Wrote ${out}`);
