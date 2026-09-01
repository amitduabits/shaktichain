import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const getHealthMock = vi.fn();
const loginMock = vi.fn();
const registerMock = vi.fn();
const demoLoginMock = vi.fn();
const getCurrentUserMock = vi.fn();

vi.mock('../../providers/Web3Provider', () => ({
  Web3Provider: ({ children }) => <>{children}</>,
}));

vi.mock('../../components/Dashboard', () => ({
  default: () => <div data-testid="dashboard-screen">Dashboard Mock</div>,
}));

vi.mock('../../components/web3', () => ({
  ConnectWallet: () => <div data-testid="connect-wallet">Connect Wallet Mock</div>,
  TransactionStatus: () => null,
}));

vi.mock('../../services/api', () => ({
  getHealth: getHealthMock,
  login: loginMock,
  register: registerMock,
  demoLogin: demoLoginMock,
  getCurrentUser: getCurrentUserMock,
}));

describe('App demo login flow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.history.replaceState({}, '', '/login');
    getHealthMock.mockResolvedValue({ status: 'healthy' });
    demoLoginMock.mockResolvedValue({ access_token: 'demo-token' });
    getCurrentUserMock.mockResolvedValue({
      id: 'demo-user',
      email: 'demo@v2g.local',
      role: 'user',
      created_at: '2026-01-01T00:00:00Z',
    });
  });

  it('authenticates with Enter Demo and routes to dashboard', async () => {
    const user = userEvent.setup();
    const { default: App } = await import('../../App');
    render(<App />);

    await user.click(screen.getByRole('button', { name: 'Enter Demo' }));

    await waitFor(() => {
      expect(screen.getByTestId('dashboard-screen')).toBeInTheDocument();
    });

    expect(demoLoginMock).toHaveBeenCalledTimes(1);
    expect(getCurrentUserMock).toHaveBeenCalled();
    expect(window.location.pathname).toBe('/dashboard');
  });
});
