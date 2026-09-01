import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BidForm } from '../../components/web3/BidForm';

const placeOrderMock = vi.fn();
let ledgerState = null;

vi.mock('../../providers/Web3Provider', () => ({
  useAppMode: () => ({
    mode: 'simulation',
    isLiveMode: false,
    isSimulationMode: true,
    demoOnly: true,
    canUseLiveMode: false,
    setMode: vi.fn(),
    toggleMode: vi.fn(),
  }),
}));

vi.mock('../../context/DemoLedgerContext', () => ({
  useDemoLedger: () => ({
    ledger: ledgerState,
    placeOrder: placeOrderMock,
  }),
}));

vi.mock('wagmi', () => ({
  useAccount: () => ({ isConnected: false }),
  useChainId: () => 80002,
}));

vi.mock('../../contracts/addresses', () => ({
  getContractAddress: () => '0x0000000000000000000000000000000000000001',
}));

vi.mock('../../contracts/hooks', () => ({
  RoundState: {},
  useAuctionStatus: () => ({
    currentRound: 0n,
    roundInfo: null,
    isOpen: true,
    timeRemaining: 0,
    isLoading: false,
  }),
  useAuctionParams: () => ({
    minBidAmount: '1',
    maxBidAmount: '1000',
  }),
  useSubmitBid: () => ({
    submitBid: vi.fn(),
    isPending: false,
    isSuccess: false,
    reset: vi.fn(),
  }),
  useSubmitAsk: () => ({
    submitAsk: vi.fn(),
    isPending: false,
    isSuccess: false,
    reset: vi.fn(),
  }),
  useShaktiBalance: () => ({
    balance: '0',
  }),
  useShaktiAllowance: () => ({
    allowance: '0',
    refetch: vi.fn(),
  }),
  useApproveShakti: () => ({
    approve: vi.fn(),
    isPending: false,
    isSuccess: false,
  }),
}));

describe('BidForm simulation mode', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    ledgerState = {
      market: { currentRound: 101, isOpen: true, roundDurationSec: 900, roundStartedAtSec: 0 },
      account: { tokenBalance: 500, energyInventory: 250 },
    };
    placeOrderMock.mockReturnValue({ success: true });
  });

  it('submits successful buy and sell orders through demo ledger', async () => {
    const user = userEvent.setup();
    render(<BidForm />);

    const [quantityInput, priceInput] = screen.getAllByRole('spinbutton');

    await user.type(quantityInput, '10');
    await user.type(priceInput, '5');
    await user.click(screen.getByRole('button', { name: 'Place Buy Order' }));

    expect(placeOrderMock).toHaveBeenCalledWith('buy', '10', '5');

    await user.click(screen.getByRole('button', { name: 'Sell (Ask)' }));
    await user.type(quantityInput, '6');
    await user.type(priceInput, '4');
    await user.click(screen.getByRole('button', { name: 'Place Sell Order' }));

    expect(placeOrderMock).toHaveBeenCalledWith('sell', '6', '4');
  });

  it('shows validation error from demo ledger when order is rejected', async () => {
    const user = userEvent.setup();
    placeOrderMock.mockReturnValue({
      success: false,
      code: 'INSUFFICIENT_BALANCE',
      error: 'Not enough SHAKTI balance for this buy order.',
    });

    render(<BidForm />);

    const [quantityInput, priceInput] = screen.getAllByRole('spinbutton');
    await user.type(quantityInput, '99');
    await user.type(priceInput, '20');
    await user.click(screen.getByRole('button', { name: 'Place Buy Order' }));

    expect(screen.getByText('Not enough SHAKTI balance for this buy order.')).toBeInTheDocument();
  });
});
