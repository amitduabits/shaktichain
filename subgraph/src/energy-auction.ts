import { BigInt, BigDecimal, Address, Bytes } from "@graphprotocol/graph-ts";
import {
  AuctionRoundCreated as AuctionRoundCreatedEvent,
  AuctionRoundClosed as AuctionRoundClosedEvent,
  AuctionCleared as AuctionClearedEvent,
  AuctionSettled as AuctionSettledEvent,
  BidSubmitted as BidSubmittedEvent,
  AskSubmitted as AskSubmittedEvent,
  OrderCancelled as OrderCancelledEvent,
  OrderMatched as OrderMatchedEvent,
  BatchBidsSubmitted as BatchBidsSubmittedEvent,
  BatchAsksSubmitted as BatchAsksSubmittedEvent,
} from "../generated/EnergyAuction/EnergyAuction";
import {
  AuctionRound,
  Order,
  Trade,
  Prosumer,
  DailyStats,
  HourlyStats,
  PriceCandle,
  Protocol,
} from "../generated/schema";
import {
  ZERO_BD,
  ZERO_BI,
  ONE_BI,
  toDecimal,
  getOrCreateProtocol,
  getOrCreateProsumer,
  getOrCreateDailyStats,
  getOrCreateHourlyStats,
  getOrCreatePriceCandle,
  generateOrderId,
  generateTradeId,
  updatePriceStats,
  updateHourlyPriceStats,
  updatePriceCandle,
  getAuctionStateFromEnum,
  SECONDS_PER_HOUR,
  SECONDS_PER_DAY,
} from "./helpers";

// ============ Auction Round Handlers ============

export function handleAuctionRoundCreated(event: AuctionRoundCreatedEvent): void {
  let roundId = event.params.roundId;
  let startTime = event.params.startTime;
  let endTime = event.params.endTime;
  let duration = event.params.duration;
  let timestamp = event.block.timestamp;

  let round = new AuctionRound(roundId.toString());
  round.roundId = roundId;
  round.startTime = BigInt.fromI64(startTime.toI64());
  round.endTime = BigInt.fromI64(endTime.toI64());
  round.duration = BigInt.fromI64(duration.toI64());
  round.state = "OPEN";
  round.totalBidVolume = ZERO_BD;
  round.totalAskVolume = ZERO_BD;
  round.totalBidValue = ZERO_BD;
  round.totalAskValue = ZERO_BD;
  round.totalBids = 0;
  round.totalAsks = 0;
  round.matchedOrders = 0;
  round.clearingPrice = null;
  round.clearedVolume = null;
  round.createdAt = timestamp;
  round.clearedAt = null;
  round.settledAt = null;
  round.save();

  // Update protocol
  let protocol = getOrCreateProtocol();
  protocol.totalAuctionRounds = protocol.totalAuctionRounds + 1;
  protocol.currentRoundId = roundId;
  protocol.lastUpdatedAt = timestamp;
  protocol.save();

  // Update daily stats
  let dailyStats = getOrCreateDailyStats(timestamp);
  dailyStats.auctionRounds = dailyStats.auctionRounds + 1;
  dailyStats.save();
}

export function handleAuctionRoundClosed(event: AuctionRoundClosedEvent): void {
  let roundId = event.params.roundId;
  let totalBids = event.params.totalBids;
  let totalAsks = event.params.totalAsks;
  let timestamp = event.block.timestamp;

  let round = AuctionRound.load(roundId.toString());
  if (round != null) {
    round.state = "CLOSED";
    round.totalBids = totalBids.toI32();
    round.totalAsks = totalAsks.toI32();
    round.save();
  }
}

export function handleAuctionCleared(event: AuctionClearedEvent): void {
  let roundId = event.params.roundId;
  let clearingPrice = toDecimal(BigInt.fromI64(event.params.clearingPrice.toI64()));
  let matchedOrders = event.params.matchedOrders;
  let totalVolume = toDecimal(event.params.totalVolume);
  let timestamp = event.block.timestamp;

  let round = AuctionRound.load(roundId.toString());
  if (round != null) {
    round.state = "CLEARING";
    round.clearingPrice = clearingPrice;
    round.matchedOrders = matchedOrders.toI32();
    round.clearedVolume = totalVolume;
    round.clearedAt = timestamp;
    round.save();

    // Update daily stats with clearing price
    let dailyStats = getOrCreateDailyStats(timestamp);
    if (dailyStats.averageClearingPrice === null) {
      dailyStats.averageClearingPrice = clearingPrice;
    } else {
      // Simple average (could be improved with weighted average)
      dailyStats.averageClearingPrice = dailyStats.averageClearingPrice!.plus(clearingPrice).div(BigDecimal.fromString("2"));
    }
    dailyStats.save();

    // Update price candles
    let hourlyCandle = getOrCreatePriceCandle(timestamp, SECONDS_PER_HOUR);
    updatePriceCandle(hourlyCandle, clearingPrice, totalVolume);
    hourlyCandle.save();

    let dailyCandle = getOrCreatePriceCandle(timestamp, SECONDS_PER_DAY);
    updatePriceCandle(dailyCandle, clearingPrice, totalVolume);
    dailyCandle.save();
  }
}

export function handleAuctionSettled(event: AuctionSettledEvent): void {
  let roundId = event.params.roundId;
  let timestamp = event.block.timestamp;

  let round = AuctionRound.load(roundId.toString());
  if (round != null) {
    round.state = "SETTLED";
    round.settledAt = timestamp;
    round.save();
  }
}

// ============ Order Handlers ============

export function handleBidSubmitted(event: BidSubmittedEvent): void {
  let roundId = event.params.roundId;
  let orderId = event.params.orderId;
  let trader = event.params.trader;
  let quantity = toDecimal(event.params.quantity);
  let maxPrice = toDecimal(event.params.maxPrice);
  let timestamp = event.block.timestamp;

  // Create order
  let id = generateOrderId(roundId, orderId);
  let order = new Order(id);
  order.orderId = orderId;
  order.round = roundId.toString();
  order.trader = trader.toHexString();
  order.orderType = "BID";
  order.quantity = quantity;
  order.price = maxPrice;
  order.totalValue = quantity.times(maxPrice);
  order.status = "ACTIVE";
  order.matchedQuantity = ZERO_BD;
  order.matchedPrice = null;
  order.submittedAt = timestamp;
  order.matchedAt = null;
  order.cancelledAt = null;
  order.transactionHash = event.transaction.hash;
  order.save();

  // Update round stats
  let round = AuctionRound.load(roundId.toString());
  if (round != null) {
    round.totalBids = round.totalBids + 1;
    round.totalBidVolume = round.totalBidVolume.plus(quantity);
    round.totalBidValue = round.totalBidValue.plus(order.totalValue);
    round.save();
  }

  // Update prosumer
  let prosumer = getOrCreateProsumer(trader, timestamp);
  prosumer.lastActivityAt = timestamp;
  prosumer.save();

  // Update protocol
  let protocol = getOrCreateProtocol();
  protocol.activeProsumers = protocol.activeProsumers + 1;
  protocol.lastUpdatedAt = timestamp;
  protocol.save();
}

export function handleAskSubmitted(event: AskSubmittedEvent): void {
  let roundId = event.params.roundId;
  let orderId = event.params.orderId;
  let trader = event.params.trader;
  let quantity = toDecimal(event.params.quantity);
  let minPrice = toDecimal(event.params.minPrice);
  let timestamp = event.block.timestamp;

  // Create order
  let id = generateOrderId(roundId, orderId);
  let order = new Order(id);
  order.orderId = orderId;
  order.round = roundId.toString();
  order.trader = trader.toHexString();
  order.orderType = "ASK";
  order.quantity = quantity;
  order.price = minPrice;
  order.totalValue = quantity.times(minPrice);
  order.status = "ACTIVE";
  order.matchedQuantity = ZERO_BD;
  order.matchedPrice = null;
  order.submittedAt = timestamp;
  order.matchedAt = null;
  order.cancelledAt = null;
  order.transactionHash = event.transaction.hash;
  order.save();

  // Update round stats
  let round = AuctionRound.load(roundId.toString());
  if (round != null) {
    round.totalAsks = round.totalAsks + 1;
    round.totalAskVolume = round.totalAskVolume.plus(quantity);
    round.totalAskValue = round.totalAskValue.plus(order.totalValue);
    round.save();
  }

  // Update prosumer
  let prosumer = getOrCreateProsumer(trader, timestamp);
  prosumer.lastActivityAt = timestamp;
  prosumer.save();
}

export function handleOrderCancelled(event: OrderCancelledEvent): void {
  let roundId = event.params.roundId;
  let orderId = event.params.orderId;
  let timestamp = event.block.timestamp;

  let id = generateOrderId(roundId, orderId);
  let order = Order.load(id);

  if (order != null) {
    order.status = "CANCELLED";
    order.cancelledAt = timestamp;
    order.save();

    // Update round stats
    let round = AuctionRound.load(roundId.toString());
    if (round != null) {
      if (order.orderType == "BID") {
        round.totalBids = round.totalBids - 1;
        round.totalBidVolume = round.totalBidVolume.minus(order.quantity);
        round.totalBidValue = round.totalBidValue.minus(order.totalValue);
      } else {
        round.totalAsks = round.totalAsks - 1;
        round.totalAskVolume = round.totalAskVolume.minus(order.quantity);
        round.totalAskValue = round.totalAskValue.minus(order.totalValue);
      }
      round.save();
    }
  }
}

export function handleOrderMatched(event: OrderMatchedEvent): void {
  let roundId = event.params.roundId;
  let orderId = event.params.orderId;
  let trader = event.params.trader;
  let matchedQuantity = toDecimal(event.params.matchedQuantity);
  let price = toDecimal(event.params.price);
  let isBid = event.params.isBid;
  let timestamp = event.block.timestamp;

  // Update order
  let id = generateOrderId(roundId, orderId);
  let order = Order.load(id);

  if (order != null) {
    order.status = "MATCHED";
    order.matchedQuantity = matchedQuantity;
    order.matchedPrice = price;
    order.matchedAt = timestamp;
    order.save();
  }

  // Update prosumer stats
  let prosumer = getOrCreateProsumer(trader, timestamp);
  prosumer.totalTrades = prosumer.totalTrades.plus(ONE_BI);
  prosumer.totalVolume = prosumer.totalVolume.plus(matchedQuantity);
  prosumer.totalValueTraded = prosumer.totalValueTraded.plus(matchedQuantity.times(price));
  prosumer.lastActivityAt = timestamp;
  prosumer.save();

  // Update daily stats
  let dailyStats = getOrCreateDailyStats(timestamp);
  dailyStats.totalTrades = dailyStats.totalTrades + 1;
  dailyStats.totalVolume = dailyStats.totalVolume.plus(matchedQuantity);
  dailyStats.totalValueTraded = dailyStats.totalValueTraded.plus(matchedQuantity.times(price));
  updatePriceStats(dailyStats, price, dailyStats.totalTrades == 1);
  dailyStats.save();

  // Update hourly stats
  let hourlyStats = getOrCreateHourlyStats(timestamp);
  hourlyStats.trades = hourlyStats.trades + 1;
  hourlyStats.volume = hourlyStats.volume.plus(matchedQuantity);
  hourlyStats.valueTraded = hourlyStats.valueTraded.plus(matchedQuantity.times(price));
  updateHourlyPriceStats(hourlyStats, price);
  hourlyStats.save();

  // Update protocol
  let protocol = getOrCreateProtocol();
  protocol.totalTrades = protocol.totalTrades.plus(ONE_BI);
  protocol.totalVolume = protocol.totalVolume.plus(matchedQuantity);
  protocol.totalValueTraded = protocol.totalValueTraded.plus(matchedQuantity.times(price));
  protocol.lastUpdatedAt = timestamp;
  protocol.save();
}

// ============ Batch Order Handlers ============

export function handleBatchBidsSubmitted(event: BatchBidsSubmittedEvent): void {
  let roundId = event.params.roundId;
  let trader = event.params.trader;
  let count = event.params.count;
  let timestamp = event.block.timestamp;

  // Update prosumer activity
  let prosumer = getOrCreateProsumer(trader, timestamp);
  prosumer.lastActivityAt = timestamp;
  prosumer.save();

  // Note: Individual orders are handled by separate BidSubmitted events
}

export function handleBatchAsksSubmitted(event: BatchAsksSubmittedEvent): void {
  let roundId = event.params.roundId;
  let trader = event.params.trader;
  let count = event.params.count;
  let timestamp = event.block.timestamp;

  // Update prosumer activity
  let prosumer = getOrCreateProsumer(trader, timestamp);
  prosumer.lastActivityAt = timestamp;
  prosumer.save();

  // Note: Individual orders are handled by separate AskSubmitted events
}
