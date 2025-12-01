import { BigInt, BigDecimal, Bytes, Address, ethereum } from "@graphprotocol/graph-ts";
import {
  Protocol,
  DailyStats,
  HourlyStats,
  PriceCandle,
  Prosumer,
  TokenHolder,
  LeaderboardEntry,
} from "../generated/schema";

// ============ Constants ============

export const ZERO_BI = BigInt.fromI32(0);
export const ONE_BI = BigInt.fromI32(1);
export const ZERO_BD = BigDecimal.fromString("0");
export const ONE_BD = BigDecimal.fromString("1");
export const BI_18 = BigInt.fromI32(18);

export const PROTOCOL_ID = "shakti-chain";
export const SECONDS_PER_DAY = 86400;
export const SECONDS_PER_HOUR = 3600;

// Price precision (18 decimals)
export const PRICE_PRECISION = BigDecimal.fromString("1000000000000000000");

// ============ ID Generation ============

export function generateOrderId(roundId: BigInt, orderId: BigInt): string {
  return roundId.toString() + "-" + orderId.toString();
}

export function generateTradeId(roundId: BigInt, tradeId: BigInt): string {
  return roundId.toString() + "-trade-" + tradeId.toString();
}

export function generateSettlementId(settlementId: BigInt): string {
  return "settlement-" + settlementId.toString();
}

export function generateDisputeId(settlementId: BigInt): string {
  return "dispute-" + settlementId.toString();
}

export function generateStakeId(staker: Address): string {
  return "stake-" + staker.toHexString();
}

export function generateTransferId(txHash: Bytes, logIndex: BigInt): string {
  return txHash.toHexString() + "-" + logIndex.toString();
}

export function generateDailyStatsId(timestamp: BigInt): string {
  let dayId = timestamp.toI32() / SECONDS_PER_DAY;
  return "daily-" + dayId.toString();
}

export function generateHourlyStatsId(timestamp: BigInt): string {
  let hourId = timestamp.toI32() / SECONDS_PER_HOUR;
  return "hourly-" + hourId.toString();
}

export function generatePriceCandleId(timestamp: BigInt, period: i32): string {
  let periodId = timestamp.toI32() / period;
  return "candle-" + period.toString() + "-" + periodId.toString();
}

export function generateReputationChangeId(txHash: Bytes, logIndex: BigInt): string {
  return "rep-" + txHash.toHexString() + "-" + logIndex.toString();
}

export function generateLeaderboardId(address: Address, period: string): string {
  return address.toHexString() + "-" + period;
}

// ============ Conversion Helpers ============

export function toDecimal(value: BigInt, decimals: i32 = 18): BigDecimal {
  let precision = BigInt.fromI32(10).pow(u8(decimals)).toBigDecimal();
  return value.toBigDecimal().div(precision);
}

export function fromDecimal(value: BigDecimal, decimals: i32 = 18): BigInt {
  let precision = BigInt.fromI32(10).pow(u8(decimals)).toBigDecimal();
  return BigInt.fromString(value.times(precision).truncate(0).toString());
}

// ============ Entity Loaders/Creators ============

export function getOrCreateProtocol(): Protocol {
  let protocol = Protocol.load(PROTOCOL_ID);

  if (protocol == null) {
    protocol = new Protocol(PROTOCOL_ID);
    protocol.totalSupply = ZERO_BD;
    protocol.circulatingSupply = ZERO_BD;
    protocol.totalBurned = ZERO_BD;
    protocol.totalVolume = ZERO_BD;
    protocol.totalValueTraded = ZERO_BD;
    protocol.totalTrades = ZERO_BI;
    protocol.totalFees = ZERO_BD;
    protocol.totalProsumers = 0;
    protocol.totalEVs = 0;
    protocol.activeProsumers = 0;
    protocol.totalStaked = ZERO_BD;
    protocol.totalStakers = 0;
    protocol.totalAuctionRounds = 0;
    protocol.currentRoundId = ZERO_BI;
    protocol.lastUpdatedAt = ZERO_BI;
    protocol.save();
  }

  return protocol;
}

export function getOrCreateProsumer(address: Address, timestamp: BigInt): Prosumer {
  let id = address.toHexString();
  let prosumer = Prosumer.load(id);

  if (prosumer == null) {
    prosumer = new Prosumer(id);
    prosumer.address = address;
    prosumer.type = "EV_OWNER"; // Default, updated by registry
    prosumer.reputation = 500; // Starting reputation
    prosumer.tier = "SILVER"; // Starting tier
    prosumer.isKYCVerified = false;
    prosumer.isFlagged = false;
    prosumer.totalTrades = ZERO_BI;
    prosumer.successfulTrades = ZERO_BI;
    prosumer.failedDeliveries = ZERO_BI;
    prosumer.disputesWon = ZERO_BI;
    prosumer.disputesLost = ZERO_BI;
    prosumer.totalVolume = ZERO_BD;
    prosumer.totalValueTraded = ZERO_BD;
    prosumer.stakedAmount = ZERO_BD;
    prosumer.registeredAt = timestamp;
    prosumer.lastActivityAt = timestamp;
    prosumer.save();

    // Update protocol stats
    let protocol = getOrCreateProtocol();
    protocol.totalProsumers = protocol.totalProsumers + 1;
    protocol.lastUpdatedAt = timestamp;
    protocol.save();
  }

  return prosumer;
}

export function getOrCreateTokenHolder(address: Address, timestamp: BigInt): TokenHolder {
  let id = address.toHexString();
  let holder = TokenHolder.load(id);

  if (holder == null) {
    holder = new TokenHolder(id);
    holder.address = address;
    holder.balance = ZERO_BD;
    holder.lockedBalance = ZERO_BD;
    holder.delegatedTo = null;
    holder.votingPower = ZERO_BD;
    holder.totalTransferred = ZERO_BD;
    holder.totalReceived = ZERO_BD;
    holder.totalBurned = ZERO_BD;
    holder.firstSeenAt = timestamp;
    holder.lastActivityAt = timestamp;
    holder.save();
  }

  return holder;
}

export function getOrCreateDailyStats(timestamp: BigInt): DailyStats {
  let id = generateDailyStatsId(timestamp);
  let stats = DailyStats.load(id);

  if (stats == null) {
    let dayTimestamp = (timestamp.toI32() / SECONDS_PER_DAY) * SECONDS_PER_DAY;

    stats = new DailyStats(id);
    stats.date = dayTimestamp;
    stats.totalVolume = ZERO_BD;
    stats.totalValueTraded = ZERO_BD;
    stats.totalTrades = 0;
    stats.successfulTrades = 0;
    stats.failedTrades = 0;
    stats.disputedTrades = 0;
    stats.averagePrice = ZERO_BD;
    stats.highPrice = ZERO_BD;
    stats.lowPrice = ZERO_BD;
    stats.openPrice = null;
    stats.closePrice = null;
    stats.uniqueTraders = 0;
    stats.newProsumers = 0;
    stats.activeEVs = 0;
    stats.totalFees = ZERO_BD;
    stats.totalBurned = ZERO_BD;
    stats.totalStaked = ZERO_BD;
    stats.stakingRewards = ZERO_BD;
    stats.auctionRounds = 0;
    stats.averageClearingPrice = null;
    stats.save();
  }

  return stats;
}

export function getOrCreateHourlyStats(timestamp: BigInt): HourlyStats {
  let id = generateHourlyStatsId(timestamp);
  let stats = HourlyStats.load(id);

  if (stats == null) {
    let hourTimestamp = (timestamp.toI32() / SECONDS_PER_HOUR) * SECONDS_PER_HOUR;

    stats = new HourlyStats(id);
    stats.timestamp = BigInt.fromI32(hourTimestamp);
    stats.hour = hourTimestamp / SECONDS_PER_HOUR;
    stats.volume = ZERO_BD;
    stats.valueTraded = ZERO_BD;
    stats.trades = 0;
    stats.averagePrice = ZERO_BD;
    stats.highPrice = ZERO_BD;
    stats.lowPrice = ZERO_BD;
    stats.save();
  }

  return stats;
}

export function getOrCreatePriceCandle(timestamp: BigInt, period: i32): PriceCandle {
  let id = generatePriceCandleId(timestamp, period);
  let candle = PriceCandle.load(id);

  if (candle == null) {
    let periodTimestamp = (timestamp.toI32() / period) * period;

    candle = new PriceCandle(id);
    candle.timestamp = BigInt.fromI32(periodTimestamp);
    candle.period = period;
    candle.open = ZERO_BD;
    candle.high = ZERO_BD;
    candle.low = ZERO_BD;
    candle.close = ZERO_BD;
    candle.volume = ZERO_BD;
    candle.trades = 0;
    candle.save();
  }

  return candle;
}

// ============ Stats Update Helpers ============

export function updatePriceStats(
  stats: DailyStats,
  price: BigDecimal,
  isFirstTrade: boolean
): void {
  if (isFirstTrade || stats.openPrice === null) {
    stats.openPrice = price;
  }
  stats.closePrice = price;

  if (price.gt(stats.highPrice)) {
    stats.highPrice = price;
  }
  if (stats.lowPrice.equals(ZERO_BD) || price.lt(stats.lowPrice)) {
    stats.lowPrice = price;
  }
}

export function updateHourlyPriceStats(
  stats: HourlyStats,
  price: BigDecimal
): void {
  if (price.gt(stats.highPrice)) {
    stats.highPrice = price;
  }
  if (stats.lowPrice.equals(ZERO_BD) || price.lt(stats.lowPrice)) {
    stats.lowPrice = price;
  }
}

export function updatePriceCandle(
  candle: PriceCandle,
  price: BigDecimal,
  volume: BigDecimal
): void {
  if (candle.open.equals(ZERO_BD)) {
    candle.open = price;
  }
  candle.close = price;

  if (price.gt(candle.high)) {
    candle.high = price;
  }
  if (candle.low.equals(ZERO_BD) || price.lt(candle.low)) {
    candle.low = price;
  }

  candle.volume = candle.volume.plus(volume);
  candle.trades = candle.trades + 1;
}

// ============ Tier Helpers ============

export function getTierFromScore(score: i32): string {
  if (score <= 300) return "BRONZE";
  if (score <= 500) return "SILVER";
  if (score <= 700) return "GOLD";
  if (score <= 850) return "PLATINUM";
  return "DIAMOND";
}

export function getTierFromEnum(tier: i32): string {
  if (tier == 0) return "BRONZE";
  if (tier == 1) return "SILVER";
  if (tier == 2) return "GOLD";
  if (tier == 3) return "PLATINUM";
  return "DIAMOND";
}

// ============ Status Helpers ============

export function getAuctionStateFromEnum(state: i32): string {
  if (state == 0) return "OPEN";
  if (state == 1) return "CLOSED";
  if (state == 2) return "CLEARING";
  return "SETTLED";
}

export function getOrderStatusFromEnum(status: i32): string {
  if (status == 0) return "ACTIVE";
  if (status == 1) return "MATCHED";
  if (status == 2) return "CANCELLED";
  return "EXPIRED";
}

export function getTradeStatusFromEnum(status: i32): string {
  if (status == 0) return "PENDING";
  if (status == 1) return "SETTLED";
  if (status == 2) return "DISPUTED";
  if (status == 3) return "RESOLVED";
  return "REFUNDED";
}

export function getDisputeOutcomeFromEnum(outcome: i32): string {
  if (outcome == 0) return "NONE";
  if (outcome == 1) return "BUYER_WINS";
  if (outcome == 2) return "SELLER_WINS";
  return "SPLIT";
}

// ============ Math Helpers ============

export function min(a: BigDecimal, b: BigDecimal): BigDecimal {
  return a.lt(b) ? a : b;
}

export function max(a: BigDecimal, b: BigDecimal): BigDecimal {
  return a.gt(b) ? a : b;
}

export function calculateAverage(sum: BigDecimal, count: i32): BigDecimal {
  if (count == 0) return ZERO_BD;
  return sum.div(BigDecimal.fromString(count.toString()));
}
