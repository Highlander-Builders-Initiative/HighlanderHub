import { expect, test } from '@playwright/test';
import { E2E_FIXTURE_EVENT } from '../../src/lib/events/fixtures';
import { waitForEventsBrowserHydration } from './events-browser-helpers';

test('calendar failure stays unknown and retries the same month', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  let attempts = 0;
  let recover = false;
  await page.route('**/api/events/calendar**', async route => {
    attempts += 1;
    if (!recover) await route.fulfill({ status: 500, json: { error: 'offline' } });
    else await route.fulfill({ json: { events: [{ ...E2E_FIXTURE_EVENT,
      startsAt: '2026-06-01T18:30:00-07:00' }] } });
  });
  await page.goto('/events');
  await waitForEventsBrowserHydration(page);
  const rail = page.getByRole('complementary', { name: 'Calendar and time filter' });
  await rail.getByRole('button', { name: 'Next month' }).click();
  await expect(rail.getByRole('alert')).toContainText('Couldn’t load this month');
  await expect(rail.getByRole('button', { name: 'Jump to 2026-06-01, event count unavailable' })).toBeVisible();
  const failedAttempts = attempts;
  recover = true;
  await rail.getByRole('button', { name: 'Retry calendar' }).click();
  await expect(rail.getByRole('button', { name: 'Jump to 2026-06-01, 1 event', exact: true })).toBeVisible();
  await expect(rail.getByRole('alert')).toHaveCount(0);
  expect(attempts).toBe(failedAttempts + 1);
});

test('superseded calendar responses cannot replace the current month', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  let releaseJune!: () => void;
  const juneGate = new Promise<void>(resolve => { releaseJune = resolve; });
  let juneStarted = false;
  await page.route('**/api/events/calendar**', async route => {
    const start = new URL(route.request().url()).searchParams.get('start');
    if (start === '2026-05-31') {
      juneStarted = true;
      await juneGate;
      await route.fulfill({ json: { events: [] } });
    } else await route.fulfill({ json: { events: [{ ...E2E_FIXTURE_EVENT,
      startsAt: '2026-07-01T18:30:00-07:00' }] } });
  });
  await page.goto('/events');
  await waitForEventsBrowserHydration(page);
  const rail = page.getByRole('complementary', { name: 'Calendar and time filter' });
  await rail.getByRole('button', { name: 'Next month' }).click();
  await expect.poll(() => juneStarted).toBe(true);
  await rail.getByRole('button', { name: 'Next month' }).click();
  const july = rail.getByRole('button', { name: 'Jump to 2026-07-01, 1 event', exact: true });
  await expect(july).toBeVisible();
  const response = page.waitForResponse(url => url.url().includes('start=2026-05-31'));
  releaseJune();
  await response;
  await expect(july).toBeVisible();
});

for (const failure of ['denied', 'quota']) {
  test(`browse and detail navigation survive ${failure} storage`, async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.addInitScript(mode => {
      if (mode === 'denied') Object.defineProperty(window, 'sessionStorage', {
        get() { throw new DOMException('denied', 'SecurityError'); },
      });
      else Storage.prototype.setItem = () => { throw new DOMException('full', 'QuotaExceededError'); };
    }, failure);
    await page.goto('/events');
    await waitForEventsBrowserHydration(page);
    await page.getByRole('link', { name: /E2E Test: Highlander Hub Showcase/i }).click();
    await expect(page).toHaveURL(/\/events\/.+/);
    await page.goBack();
    await expect(page).toHaveURL(/\/events$/);
    await expect(page.locator('[data-event-id]').first()).toBeVisible();
    expect(errors).toEqual([]);
  });
}
