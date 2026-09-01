import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DemoActivityPanel } from '../../components/web3/DemoActivityPanel';

const resetMock = vi.fn();

vi.mock('../../context/DemoLedgerContext', () => ({
  useDemoLedger: () => ({
    ledger: {
      market: {
        currentRound: 55,
        isOpen: true,
        totalTrades: 2,
        totalVolumeKwh: 22,
        feeBurned: 0.99,
        feeToStakers: 2.31,
      },
      recentOrders: [
        {
          id: 'o-1',
          side: 'buy',
          quantity: 10,
          price: 5,
          fee: 1,
          tokenDelta: -51,
        },
      ],
    },
    resetDemoState: resetMock,
  }),
}));

vi.mock('../../demo/ledger', () => ({
  getRoundTimeRemaining: () => 120,
}));

describe('DemoActivityPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders demo activity details and resets state from panel action', async () => {
    const user = userEvent.setup();
    render(<DemoActivityPanel />);

    expect(screen.getByText('Demo Activity')).toBeInTheDocument();
    expect(screen.getByText('Recent Filled Orders')).toBeInTheDocument();
    expect(screen.getByText('BUY')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Reset Demo Data' }));

    expect(resetMock).toHaveBeenCalledTimes(1);
    expect(screen.getByText('Demo state reset to seed values.')).toBeInTheDocument();
  });
});
