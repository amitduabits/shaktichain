/**
 * E2E tests for authentication flows
 */

import { test, expect } from '@playwright/test';

test.describe('Authentication', () => {
  test.describe('Login Page', () => {
    test('shows login form', async ({ page }) => {
      await page.goto('/login');

      await expect(page.getByRole('heading', { name: /login/i })).toBeVisible();
      await expect(page.getByLabel(/email/i)).toBeVisible();
      await expect(page.getByLabel(/password/i)).toBeVisible();
      await expect(page.getByRole('button', { name: /login/i })).toBeVisible();
    });

    test('shows link to register page', async ({ page }) => {
      await page.goto('/login');

      const registerLink = page.getByRole('link', { name: /register|sign up/i });
      await expect(registerLink).toBeVisible();
    });

    test('validates required fields', async ({ page }) => {
      await page.goto('/login');

      // Try to submit empty form
      await page.getByRole('button', { name: /login/i }).click();

      // Should show validation errors or stay on page
      await expect(page).toHaveURL(/login/);
    });

    test('validates email format', async ({ page }) => {
      await page.goto('/login');

      await page.getByLabel(/email/i).fill('invalid-email');
      await page.getByLabel(/password/i).fill('password123');
      await page.getByRole('button', { name: /login/i }).click();

      // Should show error or stay on login page
      await expect(page).toHaveURL(/login/);
    });

    test('shows error on invalid credentials', async ({ page }) => {
      await page.goto('/login');

      await page.getByLabel(/email/i).fill('nonexistent@example.com');
      await page.getByLabel(/password/i).fill('wrongpassword');
      await page.getByRole('button', { name: /login/i }).click();

      // Should show error message
      await expect(page.getByText(/invalid|error|incorrect/i)).toBeVisible({ timeout: 5000 });
    });

    test('successful login redirects to dashboard', async ({ page }) => {
      // First register a user
      await page.goto('/register');
      await page.getByLabel(/email/i).fill('logintest@example.com');
      await page.getByLabel(/password/i).fill('password123');
      await page.getByRole('button', { name: /register|sign up/i }).click();

      // Wait for registration to complete
      await page.waitForURL(/dashboard|\/$/);

      // Logout
      const logoutBtn = page.getByRole('button', { name: /logout/i });
      if (await logoutBtn.isVisible()) {
        await logoutBtn.click();
      }

      // Now login
      await page.goto('/login');
      await page.getByLabel(/email/i).fill('logintest@example.com');
      await page.getByLabel(/password/i).fill('password123');
      await page.getByRole('button', { name: /login/i }).click();

      // Should redirect to dashboard
      await expect(page).toHaveURL(/dashboard|\/$/);
    });
  });

  test.describe('Registration Page', () => {
    test('shows registration form', async ({ page }) => {
      await page.goto('/register');

      await expect(page.getByRole('heading', { name: /register|sign up/i })).toBeVisible();
      await expect(page.getByLabel(/email/i)).toBeVisible();
      await expect(page.getByLabel(/password/i)).toBeVisible();
      await expect(page.getByRole('button', { name: /register|sign up/i })).toBeVisible();
    });

    test('validates password length', async ({ page }) => {
      await page.goto('/register');

      await page.getByLabel(/email/i).fill('newuser@example.com');
      await page.getByLabel(/password/i).fill('short');
      await page.getByRole('button', { name: /register|sign up/i }).click();

      // Should show error or stay on register page
      await expect(page).toHaveURL(/register/);
    });

    test('successful registration redirects to dashboard', async ({ page }) => {
      const uniqueEmail = `test${Date.now()}@example.com`;

      await page.goto('/register');
      await page.getByLabel(/email/i).fill(uniqueEmail);
      await page.getByLabel(/password/i).fill('password123');
      await page.getByRole('button', { name: /register|sign up/i }).click();

      // Should redirect to dashboard
      await expect(page).toHaveURL(/dashboard|\/$/);
    });

    test('shows error for duplicate email', async ({ page }) => {
      const email = `duplicate${Date.now()}@example.com`;

      // First registration
      await page.goto('/register');
      await page.getByLabel(/email/i).fill(email);
      await page.getByLabel(/password/i).fill('password123');
      await page.getByRole('button', { name: /register|sign up/i }).click();

      await page.waitForURL(/dashboard|\/$/);

      // Logout and try to register again
      const logoutBtn = page.getByRole('button', { name: /logout/i });
      if (await logoutBtn.isVisible()) {
        await logoutBtn.click();
      }

      await page.goto('/register');
      await page.getByLabel(/email/i).fill(email);
      await page.getByLabel(/password/i).fill('password123');
      await page.getByRole('button', { name: /register|sign up/i }).click();

      // Should show duplicate error
      await expect(page.getByText(/already|exist|registered/i)).toBeVisible({ timeout: 5000 });
    });
  });

  test.describe('Protected Routes', () => {
    test('redirects to login when not authenticated', async ({ page }) => {
      // Clear any stored auth
      await page.goto('/');
      await page.evaluate(() => localStorage.clear());

      // Try to access protected route
      await page.goto('/dashboard');

      // Should redirect to login
      await expect(page).toHaveURL(/login/);
    });

    test('maintains authentication across page reloads', async ({ page }) => {
      const email = `persist${Date.now()}@example.com`;

      // Register and login
      await page.goto('/register');
      await page.getByLabel(/email/i).fill(email);
      await page.getByLabel(/password/i).fill('password123');
      await page.getByRole('button', { name: /register|sign up/i }).click();

      await page.waitForURL(/dashboard|\/$/);

      // Reload page
      await page.reload();

      // Should still be on dashboard (not redirected to login)
      await expect(page).not.toHaveURL(/login/);
    });
  });

  test.describe('Logout', () => {
    test('logout clears authentication', async ({ page }) => {
      const email = `logout${Date.now()}@example.com`;

      // Register
      await page.goto('/register');
      await page.getByLabel(/email/i).fill(email);
      await page.getByLabel(/password/i).fill('password123');
      await page.getByRole('button', { name: /register|sign up/i }).click();

      await page.waitForURL(/dashboard|\/$/);

      // Find and click logout
      const logoutBtn = page.getByRole('button', { name: /logout/i });
      if (await logoutBtn.isVisible()) {
        await logoutBtn.click();

        // Should be redirected to login
        await expect(page).toHaveURL(/login/);

        // Token should be cleared
        const token = await page.evaluate(() => localStorage.getItem('auth_token'));
        expect(token).toBeNull();
      }
    });
  });
});
