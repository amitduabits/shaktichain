import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RoleAssets } from '../../pages/RoleAssets';
import { createInitialDemoLedger, MIN_VEHICLES } from '../../demo/ledger';

const ledger = createInitialDemoLedger(0);
const removeVehicle = vi.fn(() => ({ success: false, error: 'Keep at least one vehicle.' }));
const addVehicle = vi.fn(() => ({ success: true }));

vi.mock('../../context/DemoLedgerContext', () => ({
  useDemoLedger: () => ({
    ledger,
    addVehicle,
    removeVehicle,
    updateVehicle: vi.fn(),
    setPortfolio: vi.fn(),
  }),
}));

describe('Fleet assets', () => {
  it('lists seeded vehicles', () => {
    render(<RoleAssets role="fleet" />);
    expect(screen.getAllByRole('row').length).toBeGreaterThan(5);
    expect(ledger.vehicles.length).toBeGreaterThanOrEqual(5);
  });

  it('surfaces min-1 remove error', async () => {
    render(<RoleAssets role="fleet" />);
    const buttons = screen.getAllByRole('button', { name: /remove/i });
    await userEvent.click(buttons[0]);
    expect(removeVehicle).toHaveBeenCalled();
    expect(MIN_VEHICLES).toBe(1);
  });
});
