import React from 'react';
import { ConnectButton } from '@rainbow-me/rainbowkit';
import { useAccount, useChainId, useBalance } from 'wagmi';
import { useAppMode } from '../../providers/Web3Provider';
import { useShaktiBalance, useUserInfo, TIER_NAMES, TIER_COLORS } from '../../contracts/hooks';

interface ConnectWalletProps {
  showBalance?: boolean;
  showTier?: boolean;
  compact?: boolean;
}

export function ConnectWallet({
  showBalance = true,
  showTier = true,
  compact = false,
}: ConnectWalletProps) {
  const { isLiveMode, isSimulationMode, toggleMode } = useAppMode();
  const { isConnected, address } = useAccount();
  const chainId = useChainId();

  // Only fetch on-chain data when in live mode and connected
  const { balance: shaktiBalance } = useShaktiBalance();
  const { data: nativeBalance } = useBalance({
    address,
    query: { enabled: isLiveMode && isConnected },
  });
  const { userInfo, tierName, tierColor } = useUserInfo();

  if (compact) {
    return (
      <div className="connect-wallet-compact">
        <ModeToggle isLiveMode={isLiveMode} onToggle={toggleMode} />
        {isLiveMode && (
          <ConnectButton
            accountStatus="avatar"
            chainStatus="icon"
            showBalance={false}
          />
        )}
      </div>
    );
  }

  return (
    <div className="connect-wallet">
      {/* Mode Toggle */}
      <div className="mode-toggle-container">
        <ModeToggle isLiveMode={isLiveMode} onToggle={toggleMode} />
        <span className="mode-label">
          {isSimulationMode ? 'Simulation Mode' : 'Live Blockchain'}
        </span>
      </div>

      {/* Wallet Connection (only in live mode) */}
      {isLiveMode && (
        <div className="wallet-section">
          <ConnectButton
            accountStatus={{
              smallScreen: 'avatar',
              largeScreen: 'full',
            }}
            chainStatus={{
              smallScreen: 'icon',
              largeScreen: 'full',
            }}
            showBalance={{
              smallScreen: false,
              largeScreen: showBalance,
            }}
          />

          {/* Additional info when connected */}
          {isConnected && (
            <div className="wallet-info">
              {/* SHAKTI Balance */}
              {showBalance && (
                <div className="balance-display">
                  <span className="balance-label">SHAKTI:</span>
                  <span className="balance-value">
                    {parseFloat(shaktiBalance).toLocaleString(undefined, {
                      maximumFractionDigits: 2,
                    })}
                  </span>
                </div>
              )}

              {/* Reputation Tier */}
              {showTier && userInfo && (
                <div className="tier-badge" style={{ backgroundColor: tierColor }}>
                  {tierName}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Simulation mode indicator */}
      {isSimulationMode && (
        <div className="simulation-indicator">
          <span className="simulation-icon">🎮</span>
          <span className="simulation-text">
            Using simulated data. Switch to Live mode to connect your wallet.
          </span>
        </div>
      )}
    </div>
  );
}

// Mode toggle component
interface ModeToggleProps {
  isLiveMode: boolean;
  onToggle: () => void;
}

function ModeToggle({ isLiveMode, onToggle }: ModeToggleProps) {
  return (
    <button
      className={`mode-toggle ${isLiveMode ? 'live' : 'simulation'}`}
      onClick={onToggle}
      title={isLiveMode ? 'Switch to Simulation' : 'Switch to Live Blockchain'}
    >
      <span className={`toggle-indicator ${isLiveMode ? 'right' : 'left'}`} />
      <span className="toggle-label simulation">SIM</span>
      <span className="toggle-label live">LIVE</span>
    </button>
  );
}

// Styles (can be moved to CSS file)
const styles = `
.connect-wallet {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.connect-wallet-compact {
  display: flex;
  align-items: center;
  gap: 8px;
}

.mode-toggle-container {
  display: flex;
  align-items: center;
  gap: 8px;
}

.mode-label {
  font-size: 12px;
  color: #9ca3af;
  font-weight: 500;
}

.mode-toggle {
  position: relative;
  width: 80px;
  height: 32px;
  border-radius: 16px;
  border: none;
  cursor: pointer;
  background: linear-gradient(to right, #374151, #1f2937);
  padding: 2px;
  transition: all 0.3s ease;
}

.mode-toggle.live {
  background: linear-gradient(to right, #10b981, #059669);
}

.toggle-indicator {
  position: absolute;
  width: 28px;
  height: 28px;
  border-radius: 14px;
  background: white;
  top: 2px;
  transition: left 0.3s ease;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.toggle-indicator.left {
  left: 2px;
}

.toggle-indicator.right {
  left: 50px;
}

.toggle-label {
  position: absolute;
  font-size: 10px;
  font-weight: 600;
  top: 50%;
  transform: translateY(-50%);
  color: white;
  opacity: 0.7;
}

.toggle-label.simulation {
  left: 8px;
}

.toggle-label.live {
  right: 8px;
}

.wallet-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.wallet-info {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  background: rgba(31, 41, 55, 0.5);
  border-radius: 8px;
}

.balance-display {
  display: flex;
  align-items: center;
  gap: 4px;
}

.balance-label {
  font-size: 12px;
  color: #9ca3af;
}

.balance-value {
  font-size: 14px;
  font-weight: 600;
  color: #10b981;
}

.tier-badge {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  color: #1f2937;
  text-transform: uppercase;
}

.simulation-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: rgba(59, 130, 246, 0.1);
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: 8px;
}

.simulation-icon {
  font-size: 16px;
}

.simulation-text {
  font-size: 12px;
  color: #60a5fa;
}
`;

// Inject styles
if (typeof document !== 'undefined') {
  const styleSheet = document.createElement('style');
  styleSheet.textContent = styles;
  document.head.appendChild(styleSheet);
}

export default ConnectWallet;
