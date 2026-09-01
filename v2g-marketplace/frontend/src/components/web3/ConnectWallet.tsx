import React from 'react';
import { ConnectButton } from '@rainbow-me/rainbowkit';
import { useAccount } from 'wagmi';
import { useAppMode } from '../../providers/Web3Provider';
import { useShaktiBalance, useUserInfo } from '../../contracts/hooks';

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
  const { isLiveMode, isSimulationMode, demoOnly, canUseLiveMode, toggleMode } = useAppMode();
  const { isConnected } = useAccount();

  // Only fetch on-chain data when in live mode and connected
  const { balance: shaktiBalance } = useShaktiBalance();
  const { userInfo, tierName, tierColor } = useUserInfo();

  if (compact) {
    return (
      <div className="connect-wallet-compact">
        {demoOnly ? (
          <span className="demo-only-pill">Demo Mode</span>
        ) : (
          <ModeToggle isLiveMode={isLiveMode} onToggle={toggleMode} />
        )}
        {!demoOnly && isLiveMode && (
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
      <div className="mode-toggle-container">
        {!demoOnly && canUseLiveMode ? (
          <ModeToggle isLiveMode={isLiveMode} onToggle={toggleMode} />
        ) : (
          <span className="demo-only-pill">Demo Mode</span>
        )}
        <span className="mode-label">
          {demoOnly ? 'Demo-only presentation mode' : isSimulationMode ? 'Simulation Mode' : 'Live Blockchain'}
        </span>
      </div>

      {!demoOnly && isLiveMode && (
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

          {isConnected && (
            <div className="wallet-info">
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

              {showTier && userInfo && (
                <div className="tier-badge" style={{ backgroundColor: tierColor }}>
                  {tierName}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {isSimulationMode && (
        <div className="simulation-indicator">
          <span className="simulation-icon">Demo</span>
          <span className="simulation-text">
            {demoOnly
              ? 'Wallet controls are hidden in demo mode.'
              : 'Using simulated data. Switch to Live mode to connect your wallet.'}
          </span>
        </div>
      )}
    </div>
  );
}

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

.demo-only-pill {
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(16, 185, 129, 0.18);
  color: #34d399;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
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
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #93c5fd;
}

.simulation-text {
  font-size: 12px;
  color: #60a5fa;
}
`;

if (typeof document !== 'undefined') {
  const styleSheet = document.createElement('style');
  styleSheet.textContent = styles;
  document.head.appendChild(styleSheet);
}

export default ConnectWallet;
