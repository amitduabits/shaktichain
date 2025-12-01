import { useReadContract, useWriteContract, useWaitForTransactionReceipt } from 'wagmi';
import { useAccount, useChainId } from 'wagmi';
import { parseEther, formatEther } from 'viem';
import { useCallback, useMemo } from 'react';
import { StakingPoolABI } from '../abis';
import { getContractAddress, isContractDeployed } from '../addresses';
import { useTransactions } from '../../providers/Web3Provider';

export interface StakeInfo {
  amount: bigint;
  shares: bigint;
  stakedAt: bigint;
  lockEndTime: bigint;
  pendingRewards: bigint;
}

// Hook to get the StakingPool contract address for the current chain
export function useStakingPoolAddress() {
  const chainId = useChainId();

  return useMemo(() => {
    try {
      return getContractAddress('StakingPool', chainId as any);
    } catch {
      return null;
    }
  }, [chainId]);
}

// Hook to check if StakingPool is deployed on current chain
export function useStakingPoolDeployed() {
  const chainId = useChainId();

  return useMemo(() => {
    return isContractDeployed('StakingPool', chainId as any);
  }, [chainId]);
}

// Hook to get staking pool stats
export function useStakingPoolStats() {
  const stakingAddress = useStakingPoolAddress();

  const { data: totalStaked, refetch: refetchTotal } = useReadContract({
    address: stakingAddress || undefined,
    abi: StakingPoolABI,
    functionName: 'totalStaked',
    query: {
      enabled: !!stakingAddress,
      refetchInterval: 30000, // Refetch every 30 seconds
    },
  });

  const { data: rewardRate } = useReadContract({
    address: stakingAddress || undefined,
    abi: StakingPoolABI,
    functionName: 'rewardRate',
    query: { enabled: !!stakingAddress },
  });

  const { data: minStakeAmount } = useReadContract({
    address: stakingAddress || undefined,
    abi: StakingPoolABI,
    functionName: 'minStakeAmount',
    query: { enabled: !!stakingAddress },
  });

  const { data: lockPeriod } = useReadContract({
    address: stakingAddress || undefined,
    abi: StakingPoolABI,
    functionName: 'lockPeriod',
    query: { enabled: !!stakingAddress },
  });

  const { data: apr } = useReadContract({
    address: stakingAddress || undefined,
    abi: StakingPoolABI,
    functionName: 'getAPR',
    query: { enabled: !!stakingAddress },
  });

  return {
    totalStaked: totalStaked ? formatEther(totalStaked as bigint) : '0',
    totalStakedRaw: totalStaked as bigint | undefined,
    rewardRate: rewardRate as bigint | undefined,
    minStakeAmount: minStakeAmount ? formatEther(minStakeAmount as bigint) : '0',
    lockPeriod: lockPeriod as bigint | undefined,
    apr: apr ? Number(apr) / 100 : undefined, // Assuming APR is in basis points
    refetchTotal,
  };
}

// Hook to get user's stake info
export function useStakeInfo(address?: `0x${string}`) {
  const { address: connectedAddress } = useAccount();
  const stakingAddress = useStakingPoolAddress();
  const targetAddress = address || connectedAddress;

  const { data, isLoading, isError, refetch } = useReadContract({
    address: stakingAddress || undefined,
    abi: StakingPoolABI,
    functionName: 'getStakeInfo',
    args: targetAddress ? [targetAddress] : undefined,
    query: {
      enabled: !!stakingAddress && !!targetAddress,
      refetchInterval: 15000, // Refetch every 15 seconds
    },
  });

  const stakeInfo: StakeInfo | undefined = data
    ? {
        amount: (data as any)[0],
        shares: (data as any)[1],
        stakedAt: (data as any)[2],
        lockEndTime: (data as any)[3],
        pendingRewards: (data as any)[4],
      }
    : undefined;

  const isLocked = stakeInfo
    ? Number(stakeInfo.lockEndTime) > Math.floor(Date.now() / 1000)
    : false;

  const lockTimeRemaining = stakeInfo
    ? Math.max(0, Number(stakeInfo.lockEndTime) - Math.floor(Date.now() / 1000))
    : 0;

  return {
    stakeInfo,
    stakedAmount: stakeInfo ? formatEther(stakeInfo.amount) : '0',
    pendingRewards: stakeInfo ? formatEther(stakeInfo.pendingRewards) : '0',
    isLocked,
    lockTimeRemaining,
    isLoading,
    isError,
    refetch,
  };
}

// Hook to get earned rewards
export function useEarnedRewards(address?: `0x${string}`) {
  const { address: connectedAddress } = useAccount();
  const stakingAddress = useStakingPoolAddress();
  const targetAddress = address || connectedAddress;

  const { data, isLoading, refetch } = useReadContract({
    address: stakingAddress || undefined,
    abi: StakingPoolABI,
    functionName: 'earned',
    args: targetAddress ? [targetAddress] : undefined,
    query: {
      enabled: !!stakingAddress && !!targetAddress,
      refetchInterval: 10000, // Refetch every 10 seconds
    },
  });

  return {
    earned: data ? formatEther(data as bigint) : '0',
    earnedRaw: data as bigint | undefined,
    isLoading,
    refetch,
  };
}

// Hook to stake tokens
export function useStake() {
  const stakingAddress = useStakingPoolAddress();
  const { addTransaction, updateTransaction } = useTransactions();

  const {
    writeContract,
    data: hash,
    isPending,
    isError,
    error,
    reset,
  } = useWriteContract();

  const { isLoading: isConfirming, isSuccess } = useWaitForTransactionReceipt({
    hash,
  });

  const stake = useCallback(
    async (amount: string) => {
      if (!stakingAddress) throw new Error('Staking pool not deployed on this chain');

      writeContract({
        address: stakingAddress,
        abi: StakingPoolABI,
        functionName: 'stake',
        args: [parseEther(amount)],
      });
    },
    [stakingAddress, writeContract]
  );

  if (hash && isPending) {
    addTransaction(hash, 'Staking SHAKTI tokens');
  }
  if (hash && isSuccess) {
    updateTransaction(hash, 'confirmed');
  }
  if (hash && isError) {
    updateTransaction(hash, 'failed', error?.message);
  }

  return {
    stake,
    hash,
    isPending,
    isConfirming,
    isSuccess,
    isError,
    error,
    reset,
  };
}

// Hook to unstake tokens
export function useUnstake() {
  const stakingAddress = useStakingPoolAddress();
  const { addTransaction, updateTransaction } = useTransactions();

  const {
    writeContract,
    data: hash,
    isPending,
    isError,
    error,
    reset,
  } = useWriteContract();

  const { isLoading: isConfirming, isSuccess } = useWaitForTransactionReceipt({
    hash,
  });

  const unstake = useCallback(
    async (amount: string) => {
      if (!stakingAddress) throw new Error('Staking pool not deployed on this chain');

      writeContract({
        address: stakingAddress,
        abi: StakingPoolABI,
        functionName: 'unstake',
        args: [parseEther(amount)],
      });
    },
    [stakingAddress, writeContract]
  );

  if (hash && isPending) {
    addTransaction(hash, 'Unstaking SHAKTI tokens');
  }
  if (hash && isSuccess) {
    updateTransaction(hash, 'confirmed');
  }
  if (hash && isError) {
    updateTransaction(hash, 'failed', error?.message);
  }

  return {
    unstake,
    hash,
    isPending,
    isConfirming,
    isSuccess,
    isError,
    error,
    reset,
  };
}

// Hook to claim rewards
export function useClaimRewards() {
  const stakingAddress = useStakingPoolAddress();
  const { addTransaction, updateTransaction } = useTransactions();

  const {
    writeContract,
    data: hash,
    isPending,
    isError,
    error,
    reset,
  } = useWriteContract();

  const { isLoading: isConfirming, isSuccess } = useWaitForTransactionReceipt({
    hash,
  });

  const claimRewards = useCallback(async () => {
    if (!stakingAddress) throw new Error('Staking pool not deployed on this chain');

    writeContract({
      address: stakingAddress,
      abi: StakingPoolABI,
      functionName: 'claimRewards',
    });
  }, [stakingAddress, writeContract]);

  if (hash && isPending) {
    addTransaction(hash, 'Claiming staking rewards');
  }
  if (hash && isSuccess) {
    updateTransaction(hash, 'confirmed');
  }
  if (hash && isError) {
    updateTransaction(hash, 'failed', error?.message);
  }

  return {
    claimRewards,
    hash,
    isPending,
    isConfirming,
    isSuccess,
    isError,
    error,
    reset,
  };
}

// Hook to exit (unstake all + claim rewards)
export function useExit() {
  const stakingAddress = useStakingPoolAddress();
  const { addTransaction, updateTransaction } = useTransactions();

  const {
    writeContract,
    data: hash,
    isPending,
    isError,
    error,
    reset,
  } = useWriteContract();

  const { isLoading: isConfirming, isSuccess } = useWaitForTransactionReceipt({
    hash,
  });

  const exit = useCallback(async () => {
    if (!stakingAddress) throw new Error('Staking pool not deployed on this chain');

    writeContract({
      address: stakingAddress,
      abi: StakingPoolABI,
      functionName: 'exit',
    });
  }, [stakingAddress, writeContract]);

  if (hash && isPending) {
    addTransaction(hash, 'Exiting staking pool');
  }
  if (hash && isSuccess) {
    updateTransaction(hash, 'confirmed');
  }
  if (hash && isError) {
    updateTransaction(hash, 'failed', error?.message);
  }

  return {
    exit,
    hash,
    isPending,
    isConfirming,
    isSuccess,
    isError,
    error,
    reset,
  };
}
