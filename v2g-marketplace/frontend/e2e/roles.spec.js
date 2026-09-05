import { test, expect } from '@playwright/test';

function usesHash(url) {
  return url.includes('#') || /\/demo\/?$/.test(url) || url.includes('/demo/');
}

async function gotoRoute(page, route) {
  await page.goto('/');
  const href = page.url();
  if (usesHash(href)) {
    await page.goto(`./#${route}`);
  } else {
    await page.goto(route);
  }
}

async function registerAs(page, role, email) {
  await gotoRoute(page, '/register');
  await page.getByLabel(/email/i).fill(email);
  await page.getByLabel(/^role$/i).selectOption(role);
  await page.getByLabel(/^password$/i).fill('testpass1');
  await page.getByRole('button', { name: /^register$/i }).click();
  await expect(page.getByTestId('role-home')).toBeVisible({ timeout: 15000 });
}

test.describe('Role homes', () => {
  test('Enter Demo lands on EV home and can place an order', async ({ page }) => {
    await gotoRoute(page, '/login');
    await page.getByRole('button', { name: 'Enter Demo' }).click();
    await expect(page.getByTestId('role-home')).toHaveAttribute('data-role', 'ev_owner');
    await page.getByTestId('home-cta').click();
    await expect(page.getByRole('heading', { name: /place order/i })).toBeVisible();
    await page.getByLabel(/quantity/i).fill('5');
    await page.getByLabel(/price/i).fill('4.85');
    await page.getByRole('button', { name: /place buy order/i }).click();
  });

  test('register fleet sees vehicles', async ({ page }) => {
    await registerAs(page, 'fleet', `fleet+${Date.now()}@v2g.local`);
    await expect(page.getByTestId('role-home')).toHaveAttribute('data-role', 'fleet');
    await page.getByRole('button', { name: /^assets$/i }).first().click();
    await expect(page.getByRole('cell', { name: 'Home EV' })).toBeVisible();
  });

  test('register discom has no place order', async ({ page }) => {
    await registerAs(page, 'discom', `discom+${Date.now()}@v2g.local`);
    await expect(page.getByTestId('role-home')).toHaveAttribute('data-role', 'discom');
    await expect(page.getByTestId('home-cta')).toHaveCount(0);
    await expect(page.getByRole('button', { name: /^market$/i })).toHaveCount(0);
    await page.getByRole('button', { name: /feeders/i }).first().click();
    await expect(page.getByText('DL-F12')).toBeVisible();
  });

  test('register cpo and aggregator', async ({ page }) => {
    await registerAs(page, 'cpo', `cpo+${Date.now()}@v2g.local`);
    await expect(page.getByTestId('role-home')).toHaveAttribute('data-role', 'cpo');
    await page.getByRole('button', { name: /logout/i }).click();
    await registerAs(page, 'aggregator', `agg+${Date.now()}@v2g.local`);
    await expect(page.getByTestId('role-home')).toHaveAttribute('data-role', 'aggregator');
  });

  test('ev owner cannot open admin', async ({ page }) => {
    await registerAs(page, 'ev_owner', `ev+${Date.now()}@v2g.local`);
    await gotoRoute(page, '/admin');
    await expect(page.getByText(/this view is for admin accounts/i)).toBeVisible();
  });
});
