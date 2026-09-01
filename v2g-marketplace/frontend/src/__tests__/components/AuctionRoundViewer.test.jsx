import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AuctionRoundViewer } from '../../components/web3/AuctionRoundViewer';

const {
  auctionCommitMock,
  auctionRevealMock,
  settleAuctionBatchMock,
  getAuctionRoundMock,
  getAuctionOrderbookMock,
} = vi.hoisted(() => ({
  auctionCommitMock: vi.fn(),
  auctionRevealMock: vi.fn(),
  settleAuctionBatchMock: vi.fn(),
  getAuctionRoundMock: vi.fn(),
  getAuctionOrderbookMock: vi.fn(),
}));

vi.mock('../../services/api', () => ({
  auctionCommit: auctionCommitMock,
  auctionReveal: auctionRevealMock,
  settleAuctionBatch: settleAuctionBatchMock,
  getAuctionRound: getAuctionRoundMock,
  getAuctionOrderbook: getAuctionOrderbookMock,
}));

function createDigestBuffer() {
  const bytes = new Uint8Array(32);
  bytes.fill(1);
  return bytes.buffer;
}

describe('AuctionRoundViewer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(globalThis.crypto.subtle, 'digest').mockResolvedValue(createDigestBuffer());

    auctionCommitMock
      .mockResolvedValueOnce({ round_id: 'demo-round-999', order_id: 'order-1' })
      .mockResolvedValueOnce({ round_id: 'demo-round-999', order_id: 'order-2' });
    auctionRevealMock.mockResolvedValue({ status: 'revealed' });
    settleAuctionBatchMock.mockResolvedValue({
      clearing_price: 6.8,
      matched_orders: 2,
    });
    getAuctionRoundMock.mockResolvedValue({
      id: 'demo-round-999',
      status: 'settled',
      clearing_price: 6.8,
      orders_total: 2,
      orders_revealed: 2,
      matches_total: 1,
    });
    getAuctionOrderbookMock.mockResolvedValue({
      round_id: 'demo-round-999',
      status: 'settled',
      bids: [{ id: 'order-1', quantity: 20, price: 7.2, status: 'settled' }],
      asks: [{ id: 'order-2', quantity: 20, price: 6.4, status: 'settled' }],
    });
  });

  it('runs sample round and performs commit, reveal, and settle sequence', async () => {
    const user = userEvent.setup();
    render(<AuctionRoundViewer />);

    await user.click(screen.getByRole('button', { name: 'Run Sample Round' }));

    await waitFor(() => {
      expect(auctionCommitMock).toHaveBeenCalledTimes(2);
      expect(auctionRevealMock).toHaveBeenCalledTimes(2);
      expect(settleAuctionBatchMock).toHaveBeenCalledTimes(1);
    });

    const firstRound = auctionCommitMock.mock.calls[0][0].round_id;
    const secondRound = auctionCommitMock.mock.calls[1][0].round_id;
    expect(firstRound).toBe(secondRound);
    expect(firstRound).toMatch(/^demo-round-/);

    expect(screen.getByText(/Sample double-auction flow completed/)).toBeInTheDocument();
  });
});
