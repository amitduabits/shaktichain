import React, { useState, useEffect } from 'react';
import { useAccount } from 'wagmi';
import { useAppMode } from '../../providers/Web3Provider';
import {
  useStakingPoolStats,
  useStakeInfo,
  useEarnedRewards,
  useStake,
  useUnstake,
  useClaimRewards,
  useShaktiBalance,
  useShaktiAllowance,
  useApproveShakti,
} from '../../contracts/hooks';
import { getContractAddress } from '../../contracts/addresses';
import { useChainId } from 'wagmi';

interface StakingPanelProps {
  // Simulated data for simulation mode
  simulatedData?: {
    stakedAmount: string;
    pendingRewards: string;
    apr: number;
    totalStaked: string;
  };
}

export function StakingPanel({ simulatedData }: StakingPanelProps) {
  const { isLiveMode, isSimulationMode } = useAppMode();
  const { isConnected, address } = useAccount();
  const chainId = useChainId();

  // Form state
  const [stakeAmount, setStakeAmount] = useState('');
  const [unstakeAmount, setUnstakeAmount] = useState('');
  const [activeTab, setActiveTab] = useState<'stake' | 'unstake'>('stake');

  // Live blockchain data
  const { totalStaked, apr, minStakeAmount, lockPeriod } = useStakingPoolStats();
  const { stakedAmount, pendingRewards, isLocked, lockTimeRemaining } = useStakeInfo();
  const { earned } = useEarnedRewards();
  const { balance: shaktiBalance } = useShaktiBalance();

  // Get staking pool address for approval
  let stakingPoolAddress: `0x${string}` | undefined;
  try {
    stakingPoolAddress = getContractAddress('StakingPool', chainId as any);
  } catch {
    stakingPoolAddress = undefined;
  }

  const { allowance, refetch: refetchAllowance } = useShaktiAllowance(stakingPoolAddress);

  // Contract interactions
  const { approve, isPending: approving, isSuccess: approved } = useApproveShakti();
  const { stake, isPending: staking, isSuccess: staked, reset: resetStake } = useStake();
  const { unstake, isPending: unstaking, isSuccess: unstaked, reset: resetUnstake } = useUnstake();
  const { claimRewards, isPending: claiming, isSuccess: claimed, reset: resetClaim } = useClaimRewards();

  // Use simulated or live data
  const displayStakedAmount = isSimulationMode
    ? simulatedData?.stakedAmount || '500.00'
    : stakedAmount;
  const displayPendingRewards = isSimulationMode
    ? simulatedData?.pendingRewards || '12.50'
    : pendingRewards || earned;
  const displayApr = isSimulationMode ? simulatedData?.apr || 12.5 : apr || 0;
  const displayTotalStaked = isSimulationMode
    ? simulatedData?.totalStaked || '5,000,000'
    : totalStaked;

  // Reset forms after successful transactions
  useEffect(() => {
    if (staked) {
      setStakeAmount('');
      resetStake();
      refetchAllowance();
    }
  }, [staked, resetStake, refetchAllowance]);

  useEffect(() => {
    if (unstaked) {
      setUnstakeAmount('');
      resetUnstake();
    }
  }, [unstaked, resetUnstake]);

  useEffect(() => {
    if (claimed) {
      resetClaim();
    }
  }, [claimed, resetClaim]);

  // Check if approval is needed
  const needsApproval =
    isLiveMode &&
    stakeAmount &&
    parseFloat(stakeAmount) > 0 &&
    parseFloat(allowance) < parseFloat(stakeAmount);

  // Handle stake
  const handleStake = async () => {
    if (!stakeAmount || parseFloat(stakeAmount) <= 0) return;

    if (needsApproval && stakingPoolAddress) {
      await approve(stakingPoolAddress, stakeAmount);
    } else {
      await stake(stakeAmount);
    }
  };

  // Handle unstake
  const handleUnstake = async () => {
    if (!unstakeAmount || parseFloat(unstakeAmount) <= 0) return;
    await unstake(unstakeAmount);
  };

  // Handle claim
  const handleClaim = async () => {
    await claimRewards();
  };

  // Set max amounts
  const setMaxStake = () => {
    const max = isSimulationMode ? '1000' : shaktiBalance;
    setStakeAmount(max);
  };

  const setMaxUnstake = () => {
    setUnstakeAmount(displayStakedAmount);
  };

  const isPending = approving || staking || unstaking || claiming;

  return (
    <div className="staking-panel">
      <div className="staking-header">
        <h2>SHAKTI Staking</h2>
        {isSimulationMode && <span className="sim-badge">Simulated</span>}
      </div>

      {/* Stats Overview */}
      <div className="staking-stats">
        <div className="stat-card">
          <span className="stat-label">Your Staked</span>
          <span className="stat-value">
            {parseFloat(displayStakedAmount).toLocaleString(undefined, {
              maximumFractionDigits: 2,
            })}
          </span>
          <span className="stat-unit">SHAKTI</span>
        </div>

        <div className="stat-card">
          <span className="stat-label">Pending Rewards</span>
          <span className="stat-value rewards">
            {parseFloat(displayPendingRewards).toLocaleString(undefined, {
              maximumFractionDigits: 4,
            })}
          </span>
          <span className="stat-unit">SHAKTI</span>
        </div>

        <div className="stat-card">
          <span className="stat-label">APR</span>
          <span className="stat-value apr">{displayApr.toFixed(2)}%</span>
        </div>

        <div className="stat-card">
          <span className="stat-label">Total Staked</span>
          <span className="stat-value">
            {typeof displayTotalStaked === 'string'
              ? displayTotalStaked
              : parseFloat(displayTotalStaked).toLocaleString()}
          </span>
          <span className="stat-unit">SHAKTI</span>
        </div>
      </div>

      {/* Lock Warning */}
      {isLiveMode && isLocked && lockTimeRemaining > 0 && (
        <div className="lock-warning">
          <span className="lock-icon">🔒</span>
          <span>
            Your stake is locked. Unlocks in {formatTime(lockTimeRemaining)}
          </span>
        </div>
      )}

      {/* Action Tabs */}
      <div className="action-tabs">
        <button
          className={`tab ${activeTab === 'stake' ? 'active' : ''}`}
          onClick={() => setActiveTab('stake')}
        >
          Stake
        </button>
        <button
          className={`tab ${activeTab === 'unstake' ? 'active' : ''}`}
          onClick={() => setActiveTab('unstake')}
        >
          Unstake
        </button>
      </div>

      {/* Stake Form */}
      {activeTab === 'stake' && (
        <div className="stake-form">
          <div className="input-group">
            <label>Amount to Stake</label>
            <div className="input-wrapper">
              <input
                type="number"
                value={stakeAmount}
                onChange={(e) => setStakeAmount(e.target.value)}
                placeholder="0.00"
                min="0"
                step="0.01"
                disabled={isPending}
              />
              <button className="max-btn" onClick={setMaxStake} disabled={isPending}>
                MAX
              </button>
            </div>
            {isLiveMode && (
              <span className="balance-hint">
                Available: {parseFloat(shaktiBalance).toLocaleString()} SHAKTI
              </span>
            )}
          </div>

          <button
            className="action-btn stake"
            onClick={handleStake}
            disabled={
              isPending ||
              !stakeAmount ||
              parseFloat(stakeAmount) <= 0 ||
              (isLiveMode && !isConnected)
            }
          >
            {approving
              ? 'Approving...'
              : staking
              ? 'Staking...'
              : needsApproval
              ? 'Approve & Stake'
              : 'Stake SHAKTI'}
          </button>
        </div>
      )}

      {/* Unstake Form */}
      {activeTab === 'unstake' && (
        <div className="stake-form">
          <div className="input-group">
            <label>Amount to Unstake</label>
            <div className="input-wrapper">
              <input
                type="number"
                value={unstakeAmount}
                onChange={(e) => setUnstakeAmount(e.target.value)}
                placeholder="0.00"
                min="0"
                step="0.01"
                disabled={isPending || (isLiveMode && isLocked)}
              />
              <button
                className="max-btn"
                onClick={setMaxUnstake}
                disabled={isPending || (isLiveMode && isLocked)}
              >
                MAX
              </button>
            </div>
            <span className="balance-hint">
              Staked: {parseFloat(displayStakedAmount).toLocaleString()} SHAKTI
            </span>
          </div>

          <button
            className="action-btn unstake"
            onClick={handleUnstake}
            disabled={
              isPending ||
              !unstakeAmount ||
              parseFloat(unstakeAmount) <= 0 ||
              (isLiveMode && isLocked) ||
              (isLiveMode && !isConnected)
            }
          >
            {unstaking ? 'Unstaking...' : 'Unstake SHAKTI'}
          </button>
        </div>
      )}

      {/* Claim Rewards */}
      {parseFloat(displayPendingRewards) > 0 && (
        <div className="claim-section">
          <button
            className="action-btn claim"
            onClick={handleClaim}
            disabled={isPending || (isLiveMode && !isConnected)}
          >
            {claiming
              ? 'Claiming...'
              : `Claim ${parseFloat(displayPendingRewards).toFixed(4)} SHAKTI`}
          </button>
        </div>
      )}

      {/* Connect Wallet Prompt */}
      {isLiveMode && !isConnected && (
        <div className="connect-prompt">
          Connect your wallet to stake SHAKTI tokens
        </div>
      )}
    </div>
  );
}

// Helper function to format time
function formatTime(seconds: number): string {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);

  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

// Styles
const styles = `
.staking-panel {
  background: rgba(31, 41, 55, 0.5);
  border-radius: 16px;
  padding: 24px;
  border: 1px solid rgba(75, 85, 99, 0.3);
}

.staking-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.staking-header h2 {
  margin: 0;
  font-size: 20px;
  color: #f3f4f6;
}

.staking-stats {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}

.stat-card {
  background: rgba(17, 24, 39, 0.5);
  padding: 16px;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-label {
  font-size: 12px;
  color: #9ca3af;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #f3f4f6;
}

.stat-value.rewards {
  color: #10b981;
}

.stat-value.apr {
  color: #f59e0b;
}

.stat-unit {
  font-size: 12px;
  color: #6b7280;
}

.lock-warning {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid rgba(245, 158, 11, 0.3);
  border-radius: 8px;
  margin-bottom: 16px;
  color: #fbbf24;
  font-size: 14px;
}

.action-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.tab {
  flex: 1;
  padding: 12px;
  border: none;
  border-radius: 8px;
  background: rgba(17, 24, 39, 0.5);
  color: #9ca3af;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.tab.active {
  background: rgba(16, 185, 129, 0.2);
  color: #10b981;
}

.tab:hover:not(.active) {
  background: rgba(75, 85, 99, 0.3);
}

.stake-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.input-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.input-group label {
  font-size: 14px;
  color: #9ca3af;
}

.input-wrapper {
  display: flex;
  gap: 8px;
}

.input-wrapper input {
  flex: 1;
  padding: 12px 16px;
  border: 1px solid rgba(75, 85, 99, 0.5);
  border-radius: 8px;
  background: rgba(17, 24, 39, 0.5);
  color: #f3f4f6;
  font-size: 16px;
  outline: none;
  transition: border-color 0.2s;
}

.input-wrapper input:focus {
  border-color: #10b981;
}

.input-wrapper input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.max-btn {
  padding: 12px 16px;
  border: 1px solid rgba(16, 185, 129, 0.5);
  border-radius: 8px;
  background: transparent;
  color: #10b981;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.max-btn:hover:not(:disabled) {
  background: rgba(16, 185, 129, 0.1);
}

.max-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.balance-hint {
  font-size: 12px;
  color: #6b7280;
}

.action-btn {
  padding: 14px 24px;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.action-btn.stake {
  background: linear-gradient(135deg, #10b981, #059669);
  color: white;
}

.action-btn.unstake {
  background: linear-gradient(135deg, #f59e0b, #d97706);
  color: white;
}

.action-btn.claim {
  background: linear-gradient(135deg, #8b5cf6, #7c3aed);
  color: white;
  width: 100%;
}

.action-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

.claim-section {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid rgba(75, 85, 99, 0.3);
}

.connect-prompt {
  text-align: center;
  padding: 20px;
  color: #9ca3af;
  font-size: 14px;
  background: rgba(17, 24, 39, 0.3);
  border-radius: 8px;
  margin-top: 16px;
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

export default StakingPanel;
