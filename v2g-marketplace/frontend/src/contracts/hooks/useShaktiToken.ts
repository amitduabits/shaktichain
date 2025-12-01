import { useReadContract, useWriteContract, useWaitForTransactionReceipt } from 'wagmi';
import { useAccount, useChainId } from 'wagmi';
import { parseEther, formatEther } from 'viem';
import { useCallback, useMemo } from 'react';
import { ShaktiTokenABI } from '../abis';
import { getContractAddress, isContractDeployed } from '../addresses';
import { useTransactions } from '../../providers/Web3Provider';

// Hook to get the ShaktiToken contract address for the current chain
export function useShaktiTokenAddress() {
  const chainId = useChainId();

  return useMemo(() => {
    try {
      return getContractAddress('ShaktiToken', chainId as any);
    } catch {
      return null;
    }
  }, [chainId]);
}

// Hook to check if ShaktiToken is deployed on current chain
export function useShaktiTokenDeployed() {
  const chainId = useChainId();

  return useMemo(() => {
    return isContractDeployed('ShaktiToken', chainId as any);
  }, [chainId]);
}

// Hook to get user's SHAKTI balance
export function useShaktiBalance(address?: `0x${string}`) {
  const { address: connectedAddress } = useAccount();
  const tokenAddress = useShaktiTokenAddress();
  const targetAddress = address || connectedAddress;

  const { data, isLoading, isError, error, refetch } = useReadContract({
    address: tokenAddress || undefined,
    abi: ShaktiTokenABI,
    functionName: 'balanceOf',
    args: targetAddress ? [targetAddress] : undefined,
    query: {
      enabled: !!tokenAddress && !!targetAddress,
    },
  });

  const balance = data ? formatEther(data as bigint) : '0';
  const balanceRaw = data as bigint | undefined;

  return {
    balance,
    balanceRaw,
    isLoading,
    isError,
    error,
    refetch,
  };
}

// Hook to get token info (name, symbol, decimals, totalSupply)
export function useShaktiTokenInfo() {
  const tokenAddress = useShaktiTokenAddress();

  const { data: name } = useReadContract({
    address: tokenAddress || undefined,
    abi: ShaktiTokenABI,
    functionName: 'name',
    query: { enabled: !!tokenAddress },
  });

  const { data: symbol } = useReadContract({
    address: tokenAddress || undefined,
    abi: ShaktiTokenABI,
    functionName: 'symbol',
    query: { enabled: !!tokenAddress },
  });

  const { data: decimals } = useReadContract({
    address: tokenAddress || undefined,
    abi: ShaktiTokenABI,
    functionName: 'decimals',
    query: { enabled: !!tokenAddress },
  });

  const { data: totalSupply, refetch: refetchSupply } = useReadContract({
    address: tokenAddress || undefined,
    abi: ShaktiTokenABI,
    functionName: 'totalSupply',
    query: { enabled: !!tokenAddress },
  });

  return {
    name: name as string | undefined,
    symbol: symbol as string | undefined,
    decimals: decimals as number | undefined,
    totalSupply: totalSupply ? formatEther(totalSupply as bigint) : undefined,
    totalSupplyRaw: totalSupply as bigint | undefined,
    refetchSupply,
  };
}

// Hook to get allowance
export function useShaktiAllowance(spender: `0x${string}` | undefined) {
  const { address } = useAccount();
  const tokenAddress = useShaktiTokenAddress();

  const { data, isLoading, refetch } = useReadContract({
    address: tokenAddress || undefined,
    abi: ShaktiTokenABI,
    functionName: 'allowance',
    args: address && spender ? [address, spender] : undefined,
    query: {
      enabled: !!tokenAddress && !!address && !!spender,
    },
  });

  return {
    allowance: data ? formatEther(data as bigint) : '0',
    allowanceRaw: data as bigint | undefined,
    isLoading,
    refetch,
  };
}

// Hook to approve tokens
export function useApproveShakti() {
  const tokenAddress = useShaktiTokenAddress();
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

  const approve = useCallback(
    async (spender: `0x${string}`, amount: string) => {
      if (!tokenAddress) throw new Error('Token not deployed on this chain');

      writeContract({
        address: tokenAddress,
        abi: ShaktiTokenABI,
        functionName: 'approve',
        args: [spender, parseEther(amount)],
      });
    },
    [tokenAddress, writeContract]
  );

  // Track transaction
  if (hash && isPending) {
    addTransaction(hash, 'Approving SHAKTI tokens');
  }
  if (hash && isSuccess) {
    updateTransaction(hash, 'confirmed');
  }
  if (hash && isError) {
    updateTransaction(hash, 'failed', error?.message);
  }

  return {
    approve,
    hash,
    isPending,
    isConfirming,
    isSuccess,
    isError,
    error,
    reset,
  };
}

// Hook to transfer tokens
export function useTransferShakti() {
  const tokenAddress = useShaktiTokenAddress();
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

  const transfer = useCallback(
    async (to: `0x${string}`, amount: string) => {
      if (!tokenAddress) throw new Error('Token not deployed on this chain');

      writeContract({
        address: tokenAddress,
        abi: ShaktiTokenABI,
        functionName: 'transfer',
        args: [to, parseEther(amount)],
      });
    },
    [tokenAddress, writeContract]
  );

  if (hash && isPending) {
    addTransaction(hash, 'Transferring SHAKTI tokens');
  }
  if (hash && isSuccess) {
    updateTransaction(hash, 'confirmed');
  }
  if (hash && isError) {
    updateTransaction(hash, 'failed', error?.message);
  }

  return {
    transfer,
    hash,
    isPending,
    isConfirming,
    isSuccess,
    isError,
    error,
    reset,
  };
}

// Hook to get voting power
export function useVotingPower(address?: `0x${string}`) {
  const { address: connectedAddress } = useAccount();
  const tokenAddress = useShaktiTokenAddress();
  const targetAddress = address || connectedAddress;

  const { data, isLoading, refetch } = useReadContract({
    address: tokenAddress || undefined,
    abi: ShaktiTokenABI,
    functionName: 'getVotes',
    args: targetAddress ? [targetAddress] : undefined,
    query: {
      enabled: !!tokenAddress && !!targetAddress,
    },
  });

  return {
    votingPower: data ? formatEther(data as bigint) : '0',
    votingPowerRaw: data as bigint | undefined,
    isLoading,
    refetch,
  };
}

// Hook to delegate voting power
export function useDelegateVotes() {
  const tokenAddress = useShaktiTokenAddress();
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

  const delegate = useCallback(
    async (delegatee: `0x${string}`) => {
      if (!tokenAddress) throw new Error('Token not deployed on this chain');

      writeContract({
        address: tokenAddress,
        abi: ShaktiTokenABI,
        functionName: 'delegate',
        args: [delegatee],
      });
    },
    [tokenAddress, writeContract]
  );

  if (hash && isPending) {
    addTransaction(hash, 'Delegating voting power');
  }
  if (hash && isSuccess) {
    updateTransaction(hash, 'confirmed');
  }
  if (hash && isError) {
    updateTransaction(hash, 'failed', error?.message);
  }

  return {
    delegate,
    hash,
    isPending,
    isConfirming,
    isSuccess,
    isError,
    error,
    reset,
  };
}
