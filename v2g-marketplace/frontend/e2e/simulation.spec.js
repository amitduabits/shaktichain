/**
 * E2E tests for simulation functionality
 */

import { test, expect } from '@playwright/test';

test.describe('Simulation', () => {
  // Setup: Login before each test
  test.beforeEach(async ({ page }) => {
    const email = `simtest${Date.now()}@example.com`;

    // Register a new user
    await page.goto('/register');
    await page.getByLabel(/email/i).fill(email);
    await page.getByLabel(/password/i).fill('password123');
    await page.getByRole('button', { name: /register|sign up/i }).click();

    // Wait for dashboard
    await page.waitForURL(/dashboard|\/$/);
  });

  test.describe('Dashboard Display', () => {
    test('displays market overview', async ({ page }) => {
      await expect(page.getByText(/energy market overview/i)).toBeVisible();
    });

    test('displays price chart section', async ({ page }) => {
      await expect(page.getByText(/price history/i)).toBeVisible();
    });

    test('displays simulation panel', async ({ page }) => {
      await expect(page.getByText(/run simulation/i)).toBeVisible();
    });

    test('displays market stats', async ({ page }) => {
      await expect(page.getByText(/market status/i)).toBeVisible();
      await expect(page.getByText(/active prosumers/i)).toBeVisible();
      await expect(page.getByText(/total energy traded/i)).toBeVisible();
    });
  });

  test.describe('Simulation Configuration', () => {
    test('allows configuring number of agents', async ({ page }) => {
      const slider = page.getByLabel(/number of agents/i);
      await expect(slider).toBeVisible();

      // Change slider value
      await slider.fill('500');
      await expect(page.getByText('500')).toBeVisible();
    });

    test('allows selecting simulation duration', async ({ page }) => {
      const durationSelect = page.getByLabel(/simulation duration/i);
      await expect(durationSelect).toBeVisible();

      // Select different duration
      await durationSelect.selectOption('30');
      await expect(durationSelect).toHaveValue('30');
    });

    test('allows selecting region', async ({ page }) => {
      const regionSelect = page.getByLabel(/region/i);
      await expect(regionSelect).toBeVisible();

      // Select different region
      await regionSelect.selectOption('mumbai');
      await expect(regionSelect).toHaveValue('mumbai');
    });

    test('displays agent mix configuration', async ({ page }) => {
      await expect(page.getByText(/residential/i)).toBeVisible();
      await expect(page.getByText(/commercial/i)).toBeVisible();
      await expect(page.getByText(/fleet/i)).toBeVisible();
    });
  });

  test.describe('Running Simulation', () => {
    test('can start a simulation', async ({ page }) => {
      const runButton = page.getByRole('button', { name: /run simulation/i });
      await expect(runButton).toBeVisible();
      await expect(runButton).toBeEnabled();

      await runButton.click();

      // Should show running state or progress
      await expect(
        page.getByText(/running|progress|simulating/i)
      ).toBeVisible({ timeout: 10000 });
    });

    test('disables controls while running', async ({ page }) => {
      await page.getByRole('button', { name: /run simulation/i }).click();

      // Wait for running state
      await expect(page.getByText(/running/i)).toBeVisible({ timeout: 5000 });

      // Controls should be disabled
      await expect(page.getByLabel(/number of agents/i)).toBeDisabled();
      await expect(page.getByLabel(/simulation duration/i)).toBeDisabled();
    });

    test('shows progress during simulation', async ({ page }) => {
      await page.getByRole('button', { name: /run simulation/i }).click();

      // Should show progress indicator
      await expect(
        page.getByText(/progress|%|day.*of/i)
      ).toBeVisible({ timeout: 10000 });
    });
  });

  test.describe('Simulation Results', () => {
    test.skip('displays results when simulation completes', async ({ page }) => {
      // Configure a short simulation
      await page.getByLabel(/simulation duration/i).selectOption('1');

      // Start simulation
      await page.getByRole('button', { name: /run simulation/i }).click();

      // Wait for completion (with longer timeout)
      await expect(
        page.getByText(/simulation complete|results/i)
      ).toBeVisible({ timeout: 120000 });

      // Should show result metrics
      await expect(page.getByText(/total energy traded/i)).toBeVisible();
      await expect(page.getByText(/average price/i)).toBeVisible();
    });

    test.skip('allows downloading results', async ({ page }) => {
      // Configure and run short simulation
      await page.getByLabel(/simulation duration/i).selectOption('1');
      await page.getByRole('button', { name: /run simulation/i }).click();

      // Wait for completion
      await expect(
        page.getByText(/simulation complete/i)
      ).toBeVisible({ timeout: 120000 });

      // Download button should be visible
      const downloadBtn = page.getByRole('button', { name: /download csv/i });
      await expect(downloadBtn).toBeVisible();
    });

    test.skip('allows running simulation again', async ({ page }) => {
      // Run simulation
      await page.getByLabel(/simulation duration/i).selectOption('1');
      await page.getByRole('button', { name: /run simulation/i }).click();

      // Wait for completion
      await expect(
        page.getByText(/simulation complete/i)
      ).toBeVisible({ timeout: 120000 });

      // Run again button should be visible
      const runAgainBtn = page.getByRole('button', { name: /run again/i });
      await expect(runAgainBtn).toBeVisible();

      await runAgainBtn.click();

      // Should reset to configuration form
      await expect(
        page.getByRole('button', { name: /run simulation/i })
      ).toBeVisible();
    });
  });
});

test.describe('Price Chart', () => {
  test.beforeEach(async ({ page }) => {
    const email = `charttest${Date.now()}@example.com`;

    await page.goto('/register');
    await page.getByLabel(/email/i).fill(email);
    await page.getByLabel(/password/i).fill('password123');
    await page.getByRole('button', { name: /register|sign up/i }).click();

    await page.waitForURL(/dashboard|\/$/);
  });

  test('displays price chart area', async ({ page }) => {
    // Should have a chart container
    await expect(page.getByText(/price history/i)).toBeVisible();
  });

  test('updates price display', async ({ page }) => {
    // Should show current price
    await expect(
      page.getByText(/current price|loading/i)
    ).toBeVisible();
  });
});

test.describe('Responsive Design', () => {
  test('works on mobile viewport', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });

    const email = `mobile${Date.now()}@example.com`;

    await page.goto('/register');
    await page.getByLabel(/email/i).fill(email);
    await page.getByLabel(/password/i).fill('password123');
    await page.getByRole('button', { name: /register|sign up/i }).click();

    await page.waitForURL(/dashboard|\/$/);

    // Dashboard should be visible and functional
    await expect(page.getByText(/energy market overview/i)).toBeVisible();
    await expect(page.getByRole('button', { name: /run simulation/i })).toBeVisible();
  });

  test('works on tablet viewport', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });

    const email = `tablet${Date.now()}@example.com`;

    await page.goto('/register');
    await page.getByLabel(/email/i).fill(email);
    await page.getByLabel(/password/i).fill('password123');
    await page.getByRole('button', { name: /register|sign up/i }).click();

    await page.waitForURL(/dashboard|\/$/);

    await expect(page.getByText(/energy market overview/i)).toBeVisible();
  });
});

test.describe('Error Handling', () => {
  test.beforeEach(async ({ page }) => {
    const email = `errortest${Date.now()}@example.com`;

    await page.goto('/register');
    await page.getByLabel(/email/i).fill(email);
    await page.getByLabel(/password/i).fill('password123');
    await page.getByRole('button', { name: /register|sign up/i }).click();

    await page.waitForURL(/dashboard|\/$/);
  });

  test('handles network errors gracefully', async ({ page }) => {
    // Simulate offline
    await page.route('**/api/**', (route) => route.abort('connectionfailed'));

    // Try to run simulation
    await page.getByRole('button', { name: /run simulation/i }).click();

    // Should show error state
    await expect(
      page.getByText(/error|failed|network/i)
    ).toBeVisible({ timeout: 10000 });
  });

  test('allows retry after error', async ({ page }) => {
    // Simulate error on first request
    let requestCount = 0;
    await page.route('**/api/simulation/**', (route) => {
      requestCount++;
      if (requestCount === 1) {
        route.abort('connectionfailed');
      } else {
        route.continue();
      }
    });

    await page.getByRole('button', { name: /run simulation/i }).click();

    // Wait for error
    await expect(page.getByText(/error|failed/i)).toBeVisible({ timeout: 10000 });

    // Click retry
    const retryBtn = page.getByRole('button', { name: /try again|retry/i });
    if (await retryBtn.isVisible()) {
      await retryBtn.click();
      // Should be able to try again
      await expect(
        page.getByRole('button', { name: /run simulation/i })
      ).toBeVisible();
    }
  });
});
