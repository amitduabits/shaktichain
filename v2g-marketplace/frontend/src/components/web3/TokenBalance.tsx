import React from 'react';
import { useAccount } from 'wagmi';
import { useAppMode } from '../../providers/Web3Provider';
import { useDemoLedger } from '../../context/DemoLedgerContext';
import { useShaktiBalance, useShaktiTokenInfo, useVotingPower } from '../../contracts/hooks';

interface TokenBalanceProps {
  showVotingPower?: boolean;
  showTotalSupply?: boolean;
  variant?: 'default' | 'compact' | 'detailed';
  simulatedBalance?: string; // For simulation mode
}

export function TokenBalance({
  showVotingPower = false,
  showTotalSupply = false,
  variant = 'default',
  simulatedBalance = '1000.00',
}: TokenBalanceProps) {
  const { isLiveMode, isSimulationMode } = useAppMode();
  const { ledger } = useDemoLedger();
  const { isConnected } = useAccount();

  // Live blockchain data
  const { balance, isLoading: balanceLoading } = useShaktiBalance();
  const { symbol, totalSupply, isLoading: infoLoading } = useShaktiTokenInfo();
  const { votingPower, isLoading: votingLoading } = useVotingPower();

  // Use simulated or live data based on mode
  const demoBalance = String(ledger?.account?.tokenBalance ?? simulatedBalance);
  const displayBalance = isSimulationMode ? demoBalance : balance;
  const displaySymbol = isSimulationMode ? 'SHAKTI' : (symbol || 'SHAKTI');
  const displayVotingPower = isSimulationMode
    ? String(ledger?.account?.stakedAmount ?? simulatedBalance)
    : votingPower;
  const displayTotalSupply = isSimulationMode ? '100,000,000' : totalSupply;

  const isLoading = isLiveMode && (balanceLoading || infoLoading || votingLoading);
  const showData = isSimulationMode || (isLiveMode && isConnected);

  if (!showData) {
    return (
      <div className="token-balance-placeholder">
        <span>Connect wallet to view balance</span>
      </div>
    );
  }

  if (variant === 'compact') {
    return (
      <div className="token-balance-compact">
        {isLoading ? (
          <span className="loading">...</span>
        ) : (
          <>
            <span className="amount">
              {parseFloat(displayBalance).toLocaleString(undefined, {
                maximumFractionDigits: 2,
              })}
            </span>
            <span className="symbol">{displaySymbol}</span>
          </>
        )}
      </div>
    );
  }

  if (variant === 'detailed') {
    return (
      <div className="token-balance-detailed">
        <div className="balance-header">
          <h3>Token Balance</h3>
          {isSimulationMode && <span className="sim-badge">Simulated</span>}
        </div>

        {isLoading ? (
          <div className="loading-state">Loading...</div>
        ) : (
          <>
            <div className="main-balance">
              <span className="amount">
                {parseFloat(displayBalance).toLocaleString(undefined, {
                  maximumFractionDigits: 4,
                })}
              </span>
              <span className="symbol">{displaySymbol}</span>
            </div>

            <div className="balance-details">
              {showVotingPower && (
                <div className="detail-row">
                  <span className="label">Voting Power:</span>
                  <span className="value">
                    {parseFloat(displayVotingPower).toLocaleString(undefined, {
                      maximumFractionDigits: 2,
                    })}
                  </span>
                </div>
              )}

              {showTotalSupply && displayTotalSupply && (
                <div className="detail-row">
                  <span className="label">Total Supply:</span>
                  <span className="value">
                    {typeof displayTotalSupply === 'string'
                      ? displayTotalSupply
                      : parseFloat(displayTotalSupply).toLocaleString()}
                  </span>
                </div>
              )}

              <div className="detail-row">
                <span className="label">Your Share:</span>
                <span className="value">
                  {displayTotalSupply
                    ? (
                        (parseFloat(displayBalance) /
                          parseFloat(displayTotalSupply.replace(/,/g, ''))) *
                        100
                      ).toFixed(6)
                    : '0'}
                  %
                </span>
              </div>
            </div>
          </>
        )}
      </div>
    );
  }

  // Default variant
  return (
    <div className="token-balance">
      <div className="balance-icon">TK</div>
      <div className="balance-content">
        {isLoading ? (
          <span className="loading">Loading...</span>
        ) : (
          <>
            <span className="amount">
              {parseFloat(displayBalance).toLocaleString(undefined, {
                maximumFractionDigits: 2,
              })}
            </span>
            <span className="symbol">{displaySymbol}</span>
          </>
        )}
      </div>
      {isSimulationMode && <span className="sim-indicator">SIM</span>}
    </div>
  );
}

// Styles
const styles = `
.token-balance {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.1), rgba(16, 185, 129, 0.05));
  border: 1px solid rgba(16, 185, 129, 0.2);
  border-radius: 8px;
}

.token-balance-compact {
  display: flex;
  align-items: center;
  gap: 4px;
}

.token-balance-detailed {
  padding: 16px;
  background: rgba(31, 41, 55, 0.5);
  border-radius: 12px;
  border: 1px solid rgba(75, 85, 99, 0.3);
}

.token-balance-placeholder {
  padding: 12px;
  text-align: center;
  color: #9ca3af;
  font-size: 14px;
}

.balance-icon {
  width: 24px;
  height: 24px;
  border-radius: 999px;
  background: rgba(16, 185, 129, 0.2);
  color: #6ee7b7;
  font-size: 10px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.balance-content {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.amount {
  font-size: 18px;
  font-weight: 700;
  color: #10b981;
}

.token-balance-compact .amount {
  font-size: 14px;
}

.token-balance-detailed .main-balance .amount {
  font-size: 32px;
}

.symbol {
  font-size: 12px;
  color: #9ca3af;
  font-weight: 500;
}

.token-balance-detailed .symbol {
  font-size: 16px;
}

.sim-indicator {
  font-size: 10px;
  padding: 2px 6px;
  background: rgba(59, 130, 246, 0.2);
  color: #60a5fa;
  border-radius: 4px;
  font-weight: 600;
}

.balance-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.balance-header h3 {
  margin: 0;
  font-size: 14px;
  color: #9ca3af;
  font-weight: 500;
}

.sim-badge {
  font-size: 10px;
  padding: 2px 8px;
  background: rgba(59, 130, 246, 0.2);
  color: #60a5fa;
  border-radius: 4px;
  font-weight: 600;
}

.main-balance {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 16px;
}

.balance-details {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid rgba(75, 85, 99, 0.3);
}

.detail-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.detail-row .label {
  font-size: 12px;
  color: #9ca3af;
}

.detail-row .value {
  font-size: 14px;
  color: #e5e7eb;
  font-weight: 500;
}

.loading {
  color: #9ca3af;
  font-style: italic;
}

.loading-state {
  text-align: center;
  padding: 20px;
  color: #9ca3af;
}
`;

// Inject styles
if (typeof document !== 'undefined') {
  const styleSheet = document.createElement('style');
  styleSheet.textContent = styles;
  document.head.appendChild(styleSheet);
}

export default TokenBalance;

