import { test, expect } from '@playwright/test';

const LIVE = process.env.LIVE_QA === '1';

test.describe('Live Pages visitor path', () => {
  test.skip(!LIVE, 'Set LIVE_QA=1 to hit the public GitHub Pages URL');

  test.use({
    baseURL: 'https://amitduabits.github.io/shaktichain/demo/',
  });

  async function registerOnDemo(page, email, password) {
    await page.goto('https://amitduabits.github.io/shaktichain/demo/#/register');
    await expect(page.getByRole('heading', { name: /register/i })).toBeVisible({ timeout: 15000 });
    await page.getByLabel(/email/i).fill(email);
    await page.getByLabel(/^password$/i).fill(password);
    await page.getByRole('button', { name: /^register$/i }).click();
    await expect(page.getByTestId('role-home')).toBeVisible({
      timeout: 15000,
    });
  }

  test('brochure, register, trade, logout, login, wrong password, Enter Demo', async ({ page }) => {
    const email = `qa+${Date.now()}@v2g.local`;
    const password = 'testpass1';

    await page.goto('https://amitduabits.github.io/shaktichain/');
    await expect(page.getByRole('heading', { name: /shakti-chain/i })).toBeVisible();
    await page.getByRole('link', { name: /open the live demo/i }).click();
    await expect(page).toHaveURL(/\/shaktichain\/demo\//);
    await expect(page).toHaveTitle(/Shakti-Chain V2G Demo/);

    await page.getByRole('link', { name: /register/i }).click();
    await expect(page).toHaveURL(/\/shaktichain\/demo\//);
    await expect(page).not.toHaveURL(/github\.io\/register/);
    await expect(page.getByRole('heading', { name: /register/i })).toBeVisible();

    await page.getByLabel(/email/i).fill(email);
    await page.getByLabel(/^password$/i).fill(password);
    await page.getByRole('button', { name: /^register$/i }).click();

    await expect(page.getByTestId('role-home')).toBeVisible({
      timeout: 15000,
    });
    await expect(page.getByTestId('sim-disclaimer')).toBeVisible();
    await expect(page.getByText(email)).toBeVisible();
    await page.getByTestId('home-cta').click();
    await expect(page.getByRole('heading', { name: /place order/i })).toBeVisible();

    const qty = page.locator('.bid-form input[type="number"]').nth(0);
    const price = page.locator('.bid-form input[type="number"]').nth(1);
    await page.getByRole('button', { name: /buy \(bid\)/i }).click();
    await qty.fill('5');
    await price.fill('4.85');
    await page.getByRole('button', { name: /place buy order/i }).click();

    await page.getByRole('button', { name: /sell \(ask\)/i }).click();
    await page.locator('.bid-form input[type="number"]').nth(0).fill('3');
    await page.locator('.bid-form input[type="number"]').nth(1).fill('5.10');
    await page.getByRole('button', { name: /place sell order/i }).click();

    const reset = page.getByRole('button', { name: 'Reset Demo Data' });
    await expect(reset).toBeVisible({ timeout: 10000 });
    await reset.click();
    await expect(page.getByTestId('sim-disclaimer')).toBeVisible();

    await page.getByRole('button', { name: /logout/i }).click();
    await expect(page.getByRole('heading', { name: /login/i })).toBeVisible();

    await page.getByLabel(/email/i).fill(email);
    await page.getByLabel(/^password$/i).fill(password);
    await page.getByRole('button', { name: /^login$/i }).click();
    await expect(page.getByTestId('role-home')).toBeVisible({
      timeout: 15000,
    });
    await expect(page.getByText(email)).toBeVisible();

    await page.getByRole('button', { name: /logout/i }).click();
    await expect(page.getByRole('heading', { name: /login/i })).toBeVisible();
    await page.getByLabel(/email/i).fill(email);
    await page.getByLabel(/^password$/i).fill('wrongpass');
    await page.getByRole('button', { name: /^login$/i }).click();
    await expect(page.getByTestId('auth-error')).toBeVisible();
    await expect(page.getByRole('heading', { name: /login/i })).toBeVisible();

    await page.getByRole('button', { name: 'Enter Demo' }).click();
    await expect(page.getByTestId('role-home')).toBeVisible({
      timeout: 15000,
    });
    await expect(page.getByText('demo@v2g.local')).toBeVisible();

    await page.getByTestId('role-switcher').selectOption('fleet');
    await expect(page.getByTestId('role-home')).toHaveAttribute('data-role', 'fleet');
    await expect(page.getByText('demo@v2g.local')).toBeVisible();
    await page.getByTestId('role-switcher').selectOption('discom');
    await expect(page.getByTestId('role-home')).toHaveAttribute('data-role', 'discom');
    await expect(page.getByTestId('home-cta')).toHaveCount(0);
    await page.getByTestId('role-switcher').selectOption('cpo');
    await expect(page.getByTestId('role-home')).toHaveAttribute('data-role', 'cpo');
    await page.getByTestId('role-switcher').selectOption('aggregator');
    await expect(page.getByTestId('role-home')).toHaveAttribute('data-role', 'aggregator');
  });

  test('register on mobile 375x667', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    const email = `qa+m${Date.now()}@v2g.local`;
    await registerOnDemo(page, email, 'testpass1');
    await expect(page.getByTestId('sim-disclaimer')).toBeVisible();
    await expect(page.getByText(email)).toBeVisible();
    await expect(page.getByTestId('home-cta')).toBeVisible();
  });
});
