// Token hooks
export {
  useShaktiTokenAddress,
  useShaktiTokenDeployed,
  useShaktiBalance,
  useShaktiTokenInfo,
  useShaktiAllowance,
  useApproveShakti,
  useTransferShakti,
  useVotingPower,
  useDelegateVotes,
} from './useShaktiToken';

// Auction hooks
export {
  useEnergyAuctionAddress,
  useEnergyAuctionDeployed,
  useCurrentRound,
  useRoundInfo,
  useAuctionStatus,
  useAuctionParams,
  useSubmitBid,
  useSubmitAsk,
  useCancelOrder,
  useOrder,
  useUserOrders,
  RoundState,
  OrderType,
  OrderStatus,
} from './useEnergyAuction';
export type { RoundInfo, Order } from './useEnergyAuction';

// Staking hooks
export {
  useStakingPoolAddress,
  useStakingPoolDeployed,
  useStakingPoolStats,
  useStakeInfo,
  useEarnedRewards,
  useStake,
  useUnstake,
  useClaimRewards,
  useExit,
} from './useStaking';
export type { StakeInfo } from './useStaking';

// Reputation hooks
export {
  useReputationSystemAddress,
  useReputationSystemDeployed,
  useReputation,
  useTier,
  useUserInfo,
  useIsRegistered,
  useIsKYCVerified,
  useRegister,
  useTierThresholds,
  useTierDiscount,
  ReputationTier,
  TIER_NAMES,
  TIER_COLORS,
} from './useReputation';
export type { UserInfo } from './useReputation';
