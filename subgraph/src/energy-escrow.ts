import { BigInt, BigDecimal, Address, Bytes } from "@graphprotocol/graph-ts";
import {
  Deposited as DepositedEvent,
  Withdrawn as WithdrawnEvent,
  SettlementCreated as SettlementCreatedEvent,
  SettlementCompleted as SettlementCompletedEvent,
  Refunded as RefundedEvent,
  DisputeRaised as DisputeRaisedEvent,
  DisputeResolved as DisputeResolvedEvent,
  Slashed as SlashedEvent,
} from "../generated/EnergyEscrow/EnergyEscrow";
import {
  Settlement,
  Dispute,
  Trade,
  Prosumer,
  DailyStats,
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
  generateSettlementId,
  generateDisputeId,
  getTradeStatusFromEnum,
  getDisputeOutcomeFromEnum,
} from "./helpers";

// ============ Deposit/Withdraw Handlers ============

export function handleDeposited(event: DepositedEvent): void {
  let roundId = event.params.roundId;
  let trader = event.params.trader;
  let amount = toDecimal(event.params.amount);
  let timestamp = event.block.timestamp;

  // Update prosumer locked balance (tracked in token holder)
  let prosumer = getOrCreateProsumer(trader, timestamp);
  prosumer.lastActivityAt = timestamp;
  prosumer.save();
}

export function handleWithdrawn(event: WithdrawnEvent): void {
  let roundId = event.params.roundId;
  let trader = event.params.trader;
  let amount = toDecimal(event.params.amount);
  let timestamp = event.block.timestamp;

  let prosumer = getOrCreateProsumer(trader, timestamp);
  prosumer.lastActivityAt = timestamp;
  prosumer.save();
}

// ============ Settlement Handlers ============

export function handleSettlementCreated(event: SettlementCreatedEvent): void {
  let settlementId = event.params.settlementId;
  let roundId = event.params.roundId;
  let buyer = event.params.buyer;
  let seller = event.params.seller;
  let quantity = toDecimal(event.params.quantity);
  let price = toDecimal(event.params.price);
  let totalAmount = toDecimal(event.params.totalAmount);
  let timestamp = event.block.timestamp;

  // Create settlement
  let id = generateSettlementId(settlementId);
  let settlement = new Settlement(id);
  settlement.settlementId = settlementId;
  settlement.trade = null; // Can be linked later
  settlement.round = roundId.toString();
  settlement.participant = buyer.toHexString(); // Primary participant for derived relation
  settlement.buyer = buyer.toHexString();
  settlement.seller = seller.toHexString();
  settlement.quantity = quantity;
  settlement.price = price;
  settlement.totalAmount = totalAmount;
  settlement.platformFee = ZERO_BD;
  settlement.burnAmount = ZERO_BD;
  settlement.sellerPayout = ZERO_BD;
  settlement.status = "PENDING";
  settlement.disputeOutcome = "NONE";
  settlement.dispute = null;
  settlement.createdAt = timestamp;
  settlement.disputeDeadline = timestamp.plus(BigInt.fromI32(86400)); // 24 hours
  settlement.completedAt = null;
  settlement.transactionHash = event.transaction.hash;
  settlement.save();

  // Update prosumers
  let buyerProsumer = getOrCreateProsumer(buyer, timestamp);
  buyerProsumer.lastActivityAt = timestamp;
  buyerProsumer.save();

  let sellerProsumer = getOrCreateProsumer(seller, timestamp);
  sellerProsumer.lastActivityAt = timestamp;
  sellerProsumer.save();
}

export function handleSettlementCompleted(event: SettlementCompletedEvent): void {
  let settlementId = event.params.settlementId;
  let seller = event.params.seller;
  let sellerAmount = toDecimal(event.params.sellerAmount);
  let fee = toDecimal(event.params.fee);
  let burned = toDecimal(event.params.burned);
  let timestamp = event.block.timestamp;

  let id = generateSettlementId(settlementId);
  let settlement = Settlement.load(id);

  if (settlement != null) {
    settlement.status = "SETTLED";
    settlement.platformFee = fee;
    settlement.burnAmount = burned;
    settlement.sellerPayout = sellerAmount;
    settlement.completedAt = timestamp;
    settlement.save();

    // Update buyer prosumer
    let buyerAddress = Address.fromString(settlement.buyer);
    let buyerProsumer = getOrCreateProsumer(buyerAddress, timestamp);
    buyerProsumer.successfulTrades = buyerProsumer.successfulTrades.plus(ONE_BI);
    buyerProsumer.lastActivityAt = timestamp;
    buyerProsumer.save();

    // Update seller prosumer
    let sellerProsumer = getOrCreateProsumer(seller, timestamp);
    sellerProsumer.successfulTrades = sellerProsumer.successfulTrades.plus(ONE_BI);
    sellerProsumer.lastActivityAt = timestamp;
    sellerProsumer.save();

    // Update daily stats
    let dailyStats = getOrCreateDailyStats(timestamp);
    dailyStats.successfulTrades = dailyStats.successfulTrades + 1;
    dailyStats.totalFees = dailyStats.totalFees.plus(fee);
    dailyStats.totalBurned = dailyStats.totalBurned.plus(burned);
    dailyStats.save();

    // Update protocol
    let protocol = getOrCreateProtocol();
    protocol.totalFees = protocol.totalFees.plus(fee);
    protocol.totalBurned = protocol.totalBurned.plus(burned);
    protocol.lastUpdatedAt = timestamp;
    protocol.save();
  }
}

export function handleRefunded(event: RefundedEvent): void {
  let settlementId = event.params.settlementId;
  let buyer = event.params.buyer;
  let amount = toDecimal(event.params.amount);
  let timestamp = event.block.timestamp;

  let id = generateSettlementId(settlementId);
  let settlement = Settlement.load(id);

  if (settlement != null) {
    settlement.status = "REFUNDED";
    settlement.completedAt = timestamp;
    settlement.save();

    // Update daily stats
    let dailyStats = getOrCreateDailyStats(timestamp);
    dailyStats.failedTrades = dailyStats.failedTrades + 1;
    dailyStats.save();
  }
}

// ============ Dispute Handlers ============

export function handleDisputeRaised(event: DisputeRaisedEvent): void {
  let settlementId = event.params.settlementId;
  let raisedBy = event.params.raisedBy;
  let reason = event.params.reason;
  let timestamp = event.block.timestamp;

  // Create dispute
  let disputeId = generateDisputeId(settlementId);
  let dispute = new Dispute(disputeId);
  dispute.settlement = generateSettlementId(settlementId);
  dispute.raisedBy = raisedBy.toHexString();
  dispute.reason = reason;
  dispute.resolved = false;
  dispute.outcome = "NONE";
  dispute.resolution = null;
  dispute.arbiter = null;
  dispute.buyerRefund = null;
  dispute.sellerPayout = null;
  dispute.raisedAt = timestamp;
  dispute.resolvedAt = null;
  dispute.transactionHash = event.transaction.hash;
  dispute.save();

  // Update settlement
  let settlementEntityId = generateSettlementId(settlementId);
  let settlement = Settlement.load(settlementEntityId);
  if (settlement != null) {
    settlement.status = "DISPUTED";
    settlement.dispute = disputeId;
    settlement.save();
  }

  // Update daily stats
  let dailyStats = getOrCreateDailyStats(timestamp);
  dailyStats.disputedTrades = dailyStats.disputedTrades + 1;
  dailyStats.save();

  // Update prosumer
  let prosumer = getOrCreateProsumer(raisedBy, timestamp);
  prosumer.lastActivityAt = timestamp;
  prosumer.save();
}

export function handleDisputeResolved(event: DisputeResolvedEvent): void {
  let settlementId = event.params.settlementId;
  let outcome = event.params.outcome;
  let resolution = event.params.resolution;
  let timestamp = event.block.timestamp;

  let disputeId = generateDisputeId(settlementId);
  let dispute = Dispute.load(disputeId);

  if (dispute != null) {
    dispute.resolved = true;
    dispute.outcome = getDisputeOutcomeFromEnum(outcome);
    dispute.resolution = resolution;
    dispute.resolvedAt = timestamp;
    dispute.save();

    // Update settlement
    let settlementEntityId = generateSettlementId(settlementId);
    let settlement = Settlement.load(settlementEntityId);
    if (settlement != null) {
      settlement.status = "RESOLVED";
      settlement.disputeOutcome = getDisputeOutcomeFromEnum(outcome);
      settlement.completedAt = timestamp;
      settlement.save();

      // Update prosumer dispute stats based on outcome
      let buyerAddress = Address.fromString(settlement.buyer);
      let sellerAddress = Address.fromString(settlement.seller);

      let buyerProsumer = getOrCreateProsumer(buyerAddress, timestamp);
      let sellerProsumer = getOrCreateProsumer(sellerAddress, timestamp);

      if (outcome == 1) {
        // BUYER_WINS
        buyerProsumer.disputesWon = buyerProsumer.disputesWon.plus(ONE_BI);
        sellerProsumer.disputesLost = sellerProsumer.disputesLost.plus(ONE_BI);
      } else if (outcome == 2) {
        // SELLER_WINS
        sellerProsumer.disputesWon = sellerProsumer.disputesWon.plus(ONE_BI);
        buyerProsumer.disputesLost = buyerProsumer.disputesLost.plus(ONE_BI);
      }
      // SPLIT outcome doesn't update win/loss counts

      buyerProsumer.lastActivityAt = timestamp;
      sellerProsumer.lastActivityAt = timestamp;
      buyerProsumer.save();
      sellerProsumer.save();
    }
  }
}

export function handleSlashed(event: SlashedEvent): void {
  let trader = event.params.trader;
  let amount = toDecimal(event.params.amount);
  let reason = event.params.reason;
  let timestamp = event.block.timestamp;

  // Update prosumer
  let prosumer = getOrCreateProsumer(trader, timestamp);
  prosumer.failedDeliveries = prosumer.failedDeliveries.plus(ONE_BI);
  prosumer.lastActivityAt = timestamp;
  prosumer.save();

  // Update daily stats
  let dailyStats = getOrCreateDailyStats(timestamp);
  dailyStats.failedTrades = dailyStats.failedTrades + 1;
  dailyStats.save();
}
