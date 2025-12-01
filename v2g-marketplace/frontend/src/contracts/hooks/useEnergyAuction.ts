import { useReadContract, useWriteContract, useWaitForTransactionReceipt } from 'wagmi';
import { useAccount, useChainId } from 'wagmi';
import { parseEther, formatEther } from 'viem';
import { useCallback, useMemo } from 'react';
import { EnergyAuctionABI } from '../abis';
import { getContractAddress, isContractDeployed } from '../addresses';
import { useTransactions } from '../../providers/Web3Provider';

// Auction round states
export enum RoundState {
  NONE = 0,
  OPEN = 1,
  CLEARING = 2,
  SETTLED = 3,
  CANCELLED = 4,
}

// Order types
export enum OrderType {
  BID = 0,
  ASK = 1,
}

// Order statuses
export enum OrderStatus {
  PENDING = 0,
  MATCHED = 1,
  PARTIAL = 2,
  CANCELLED = 3,
  EXPIRED = 4,
}

export interface RoundInfo {
  startTime: bigint;
  endTime: bigint;
  clearingPrice: bigint;
  totalBidVolume: bigint;
  totalAskVolume: bigint;
  state: RoundState;
}

export interface Order {
  trader: `0x${string}`;
  roundId: bigint;
  orderType: OrderType;
  quantity: bigint;
  price: bigint;
  status: OrderStatus;
  matchedQuantity: bigint;
  matchedPrice: bigint;
}

// Hook to get the EnergyAuction contract address for the current chain
export function useEnergyAuctionAddress() {
  const chainId = useChainId();

  return useMemo(() => {
    try {
      return getContractAddress('EnergyAuction', chainId as any);
    } catch {
      return null;
    }
  }, [chainId]);
}

// Hook to check if EnergyAuction is deployed on current chain
export function useEnergyAuctionDeployed() {
  const chainId = useChainId();

  return useMemo(() => {
    return isContractDeployed('EnergyAuction', chainId as any);
  }, [chainId]);
}

// Hook to get current auction round
export function useCurrentRound() {
  const auctionAddress = useEnergyAuctionAddress();

  const { data, isLoading, isError, refetch } = useReadContract({
    address: auctionAddress || undefined,
    abi: EnergyAuctionABI,
    functionName: 'getCurrentRound',
    query: {
      enabled: !!auctionAddress,
      refetchInterval: 10000, // Refetch every 10 seconds
    },
  });

  return {
    currentRound: data as bigint | undefined,
    isLoading,
    isError,
    refetch,
  };
}

// Hook to get round info
export function useRoundInfo(roundId: bigint | undefined) {
  const auctionAddress = useEnergyAuctionAddress();

  const { data, isLoading, isError, refetch } = useReadContract({
    address: auctionAddress || undefined,
    abi: EnergyAuctionABI,
    functionName: 'getRoundInfo',
    args: roundId !== undefined ? [roundId] : undefined,
    query: {
      enabled: !!auctionAddress && roundId !== undefined,
      refetchInterval: 5000, // Refetch every 5 seconds for live updates
    },
  });

  const roundInfo: RoundInfo | undefined = data
    ? {
        startTime: (data as any)[0],
        endTime: (data as any)[1],
        clearingPrice: (data as any)[2],
        totalBidVolume: (data as any)[3],
        totalAskVolume: (data as any)[4],
        state: (data as any)[5],
      }
    : undefined;

  return {
    roundInfo,
    isLoading,
    isError,
    refetch,
  };
}

// Hook to get current auction status (combines current round and round info)
export function useAuctionStatus() {
  const { currentRound, isLoading: roundLoading } = useCurrentRound();
  const { roundInfo, isLoading: infoLoading, refetch } = useRoundInfo(currentRound);

  const isOpen = roundInfo?.state === RoundState.OPEN;
  const timeRemaining = roundInfo
    ? Math.max(0, Number(roundInfo.endTime) - Math.floor(Date.now() / 1000))
    : 0;

  return {
    currentRound,
    roundInfo,
    isOpen,
    timeRemaining,
    isLoading: roundLoading || infoLoading,
    refetch,
  };
}

// Hook to get auction parameters
export function useAuctionParams() {
  const auctionAddress = useEnergyAuctionAddress();

  const { data: roundDuration } = useReadContract({
    address: auctionAddress || undefined,
    abi: EnergyAuctionABI,
    functionName: 'roundDuration',
    query: { enabled: !!auctionAddress },
  });

  const { data: minBidAmount } = useReadContract({
    address: auctionAddress || undefined,
    abi: EnergyAuctionABI,
    functionName: 'minBidAmount',
    query: { enabled: !!auctionAddress },
  });

  const { data: maxBidAmount } = useReadContract({
    address: auctionAddress || undefined,
    abi: EnergyAuctionABI,
    functionName: 'maxBidAmount',
    query: { enabled: !!auctionAddress },
  });

  return {
    roundDuration: roundDuration as bigint | undefined,
    minBidAmount: minBidAmount ? formatEther(minBidAmount as bigint) : undefined,
    maxBidAmount: maxBidAmount ? formatEther(maxBidAmount as bigint) : undefined,
  };
}

// Hook to submit a bid (buy order)
export function useSubmitBid() {
  const auctionAddress = useEnergyAuctionAddress();
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

  const submitBid = useCallback(
    async (quantity: string, maxPrice: string) => {
      if (!auctionAddress) throw new Error('Auction not deployed on this chain');

      writeContract({
        address: auctionAddress,
        abi: EnergyAuctionABI,
        functionName: 'submitBid',
        args: [parseEther(quantity), parseEther(maxPrice)],
      });
    },
    [auctionAddress, writeContract]
  );

  if (hash && isPending) {
    addTransaction(hash, 'Submitting buy order');
  }
  if (hash && isSuccess) {
    updateTransaction(hash, 'confirmed');
  }
  if (hash && isError) {
    updateTransaction(hash, 'failed', error?.message);
  }

  return {
    submitBid,
    hash,
    isPending,
    isConfirming,
    isSuccess,
    isError,
    error,
    reset,
  };
}

// Hook to submit an ask (sell order)
export function useSubmitAsk() {
  const auctionAddress = useEnergyAuctionAddress();
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

  const submitAsk = useCallback(
    async (quantity: string, minPrice: string) => {
      if (!auctionAddress) throw new Error('Auction not deployed on this chain');

      writeContract({
        address: auctionAddress,
        abi: EnergyAuctionABI,
        functionName: 'submitAsk',
        args: [parseEther(quantity), parseEther(minPrice)],
      });
    },
    [auctionAddress, writeContract]
  );

  if (hash && isPending) {
    addTransaction(hash, 'Submitting sell order');
  }
  if (hash && isSuccess) {
    updateTransaction(hash, 'confirmed');
  }
  if (hash && isError) {
    updateTransaction(hash, 'failed', error?.message);
  }

  return {
    submitAsk,
    hash,
    isPending,
    isConfirming,
    isSuccess,
    isError,
    error,
    reset,
  };
}

// Hook to cancel an order
export function useCancelOrder() {
  const auctionAddress = useEnergyAuctionAddress();
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

  const cancelOrder = useCallback(
    async (orderId: bigint) => {
      if (!auctionAddress) throw new Error('Auction not deployed on this chain');

      writeContract({
        address: auctionAddress,
        abi: EnergyAuctionABI,
        functionName: 'cancelOrder',
        args: [orderId],
      });
    },
    [auctionAddress, writeContract]
  );

  if (hash && isPending) {
    addTransaction(hash, 'Cancelling order');
  }
  if (hash && isSuccess) {
    updateTransaction(hash, 'confirmed');
  }
  if (hash && isError) {
    updateTransaction(hash, 'failed', error?.message);
  }

  return {
    cancelOrder,
    hash,
    isPending,
    isConfirming,
    isSuccess,
    isError,
    error,
    reset,
  };
}

// Hook to get order details
export function useOrder(orderId: bigint | undefined) {
  const auctionAddress = useEnergyAuctionAddress();

  const { data, isLoading, isError, refetch } = useReadContract({
    address: auctionAddress || undefined,
    abi: EnergyAuctionABI,
    functionName: 'getOrder',
    args: orderId !== undefined ? [orderId] : undefined,
    query: {
      enabled: !!auctionAddress && orderId !== undefined,
    },
  });

  const order: Order | undefined = data
    ? {
        trader: (data as any)[0],
        roundId: (data as any)[1],
        orderType: (data as any)[2],
        quantity: (data as any)[3],
        price: (data as any)[4],
        status: (data as any)[5],
        matchedQuantity: (data as any)[6],
        matchedPrice: (data as any)[7],
      }
    : undefined;

  return {
    order,
    isLoading,
    isError,
    refetch,
  };
}

// Hook to get user's orders for a specific round
export function useUserOrders(roundId: bigint | undefined) {
  const { address } = useAccount();
  const auctionAddress = useEnergyAuctionAddress();

  const { data, isLoading, isError, refetch } = useReadContract({
    address: auctionAddress || undefined,
    abi: EnergyAuctionABI,
    functionName: 'getUserOrders',
    args: address && roundId !== undefined ? [address, roundId] : undefined,
    query: {
      enabled: !!auctionAddress && !!address && roundId !== undefined,
    },
  });

  return {
    orderIds: data as bigint[] | undefined,
    isLoading,
    isError,
    refetch,
  };
}
