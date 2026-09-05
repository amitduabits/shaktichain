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

test.describe('Local register and login (no FastAPI)', () => {
  test('register unique email, logout, login, wrong password, Enter Demo, stay under demo', async ({
    page,
  }) => {
    const email = `qa+${Date.now()}@v2g.local`;
    const password = 'testpass1';

    await gotoRoute(page, '/login');
    await expect(page.getByRole('heading', { name: /login/i })).toBeVisible();

    const registerLink = page.getByRole('link', { name: /register/i });
    await expect(registerLink).toBeVisible();
    await registerLink.click();

    await expect(page.getByRole('heading', { name: /register/i })).toBeVisible();
    const afterRegisterClick = page.url();
    if (afterRegisterClick.includes('github.io')) {
      expect(afterRegisterClick).toMatch(/\/shaktichain\/demo/);
      expect(afterRegisterClick).not.toMatch(/github\.io\/register(?:\?|$)/);
    } else {
      expect(afterRegisterClick).toMatch(/register/);
    }

    await page.getByLabel(/email/i).fill(email);
    await page.getByLabel(/^password$/i).fill(password);
    await page.getByRole('button', { name: /^register$/i }).click();

    await expect(page.getByTestId('role-home')).toBeVisible({
      timeout: 15000,
    });
    await expect(page.getByText(email)).toBeVisible();
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
    await expect(page.getByTestId('role-home')).toHaveCount(0);

    await page.getByRole('button', { name: 'Enter Demo' }).click();
    await expect(page.getByTestId('role-home')).toBeVisible({
      timeout: 15000,
    });
  });
});
