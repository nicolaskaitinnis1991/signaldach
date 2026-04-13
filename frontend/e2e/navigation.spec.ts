import { test, expect } from '@playwright/test';

test.describe('Navigation', () => {
  test('landing page loads', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/SignalDACH/);
  });

  test('dashboard loads', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.locator('text=SignalDACH')).toBeVisible();
  });

  test('all dashboard routes accessible', async ({ page }) => {
    const routes = [
      '/dashboard/market',
      '/dashboard/signals',
      '/dashboard/fund',
      '/dashboard/chat',
      '/dashboard/paper-trading',
      '/dashboard/reports',
      '/dashboard/settings',
    ];
    for (const route of routes) {
      await page.goto(route);
      // Should not show error boundary
      await expect(page.locator('text=Something went wrong')).not.toBeVisible();
    }
  });

  test('sidebar navigation works', async ({ page }) => {
    await page.goto('/dashboard');
    // Click on Market link
    await page.click('a[href="/dashboard/market"]');
    await expect(page).toHaveURL(/\/dashboard\/market/);
  });

  test('404 page shows for unknown routes', async ({ page }) => {
    await page.goto('/dashboard/nonexistent');
    await expect(page.locator('text=404')).toBeVisible();
  });
});
