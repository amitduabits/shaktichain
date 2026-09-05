import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

vi.mock('../../providers/Web3Provider', () => ({
  Web3Provider: ({ children }) => <>{children}</>,
}));

vi.mock('../../components/web3', () => ({
  ConnectWallet: () => null,
  TransactionStatus: () => null,
  BidForm: () => <div data-testid="bid-form">BidForm</div>,
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

async function registerRole(user, role, email) {
  await user.click(screen.getByRole('link', { name: /register/i }));
  await user.type(screen.getByLabelText(/email \(user id\)/i), email);
  await user.selectOptions(screen.getByLabelText(/^role$/i), role);
  await user.type(screen.getByLabelText(/^password$/i), 'testpass1');
  await user.click(screen.getByRole('button', { name: /^register$/i }));
  await waitFor(() => {
    expect(screen.getByTestId('role-home')).toBeInTheDocument();
  });
}

describe('Role guards', () => {
  beforeEach(() => {
    vi.stubEnv('VITE_DEMO_ONLY', 'true');
    window.history.replaceState({}, '', '/login');
    localStorage.clear();
    vi.resetModules();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('shows 403 when an EV owner opens admin', async () => {
    const user = userEvent.setup();
    const { default: App } = await import('../../App');
    render(<App />);
    await registerRole(user, 'ev_owner', `ev+${Date.now()}@v2g.local`);
    window.history.pushState({}, '', '/admin');
    window.dispatchEvent(new PopStateEvent('popstate'));
    await waitFor(() => {
      expect(screen.getByText(/this view is for admin accounts/i)).toBeInTheDocument();
    });
  });

  it('shows 403 when a DISCOM opens market', async () => {
    const user = userEvent.setup();
    const { default: App } = await import('../../App');
    render(<App />);
    await registerRole(user, 'discom', `discom+${Date.now()}@v2g.local`);
    expect(screen.queryByRole('button', { name: /place order/i })).not.toBeInTheDocument();
    window.history.pushState({}, '', '/market');
    window.dispatchEvent(new PopStateEvent('popstate'));
    await waitFor(() => {
      expect(screen.getByText(/this view is for trader accounts/i)).toBeInTheDocument();
    });
  });
});
