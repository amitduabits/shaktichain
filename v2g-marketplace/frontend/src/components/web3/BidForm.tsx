import React, { useState, useEffect } from 'react';
import { useAccount, useChainId } from 'wagmi';
import { useAppMode } from '../../providers/Web3Provider';
import {
  useAuctionStatus,
  useAuctionParams,
  useSubmitBid,
  useSubmitAsk,
  useShaktiBalance,
  useShaktiAllowance,
  useApproveShakti,
  RoundState,
} from '../../contracts/hooks';
import { getContractAddress } from '../../contracts/addresses';

type OrderType = 'bid' | 'ask';

interface BidFormProps {
  onOrderSubmitted?: (orderType: OrderType, quantity: string, price: string) => void;
  simulatedData?: {
    currentRound: number;
    timeRemaining: number;
    isOpen: boolean;
  };
}

export function BidForm({ onOrderSubmitted, simulatedData }: BidFormProps) {
  const { isLiveMode, isSimulationMode } = useAppMode();
  const { isConnected } = useAccount();
  const chainId = useChainId();

  // Form state
  const [orderType, setOrderType] = useState<OrderType>('bid');
  const [quantity, setQuantity] = useState('');
  const [price, setPrice] = useState('');

  // Live blockchain data
  const { currentRound, roundInfo, isOpen, timeRemaining, isLoading } = useAuctionStatus();
  const { minBidAmount, maxBidAmount } = useAuctionParams();
  const { balance: shaktiBalance } = useShaktiBalance();

  // Get auction address for approval
  let auctionAddress: `0x${string}` | undefined;
  try {
    auctionAddress = getContractAddress('EnergyAuction', chainId as any);
  } catch {
    auctionAddress = undefined;
  }

  const { allowance, refetch: refetchAllowance } = useShaktiAllowance(auctionAddress);

  // Contract interactions
  const { approve, isPending: approving, isSuccess: approved } = useApproveShakti();
  const {
    submitBid,
    isPending: submittingBid,
    isSuccess: bidSubmitted,
    reset: resetBid,
  } = useSubmitBid();
  const {
    submitAsk,
    isPending: submittingAsk,
    isSuccess: askSubmitted,
    reset: resetAsk,
  } = useSubmitAsk();

  // Use simulated or live data
  const displayRound = isSimulationMode
    ? simulatedData?.currentRound || 42
    : currentRound
    ? Number(currentRound)
    : 0;
  const displayTimeRemaining = isSimulationMode
    ? simulatedData?.timeRemaining || 300
    : timeRemaining;
  const displayIsOpen = isSimulationMode
    ? simulatedData?.isOpen !== undefined
      ? simulatedData.isOpen
      : true
    : isOpen;

  // Reset form after successful submission
  useEffect(() => {
    if (bidSubmitted) {
      if (onOrderSubmitted) onOrderSubmitted('bid', quantity, price);
      setQuantity('');
      setPrice('');
      resetBid();
      refetchAllowance();
    }
  }, [bidSubmitted, resetBid, refetchAllowance, onOrderSubmitted, quantity, price]);

  useEffect(() => {
    if (askSubmitted) {
      if (onOrderSubmitted) onOrderSubmitted('ask', quantity, price);
      setQuantity('');
      setPrice('');
      resetAsk();
    }
  }, [askSubmitted, resetAsk, onOrderSubmitted, quantity, price]);

  // Calculate total value for bids
  const totalValue =
    quantity && price ? (parseFloat(quantity) * parseFloat(price)).toFixed(2) : '0.00';

  // Check if approval is needed (for bids)
  const needsApproval =
    isLiveMode &&
    orderType === 'bid' &&
    totalValue &&
    parseFloat(totalValue) > 0 &&
    parseFloat(allowance) < parseFloat(totalValue);

  // Handle submit
  const handleSubmit = async () => {
    if (!quantity || !price || parseFloat(quantity) <= 0 || parseFloat(price) <= 0) return;

    if (isSimulationMode) {
      // In simulation mode, just call the callback
      if (onOrderSubmitted) onOrderSubmitted(orderType, quantity, price);
      setQuantity('');
      setPrice('');
      return;
    }

    if (orderType === 'bid') {
      if (needsApproval && auctionAddress) {
        await approve(auctionAddress, totalValue);
      } else {
        await submitBid(quantity, price);
      }
    } else {
      await submitAsk(quantity, price);
    }
  };

  const isPending = approving || submittingBid || submittingAsk;

  return (
    <div className="bid-form">
      <div className="bid-form-header">
        <h2>Place Order</h2>
        {isSimulationMode && <span className="sim-badge">Simulated</span>}
      </div>

      {/* Auction Status */}
      <div className="auction-status">
        <div className="status-row">
          <span className="status-label">Round:</span>
          <span className="status-value">#{displayRound}</span>
        </div>
        <div className="status-row">
          <span className="status-label">Status:</span>
          <span className={`status-value ${displayIsOpen ? 'open' : 'closed'}`}>
            {displayIsOpen ? 'Open' : 'Closed'}
          </span>
        </div>
        {displayIsOpen && (
          <div className="status-row">
            <span className="status-label">Time Left:</span>
            <span className="status-value countdown">{formatTime(displayTimeRemaining)}</span>
          </div>
        )}
      </div>

      {/* Order Type Tabs */}
      <div className="order-type-tabs">
        <button
          className={`order-tab bid ${orderType === 'bid' ? 'active' : ''}`}
          onClick={() => setOrderType('bid')}
        >
          Buy (Bid)
        </button>
        <button
          className={`order-tab ask ${orderType === 'ask' ? 'active' : ''}`}
          onClick={() => setOrderType('ask')}
        >
          Sell (Ask)
        </button>
      </div>

      {/* Order Form */}
      <div className="order-form">
        <div className="input-group">
          <label>
            {orderType === 'bid' ? 'Energy Quantity (kWh)' : 'Energy to Sell (kWh)'}
          </label>
          <input
            type="number"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            placeholder="0.00"
            min="0"
            step="0.1"
            disabled={isPending || !displayIsOpen}
          />
          {minBidAmount && maxBidAmount && (
            <span className="input-hint">
              Min: {minBidAmount} | Max: {maxBidAmount}
            </span>
          )}
        </div>

        <div className="input-group">
          <label>
            {orderType === 'bid' ? 'Max Price (SHAKTI/kWh)' : 'Min Price (SHAKTI/kWh)'}
          </label>
          <input
            type="number"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            placeholder="0.00"
            min="0"
            step="0.01"
            disabled={isPending || !displayIsOpen}
          />
        </div>

        {/* Order Summary */}
        {quantity && price && parseFloat(quantity) > 0 && parseFloat(price) > 0 && (
          <div className="order-summary">
            <div className="summary-row">
              <span>Quantity:</span>
              <span>{parseFloat(quantity).toFixed(2)} kWh</span>
            </div>
            <div className="summary-row">
              <span>{orderType === 'bid' ? 'Max' : 'Min'} Price:</span>
              <span>{parseFloat(price).toFixed(2)} SHAKTI/kWh</span>
            </div>
            <div className="summary-row total">
              <span>{orderType === 'bid' ? 'Max Total:' : 'Min Earnings:'}</span>
              <span>{totalValue} SHAKTI</span>
            </div>
          </div>
        )}

        {/* Balance Info for Bids */}
        {isLiveMode && orderType === 'bid' && (
          <div className="balance-info">
            <span>Available Balance:</span>
            <span>{parseFloat(shaktiBalance).toLocaleString()} SHAKTI</span>
          </div>
        )}

        {/* Submit Button */}
        <button
          className={`submit-btn ${orderType}`}
          onClick={handleSubmit}
          disabled={
            isPending ||
            !displayIsOpen ||
            !quantity ||
            !price ||
            parseFloat(quantity) <= 0 ||
            parseFloat(price) <= 0 ||
            (isLiveMode && !isConnected)
          }
        >
          {isPending
            ? approving
              ? 'Approving...'
              : 'Submitting...'
            : needsApproval
            ? `Approve & ${orderType === 'bid' ? 'Buy' : 'Sell'}`
            : orderType === 'bid'
            ? 'Place Buy Order'
            : 'Place Sell Order'}
        </button>

        {/* Warnings */}
        {!displayIsOpen && (
          <div className="warning">
            Auction is currently closed. Please wait for the next round.
          </div>
        )}

        {isLiveMode && !isConnected && (
          <div className="warning">Connect your wallet to place orders.</div>
        )}
      </div>
    </div>
  );
}

// Helper function to format time
function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

// Styles
const styles = `
.bid-form {
  background: rgba(31, 41, 55, 0.5);
  border-radius: 16px;
  padding: 24px;
  border: 1px solid rgba(75, 85, 99, 0.3);
}

.bid-form-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.bid-form-header h2 {
  margin: 0;
  font-size: 20px;
  color: #f3f4f6;
}

.auction-status {
  background: rgba(17, 24, 39, 0.5);
  padding: 16px;
  border-radius: 12px;
  margin-bottom: 20px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.status-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.status-label {
  font-size: 14px;
  color: #9ca3af;
}

.status-value {
  font-size: 14px;
  font-weight: 600;
  color: #f3f4f6;
}

.status-value.open {
  color: #10b981;
}

.status-value.closed {
  color: #ef4444;
}

.status-value.countdown {
  font-family: monospace;
  color: #f59e0b;
}

.order-type-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
}

.order-tab {
  flex: 1;
  padding: 12px;
  border: none;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.order-tab.bid {
  background: rgba(16, 185, 129, 0.1);
  color: #6b7280;
}

.order-tab.bid.active {
  background: rgba(16, 185, 129, 0.2);
  color: #10b981;
  border: 1px solid rgba(16, 185, 129, 0.5);
}

.order-tab.ask {
  background: rgba(239, 68, 68, 0.1);
  color: #6b7280;
}

.order-tab.ask.active {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
  border: 1px solid rgba(239, 68, 68, 0.5);
}

.order-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.order-form .input-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.order-form label {
  font-size: 14px;
  color: #9ca3af;
}

.order-form input {
  padding: 12px 16px;
  border: 1px solid rgba(75, 85, 99, 0.5);
  border-radius: 8px;
  background: rgba(17, 24, 39, 0.5);
  color: #f3f4f6;
  font-size: 16px;
  outline: none;
  transition: border-color 0.2s;
}

.order-form input:focus {
  border-color: #10b981;
}

.order-form input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.input-hint {
  font-size: 11px;
  color: #6b7280;
}

.order-summary {
  background: rgba(17, 24, 39, 0.5);
  padding: 16px;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.summary-row {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
  color: #9ca3af;
}

.summary-row.total {
  padding-top: 8px;
  border-top: 1px solid rgba(75, 85, 99, 0.3);
  font-weight: 600;
  color: #f3f4f6;
}

.balance-info {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #6b7280;
  padding: 8px 12px;
  background: rgba(17, 24, 39, 0.3);
  border-radius: 6px;
}

.submit-btn {
  padding: 14px 24px;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.submit-btn.bid {
  background: linear-gradient(135deg, #10b981, #059669);
  color: white;
}

.submit-btn.ask {
  background: linear-gradient(135deg, #ef4444, #dc2626);
  color: white;
}

.submit-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.submit-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

.warning {
  text-align: center;
  padding: 12px;
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid rgba(245, 158, 11, 0.3);
  border-radius: 8px;
  color: #fbbf24;
  font-size: 14px;
}

.sim-badge {
  font-size: 10px;
  padding: 4px 8px;
  background: rgba(59, 130, 246, 0.2);
  color: #60a5fa;
  border-radius: 4px;
  font-weight: 600;
}
`;

// Inject styles
if (typeof document !== 'undefined') {
  const styleSheet = document.createElement('style');
  styleSheet.textContent = styles;
  document.head.appendChild(styleSheet);
}

export default BidForm;
