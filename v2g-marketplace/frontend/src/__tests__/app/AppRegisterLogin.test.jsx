import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
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

describe('App register/login local mode', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubEnv('VITE_DEMO_ONLY', 'true');
    window.history.replaceState({}, '', '/login');
    localStorage.clear();
    getHealthMock.mockRejectedValue(new Error('Network error'));
    vi.resetModules();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('registers with Email (user id) and password and lands on the dashboard', async () => {
    const user = userEvent.setup();
    const email = `qa+${Date.now()}@v2g.local`;
    const { default: App } = await import('../../App');
    render(<App />);

    await user.click(screen.getByRole('link', { name: /register/i }));
    expect(screen.getByRole('heading', { name: /register/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/email \(user id\)/i)).toBeInTheDocument();

    await user.type(screen.getByLabelText(/email \(user id\)/i), email);
    await user.type(screen.getByLabelText(/^password$/i), 'testpass1');
    await user.click(screen.getByRole('button', { name: /^register$/i }));

    await waitFor(() => {
      expect(screen.getByTestId('role-home')).toBeInTheDocument();
    });
    expect(screen.getByText(email)).toBeInTheDocument();
    expect(registerMock).not.toHaveBeenCalled();
    expect(screen.queryByTestId('connect-wallet')).not.toBeInTheDocument();
  });

  it('logs out and logs back in with the same pair', async () => {
    const user = userEvent.setup();
    const email = `qa+${Date.now()}@v2g.local`;
    const { default: App } = await import('../../App');
    render(<App />);

    await user.click(screen.getByRole('link', { name: /register/i }));
    await user.type(screen.getByLabelText(/email \(user id\)/i), email);
    await user.type(screen.getByLabelText(/^password$/i), 'testpass1');
    await user.click(screen.getByRole('button', { name: /^register$/i }));

    await waitFor(() => {
      expect(screen.getByTestId('role-home')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /logout/i }));
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /login/i })).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/email \(user id\)/i), email);
    await user.type(screen.getByLabelText(/^password$/i), 'testpass1');
    await user.click(screen.getByRole('button', { name: /^login$/i }));

    await waitFor(() => {
      expect(screen.getByTestId('role-home')).toBeInTheDocument();
    });
    expect(screen.getByText(email)).toBeInTheDocument();
    expect(loginMock).not.toHaveBeenCalled();
  });

  it('keeps the login screen and shows an error for a wrong password', async () => {
    const user = userEvent.setup();
    const email = `qa+${Date.now()}@v2g.local`;
    const { default: App } = await import('../../App');
    render(<App />);

    await user.click(screen.getByRole('link', { name: /register/i }));
    await user.type(screen.getByLabelText(/email \(user id\)/i), email);
    await user.type(screen.getByLabelText(/^password$/i), 'testpass1');
    await user.click(screen.getByRole('button', { name: /^register$/i }));
    await waitFor(() => {
      expect(screen.getByTestId('role-home')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /logout/i }));
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /login/i })).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/email \(user id\)/i), email);
    await user.type(screen.getByLabelText(/^password$/i), 'wrongpass');
    await user.click(screen.getByRole('button', { name: /^login$/i }));

    await waitFor(() => {
      expect(screen.getByTestId('auth-error')).toHaveTextContent('Invalid email or password');
    });
    expect(screen.queryByTestId('dashboard-screen')).not.toBeInTheDocument();
    expect(window.location.pathname).toMatch(/login/);
  });
});
