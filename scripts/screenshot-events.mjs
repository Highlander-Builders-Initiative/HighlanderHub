import { chromium } from "@playwright/test";
import { mkdir } from "node:fs/promises";

const BASE = process.env.SCREENSHOT_BASE ?? "http://127.0.0.1:3007";
const OUT = new URL("../test-results/events-screens/", import.meta.url);

await mkdir(OUT, { recursive: true });

const browser = await chromium.launch();

const viewports = [
  { name: "desktop-1440", width: 1440, height: 900 },
  { name: "desktop-1024", width: 1024, height: 800 },
  { name: "mobile-375", width: 375, height: 720 },
];

for (const vp of viewports) {
  const context = await browser.newContext({
    viewport: { width: vp.width, height: vp.height },
    deviceScaleFactor: 2,
  });
  const page = await context.newPage();
  await page.goto(`${BASE}/events`, { waitUntil: "networkidle" });
  // Wait a tick for fonts and intersection observers
  await page.waitForTimeout(400);

  // Top of page
  await page.screenshot({
    path: new URL(`./${vp.name}-top.png`, OUT).pathname,
    fullPage: false,
  });

  // Scrolled (shows day headers + scroll-spy effect on calendar)
  await page.evaluate(() => window.scrollTo({ top: 700, behavior: "instant" }));
  await page.waitForTimeout(300);
  await page.screenshot({
    path: new URL(`./${vp.name}-scrolled.png`, OUT).pathname,
    fullPage: false,
  });

  if (vp.name === "mobile-375") {
    // Open the mobile filter sheet
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
    await page.waitForTimeout(200);
    await page.getByRole("button", { name: /^Filter/ }).click();
    await page.waitForTimeout(350);
    await page.screenshot({
      path: new URL(`./${vp.name}-sheet.png`, OUT).pathname,
      fullPage: false,
    });
  }

  await context.close();
  console.log(`captured ${vp.name}`);
}

await browser.close();
console.log("done");
