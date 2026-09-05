import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RoleHome } from '../../pages/RoleHome';
import { RoleAssets } from '../../pages/RoleAssets';
import { createInitialDemoLedger } from '../../demo/ledger';

vi.mock('../../context/DemoLedgerContext', () => ({
  useDemoLedger: () => ({
    ledger: createInitialDemoLedger(0),
    addVehicle: vi.fn(),
    removeVehicle: vi.fn(),
    updateVehicle: vi.fn(),
    setPortfolio: vi.fn(),
  }),
}));

describe('DISCOM home', () => {
  it('has feeders and no order ticket', () => {
    render(<RoleHome role="discom" onNavigate={() => {}} />);
    expect(screen.getByTestId('role-home')).toHaveAttribute('data-role', 'discom');
    expect(screen.queryByTestId('home-cta')).not.toBeInTheDocument();
    expect(screen.queryByText(/place order/i)).not.toBeInTheDocument();
    render(<RoleAssets role="discom" />);
    expect(screen.getByText('DL-F12')).toBeInTheDocument();
  });
});
