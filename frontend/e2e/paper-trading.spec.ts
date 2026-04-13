import { test, expect } from '@playwright/test';

test.describe('Paper Trading', () => {
  test('page loads with portfolio summary', async ({ page }) => {
    await page.goto('/dashboard/paper-trading');
    await expect(page.locator('text=Paper Trading')).toBeVisible();
  });

  test('order form is present', async ({ page }) => {
    await page.goto('/dashboard/paper-trading');
    await expect(page.locator('select, input[type="number"]')).toBeVisible();
  });
});
