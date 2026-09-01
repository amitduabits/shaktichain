import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { StakingPanel } from '../../components/web3/StakingPanel';

let ledgerState = null;
const stakeMock = vi.fn();
const unstakeMock = vi.fn();
const claimMock = vi.fn();

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
    stake: stakeMock,
    unstake: unstakeMock,
    claimRewards: claimMock,
  }),
}));

vi.mock('wagmi', () => ({
  useAccount: () => ({ isConnected: false }),
  useChainId: () => 80002,
}));

vi.mock('../../contracts/addresses', () => ({
  getContractAddress: () => '0x0000000000000000000000000000000000000002',
}));

vi.mock('../../contracts/hooks', () => ({
  useStakingPoolStats: () => ({
    totalStaked: '0',
    apr: 0,
    minStakeAmount: '0',
    lockPeriod: 0,
  }),
  useStakeInfo: () => ({
    stakedAmount: '0',
    pendingRewards: '0',
    isLocked: false,
    lockTimeRemaining: 0,
  }),
  useEarnedRewards: () => ({
    earned: '0',
  }),
  useStake: () => ({
    stake: vi.fn(),
    isPending: false,
    isSuccess: false,
    reset: vi.fn(),
  }),
  useUnstake: () => ({
    unstake: vi.fn(),
    isPending: false,
    isSuccess: false,
    reset: vi.fn(),
  }),
  useClaimRewards: () => ({
    claimRewards: vi.fn(),
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

describe('StakingPanel simulation mode', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    ledgerState = {
      account: {
        tokenBalance: 1000,
        stakedAmount: 500,
        pendingRewards: 10,
      },
      staking: {
        apr: 12.5,
        totalStaked: 5000000,
      },
    };

    stakeMock.mockImplementation((amount) => {
      const value = Number(amount);
      if (value <= 0 || value > ledgerState.account.tokenBalance) {
        return { success: false, error: 'Stake amount is invalid.' };
      }
      ledgerState = {
        ...ledgerState,
        account: {
          ...ledgerState.account,
          tokenBalance: ledgerState.account.tokenBalance - value,
          stakedAmount: ledgerState.account.stakedAmount + value,
        },
        staking: {
          ...ledgerState.staking,
          totalStaked: ledgerState.staking.totalStaked + value,
        },
      };
      return { success: true };
    });

    unstakeMock.mockImplementation((amount) => {
      const value = Number(amount);
      if (value <= 0 || value > ledgerState.account.stakedAmount) {
        return { success: false, error: 'Unstake amount is invalid.' };
      }
      ledgerState = {
        ...ledgerState,
        account: {
          ...ledgerState.account,
          tokenBalance: ledgerState.account.tokenBalance + value,
          stakedAmount: ledgerState.account.stakedAmount - value,
        },
        staking: {
          ...ledgerState.staking,
          totalStaked: ledgerState.staking.totalStaked - value,
        },
      };
      return { success: true };
    });

    claimMock.mockImplementation(() => {
      if (ledgerState.account.pendingRewards <= 0) {
        return { success: false, error: 'No rewards available.' };
      }
      ledgerState = {
        ...ledgerState,
        account: {
          ...ledgerState.account,
          tokenBalance: ledgerState.account.tokenBalance + ledgerState.account.pendingRewards,
          pendingRewards: 0,
        },
      };
      return { success: true };
    });
  });

  it('updates displayed values after stake action', async () => {
    const user = userEvent.setup();
    const { rerender } = render(<StakingPanel />);

    expect(screen.getByText('500')).toBeInTheDocument();

    const amountInput = screen.getByPlaceholderText('0.00');
    await user.type(amountInput, '100');
    await user.click(screen.getByRole('button', { name: 'Stake SHAKTI' }));

    rerender(<StakingPanel />);
    expect(screen.getByText('600')).toBeInTheDocument();
  });

  it('updates displayed values after unstake action', async () => {
    const user = userEvent.setup();
    const { rerender } = render(<StakingPanel />);

    await user.click(screen.getByRole('button', { name: 'Unstake' }));

    const unstakeInput = screen.getByPlaceholderText('0.00');
    await user.type(unstakeInput, '100');
    await user.click(screen.getByRole('button', { name: 'Unstake SHAKTI' }));

    rerender(<StakingPanel />);
    expect(screen.getByText('400')).toBeInTheDocument();
  });

  it('claims rewards and updates pending rewards display', async () => {
    const user = userEvent.setup();
    const { rerender } = render(<StakingPanel />);

    await user.click(screen.getByRole('button', { name: 'Claim 10.0000 SHAKTI' }));

    rerender(<StakingPanel />);
    expect(screen.queryByRole('button', { name: /Claim/ })).not.toBeInTheDocument();
    expect(screen.getByText('0')).toBeInTheDocument();
  });
});
