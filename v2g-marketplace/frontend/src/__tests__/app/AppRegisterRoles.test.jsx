import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { PUBLIC_ROLES, ROLE_LABELS } from '../../auth/roles';

vi.mock('../../providers/Web3Provider', () => ({
  Web3Provider: ({ children }) => <>{children}</>,
}));

vi.mock('../../components/web3', () => ({
  ConnectWallet: () => null,
  TransactionStatus: () => null,
  BidForm: () => <div>BidForm</div>,
  AuctionRoundViewer: () => null,
  DemoActivityPanel: () => null,
  TokenBalance: () => null,
  StakingPanel: () => null,
}));

vi.mock('../../services/api', () => ({
  getHealth: vi.fn().mockRejectedValue(new Error('offline')),
  login: vi.fn(),
  register: vi.fn(),
  demoLogin: vi.fn(),
  getCurrentUser: vi.fn(),
}));

describe('App register roles', () => {
  beforeEach(() => {
    vi.stubEnv('VITE_DEMO_ONLY', 'true');
    window.history.replaceState({}, '', '/login');
    localStorage.clear();
    vi.resetModules();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('omits admin from the role select', async () => {
    const { default: App } = await import('../../App');
    render(<App />);
    await userEvent.click(screen.getByRole('link', { name: /register/i }));
    const options = screen.getAllByRole('option').map((node) => node.textContent);
    expect(options).not.toContain('Admin');
    expect(options).toEqual(PUBLIC_ROLES.map((id) => ROLE_LABELS[id]));
  });

  it.each(PUBLIC_ROLES)('registers as %s and sets data-role', async (role) => {
    const user = userEvent.setup();
    const email = `${role}+${Date.now()}@v2g.local`;
    const { default: App } = await import('../../App');
    render(<App />);
    await user.click(screen.getByRole('link', { name: /register/i }));
    await user.type(screen.getByLabelText(/email \(user id\)/i), email);
    await user.selectOptions(screen.getByLabelText(/^role$/i), role);
    await user.type(screen.getByLabelText(/^password$/i), 'testpass1');
    await user.click(screen.getByRole('button', { name: /^register$/i }));
    await waitFor(() => {
      expect(screen.getByTestId('role-home')).toHaveAttribute('data-role', role);
    });
  });
});
