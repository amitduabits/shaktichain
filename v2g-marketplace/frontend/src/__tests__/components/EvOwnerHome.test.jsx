import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RoleHome } from '../../pages/RoleHome';
import { createInitialDemoLedger } from '../../demo/ledger';

vi.mock('../../context/DemoLedgerContext', () => ({
  useDemoLedger: () => ({ ledger: createInitialDemoLedger(0) }),
}));

describe('EV owner home', () => {
  it('shows Place order and no city simulation', () => {
    render(<RoleHome role="ev_owner" onNavigate={() => {}} />);
    expect(screen.getByTestId('role-home')).toHaveAttribute('data-role', 'ev_owner');
    expect(screen.getByTestId('home-cta')).toHaveTextContent('Place order');
    expect(screen.queryByRole('button', { name: /run simulation/i })).not.toBeInTheDocument();
    expect(screen.getByText(/SOC/i)).toBeInTheDocument();
  });
});
