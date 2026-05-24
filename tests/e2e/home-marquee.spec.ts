import { expect, test } from "@playwright/test";

test("home marquee wraps auto motion and manual drag", async ({ page }) => {
  await page.goto("/");

  const track = page.locator("[data-marquee-track]");
  await expect(track).toBeVisible();

  const firstX = await track.evaluate((el) => {
    const style = window.getComputedStyle(el);
    return new DOMMatrixReadOnly(style.transform).m41;
  });

  await page.waitForTimeout(700);

  const secondX = await track.evaluate((el) => {
    const style = window.getComputedStyle(el);
    return new DOMMatrixReadOnly(style.transform).m41;
  });
  expect(secondX).toBeLessThan(firstX);

  const box = await track.boundingBox();
  expect(box).not.toBeNull();
  if (!box) return;

  const y = box.y + Math.min(box.height / 2, 120);
  await page.mouse.move(box.x + 320, y);
  await page.mouse.down();
  await page.mouse.move(box.x - 700, y, { steps: 8 });
  await page.mouse.up();

  const draggedX = await track.evaluate((el) => {
    const width = Number(el.getAttribute("data-marquee-width"));
    const style = window.getComputedStyle(el);
    const x = new DOMMatrixReadOnly(style.transform).m41;
    return { width, x };
  });

  expect(draggedX.width).toBeGreaterThan(0);
  expect(draggedX.x).toBeLessThanOrEqual(0);
  expect(draggedX.x).toBeGreaterThan(-draggedX.width);

  await page.keyboard.down("Shift");
  await page.mouse.wheel(0, 900);
  await page.keyboard.up("Shift");

  const wheeledX = await track.evaluate((el) => {
    const width = Number(el.getAttribute("data-marquee-width"));
    const style = window.getComputedStyle(el);
    const x = new DOMMatrixReadOnly(style.transform).m41;
    return { width, x };
  });

  expect(wheeledX.x).not.toBe(draggedX.x);
  expect(wheeledX.x).toBeLessThanOrEqual(0);
  expect(wheeledX.x).toBeGreaterThan(-wheeledX.width);
});
