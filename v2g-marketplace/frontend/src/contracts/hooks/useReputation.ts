import { useReadContract, useWriteContract, useWaitForTransactionReceipt } from 'wagmi';
import { useAccount, useChainId } from 'wagmi';
import { useCallback, useMemo } from 'react';
import { ReputationSystemABI } from '../abis';
import { getContractAddress, isContractDeployed } from '../addresses';
import { useTransactions } from '../../providers/Web3Provider';

// Reputation tiers
export enum ReputationTier {
  UNRANKED = 0,
  BRONZE = 1,
  SILVER = 2,
  GOLD = 3,
  PLATINUM = 4,
}

export const TIER_NAMES: Record<ReputationTier, string> = {
  [ReputationTier.UNRANKED]: 'Unranked',
  [ReputationTier.BRONZE]: 'Bronze',
  [ReputationTier.SILVER]: 'Silver',
  [ReputationTier.GOLD]: 'Gold',
  [ReputationTier.PLATINUM]: 'Platinum',
};

export const TIER_COLORS: Record<ReputationTier, string> = {
  [ReputationTier.UNRANKED]: '#6b7280', // gray
  [ReputationTier.BRONZE]: '#cd7f32', // bronze
  [ReputationTier.SILVER]: '#c0c0c0', // silver
  [ReputationTier.GOLD]: '#ffd700', // gold
  [ReputationTier.PLATINUM]: '#e5e4e2', // platinum
};

export interface UserInfo {
  reputation: bigint;
  tier: ReputationTier;
  totalTrades: bigint;
  successfulTrades: bigint;
  failedDeliveries: bigint;
  disputesWon: bigint;
  disputesLost: bigint;
  isKYCVerified: boolean;
  isFlagged: boolean;
}

// Hook to get the ReputationSystem contract address for the current chain
export function useReputationSystemAddress() {
  const chainId = useChainId();

  return useMemo(() => {
    try {
      return getContractAddress('ReputationSystem', chainId as any);
    } catch {
      return null;
    }
  }, [chainId]);
}

// Hook to check if ReputationSystem is deployed on current chain
export function useReputationSystemDeployed() {
  const chainId = useChainId();

  return useMemo(() => {
    return isContractDeployed('ReputationSystem', chainId as any);
  }, [chainId]);
}

// Hook to get user's reputation score
export function useReputation(address?: `0x${string}`) {
  const { address: connectedAddress } = useAccount();
  const reputationAddress = useReputationSystemAddress();
  const targetAddress = address || connectedAddress;

  const { data, isLoading, isError, refetch } = useReadContract({
    address: reputationAddress || undefined,
    abi: ReputationSystemABI,
    functionName: 'getReputation',
    args: targetAddress ? [targetAddress] : undefined,
    query: {
      enabled: !!reputationAddress && !!targetAddress,
    },
  });

  return {
    reputation: data ? Number(data) : 0,
    reputationRaw: data as bigint | undefined,
    isLoading,
    isError,
    refetch,
  };
}

// Hook to get user's tier
export function useTier(address?: `0x${string}`) {
  const { address: connectedAddress } = useAccount();
  const reputationAddress = useReputationSystemAddress();
  const targetAddress = address || connectedAddress;

  const { data, isLoading, isError, refetch } = useReadContract({
    address: reputationAddress || undefined,
    abi: ReputationSystemABI,
    functionName: 'getTier',
    args: targetAddress ? [targetAddress] : undefined,
    query: {
      enabled: !!reputationAddress && !!targetAddress,
    },
  });

  const tier = data !== undefined ? (data as ReputationTier) : ReputationTier.UNRANKED;
  const tierName = TIER_NAMES[tier];
  const tierColor = TIER_COLORS[tier];

  return {
    tier,
    tierName,
    tierColor,
    isLoading,
    isError,
    refetch,
  };
}

// Hook to get full user info
export function useUserInfo(address?: `0x${string}`) {
  const { address: connectedAddress } = useAccount();
  const reputationAddress = useReputationSystemAddress();
  const targetAddress = address || connectedAddress;

  const { data, isLoading, isError, refetch } = useReadContract({
    address: reputationAddress || undefined,
    abi: ReputationSystemABI,
    functionName: 'getUserInfo',
    args: targetAddress ? [targetAddress] : undefined,
    query: {
      enabled: !!reputationAddress && !!targetAddress,
    },
  });

  const userInfo: UserInfo | undefined = data
    ? {
        reputation: (data as any)[0],
        tier: (data as any)[1] as ReputationTier,
        totalTrades: (data as any)[2],
        successfulTrades: (data as any)[3],
        failedDeliveries: (data as any)[4],
        disputesWon: (data as any)[5],
        disputesLost: (data as any)[6],
        isKYCVerified: (data as any)[7],
        isFlagged: (data as any)[8],
      }
    : undefined;

  const tierName = userInfo ? TIER_NAMES[userInfo.tier] : 'Unknown';
  const tierColor = userInfo ? TIER_COLORS[userInfo.tier] : '#6b7280';
  const successRate = userInfo && Number(userInfo.totalTrades) > 0
    ? (Number(userInfo.successfulTrades) / Number(userInfo.totalTrades)) * 100
    : 0;

  return {
    userInfo,
    tierName,
    tierColor,
    successRate,
    isLoading,
    isError,
    refetch,
  };
}

// Hook to check if user is registered
export function useIsRegistered(address?: `0x${string}`) {
  const { address: connectedAddress } = useAccount();
  const reputationAddress = useReputationSystemAddress();
  const targetAddress = address || connectedAddress;

  const { data, isLoading, isError, refetch } = useReadContract({
    address: reputationAddress || undefined,
    abi: ReputationSystemABI,
    functionName: 'isRegistered',
    args: targetAddress ? [targetAddress] : undefined,
    query: {
      enabled: !!reputationAddress && !!targetAddress,
    },
  });

  return {
    isRegistered: data as boolean | undefined,
    isLoading,
    isError,
    refetch,
  };
}

// Hook to check if user is KYC verified
export function useIsKYCVerified(address?: `0x${string}`) {
  const { address: connectedAddress } = useAccount();
  const reputationAddress = useReputationSystemAddress();
  const targetAddress = address || connectedAddress;

  const { data, isLoading, refetch } = useReadContract({
    address: reputationAddress || undefined,
    abi: ReputationSystemABI,
    functionName: 'isKYCVerified',
    args: targetAddress ? [targetAddress] : undefined,
    query: {
      enabled: !!reputationAddress && !!targetAddress,
    },
  });

  return {
    isKYCVerified: data as boolean | undefined,
    isLoading,
    refetch,
  };
}

// Hook to register as a prosumer
export function useRegister() {
  const reputationAddress = useReputationSystemAddress();
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

  const register = useCallback(async () => {
    if (!reputationAddress) throw new Error('Reputation system not deployed on this chain');

    writeContract({
      address: reputationAddress,
      abi: ReputationSystemABI,
      functionName: 'register',
    });
  }, [reputationAddress, writeContract]);

  if (hash && isPending) {
    addTransaction(hash, 'Registering as prosumer');
  }
  if (hash && isSuccess) {
    updateTransaction(hash, 'confirmed');
  }
  if (hash && isError) {
    updateTransaction(hash, 'failed', error?.message);
  }

  return {
    register,
    hash,
    isPending,
    isConfirming,
    isSuccess,
    isError,
    error,
    reset,
  };
}

// Hook to get tier thresholds
export function useTierThresholds() {
  const reputationAddress = useReputationSystemAddress();

  const { data, isLoading } = useReadContract({
    address: reputationAddress || undefined,
    abi: ReputationSystemABI,
    functionName: 'getTierThresholds',
    query: { enabled: !!reputationAddress },
  });

  const thresholds = data
    ? {
        bronze: Number((data as any)[0]),
        silver: Number((data as any)[1]),
        gold: Number((data as any)[2]),
        platinum: Number((data as any)[3]),
      }
    : undefined;

  return {
    thresholds,
    isLoading,
  };
}

// Hook to get tier discount
export function useTierDiscount(tier: ReputationTier) {
  const reputationAddress = useReputationSystemAddress();

  const { data, isLoading } = useReadContract({
    address: reputationAddress || undefined,
    abi: ReputationSystemABI,
    functionName: 'getTierDiscount',
    args: [tier],
    query: { enabled: !!reputationAddress },
  });

  return {
    discount: data ? Number(data) / 100 : 0, // Assuming percentage in basis points
    isLoading,
  };
}
