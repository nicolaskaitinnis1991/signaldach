import { test, expect } from '@playwright/test';

test.describe('Theme', () => {
  test('dark mode is default', async ({ page }) => {
    await page.goto('/dashboard');
    const html = page.locator('html');
    await expect(html).toHaveClass(/dark/);
  });

  test('theme toggle exists', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.locator('[aria-label*="theme"], [aria-label*="Theme"], button:has(svg)')).toBeVisible();
  });
});
