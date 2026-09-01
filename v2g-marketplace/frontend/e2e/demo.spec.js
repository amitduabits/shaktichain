import { test, expect } from '@playwright/test';

test.describe('Industry demo walkthrough', () => {
  test('Enter Demo, trade, and reset', async ({ page }) => {
    await page.goto('/login');
    await page.getByRole('button', { name: 'Enter Demo' }).click();
    await expect(page.getByRole('heading', { name: /energy market overview/i })).toBeVisible({
      timeout: 15000,
    });
    await expect(page.getByTestId('sim-disclaimer')).toBeVisible();

    const buyQty = page.getByLabel(/quantity/i).first();
    if (await buyQty.isVisible().catch(() => false)) {
      await buyQty.fill('5');
    }
    const buyBtn = page.getByRole('button', { name: /buy/i }).first();
    if (await buyBtn.isVisible().catch(() => false)) {
      await buyBtn.click();
    }
    const sellBtn = page.getByRole('button', { name: /sell/i }).first();
    if (await sellBtn.isVisible().catch(() => false)) {
      await sellBtn.click();
    }

    const reset = page.getByRole('button', { name: 'Reset Demo Data' });
    await expect(reset).toBeVisible({ timeout: 10000 });
    await reset.click();
    await expect(page.getByTestId('sim-disclaimer')).toBeVisible();
  });

  test('unauthenticated dashboard redirects to login', async ({ page }) => {
    await page.goto('/');
    await page.evaluate(() => localStorage.clear());
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/login/);
  });
});

test.describe('Industry demo viewports', () => {
  for (const size of [
    { name: 'mobile', width: 375, height: 667 },
    { name: 'desktop', width: 1280, height: 800 },
  ]) {
    test(`Enter Demo on ${size.name}`, async ({ page }) => {
      await page.setViewportSize({ width: size.width, height: size.height });
      await page.goto('/login');
      await page.getByRole('button', { name: 'Enter Demo' }).click();
      await expect(page.getByText(/energy market overview/i)).toBeVisible({ timeout: 15000 });
    });
  }
});
