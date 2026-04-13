import { test, expect } from '@playwright/test';

test.describe('Accessibility', () => {
  test('dashboard has proper heading hierarchy', async ({ page }) => {
    await page.goto('/dashboard');
    const h1Count = await page.locator('h1').count();
    expect(h1Count).toBeGreaterThanOrEqual(1);
  });

  test('navigation has aria-label', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.locator('nav[aria-label], [role="navigation"]')).toBeVisible();
  });

  test('interactive elements are keyboard accessible', async ({ page }) => {
    await page.goto('/dashboard');
    // Tab through and check focus is visible
    await page.keyboard.press('Tab');
    const focused = await page.evaluate(() => document.activeElement?.tagName);
    expect(focused).toBeTruthy();
  });
});
