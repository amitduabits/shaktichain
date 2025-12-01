import { Address, BigInt, Bytes, ethereum } from "@graphprotocol/graph-ts";
import { newMockEvent } from "matchstick-as";
import {
  Transfer as TransferEvent,
  FeesBurned as FeesBurnedEvent,
} from "../generated/ShaktiToken/ShaktiToken";
import {
  AuctionRoundCreated as AuctionRoundCreatedEvent,
  BidSubmitted as BidSubmittedEvent,
  AskSubmitted as AskSubmittedEvent,
  OrderMatched as OrderMatchedEvent,
  AuctionCleared as AuctionClearedEvent,
} from "../generated/EnergyAuction/EnergyAuction";
import {
  SettlementCreated as SettlementCreatedEvent,
  SettlementCompleted as SettlementCompletedEvent,
  DisputeRaised as DisputeRaisedEvent,
} from "../generated/EnergyEscrow/EnergyEscrow";
import {
  UserRegistered as UserRegisteredEvent,
  ReputationUpdated as ReputationUpdatedEvent,
} from "../generated/ReputationSystem/ReputationSystem";

// ============ Token Events ============

export function createTransferEvent(
  from: Address,
  to: Address,
  value: BigInt
): TransferEvent {
  let event = changetype<TransferEvent>(newMockEvent());

  event.parameters = new Array();
  event.parameters.push(
    new ethereum.EventParam("from", ethereum.Value.fromAddress(from))
  );
  event.parameters.push(
    new ethereum.EventParam("to", ethereum.Value.fromAddress(to))
  );
  event.parameters.push(
    new ethereum.EventParam("value", ethereum.Value.fromUnsignedBigInt(value))
  );

  return event;
}

export function createFeesBurnedEvent(
  from: Address,
  feeAmount: BigInt,
  burnedAmount: BigInt
): FeesBurnedEvent {
  let event = changetype<FeesBurnedEvent>(newMockEvent());

  event.parameters = new Array();
  event.parameters.push(
    new ethereum.EventParam("from", ethereum.Value.fromAddress(from))
  );
  event.parameters.push(
    new ethereum.EventParam("feeAmount", ethereum.Value.fromUnsignedBigInt(feeAmount))
  );
  event.parameters.push(
    new ethereum.EventParam("burnedAmount", ethereum.Value.fromUnsignedBigInt(burnedAmount))
  );

  return event;
}

// ============ Auction Events ============

export function createAuctionRoundCreatedEvent(
  roundId: BigInt,
  startTime: BigInt,
  endTime: BigInt,
  duration: BigInt
): AuctionRoundCreatedEvent {
  let event = changetype<AuctionRoundCreatedEvent>(newMockEvent());

  event.parameters = new Array();
  event.parameters.push(
    new ethereum.EventParam("roundId", ethereum.Value.fromUnsignedBigInt(roundId))
  );
  event.parameters.push(
    new ethereum.EventParam("startTime", ethereum.Value.fromUnsignedBigInt(startTime))
  );
  event.parameters.push(
    new ethereum.EventParam("endTime", ethereum.Value.fromUnsignedBigInt(endTime))
  );
  event.parameters.push(
    new ethereum.EventParam("duration", ethereum.Value.fromUnsignedBigInt(duration))
  );

  return event;
}

export function createBidSubmittedEvent(
  roundId: BigInt,
  orderId: BigInt,
  trader: Address,
  quantity: BigInt,
  maxPrice: BigInt
): BidSubmittedEvent {
  let event = changetype<BidSubmittedEvent>(newMockEvent());

  event.parameters = new Array();
  event.parameters.push(
    new ethereum.EventParam("roundId", ethereum.Value.fromUnsignedBigInt(roundId))
  );
  event.parameters.push(
    new ethereum.EventParam("orderId", ethereum.Value.fromUnsignedBigInt(orderId))
  );
  event.parameters.push(
    new ethereum.EventParam("trader", ethereum.Value.fromAddress(trader))
  );
  event.parameters.push(
    new ethereum.EventParam("quantity", ethereum.Value.fromUnsignedBigInt(quantity))
  );
  event.parameters.push(
    new ethereum.EventParam("maxPrice", ethereum.Value.fromUnsignedBigInt(maxPrice))
  );

  return event;
}

export function createAskSubmittedEvent(
  roundId: BigInt,
  orderId: BigInt,
  trader: Address,
  quantity: BigInt,
  minPrice: BigInt
): AskSubmittedEvent {
  let event = changetype<AskSubmittedEvent>(newMockEvent());

  event.parameters = new Array();
  event.parameters.push(
    new ethereum.EventParam("roundId", ethereum.Value.fromUnsignedBigInt(roundId))
  );
  event.parameters.push(
    new ethereum.EventParam("orderId", ethereum.Value.fromUnsignedBigInt(orderId))
  );
  event.parameters.push(
    new ethereum.EventParam("trader", ethereum.Value.fromAddress(trader))
  );
  event.parameters.push(
    new ethereum.EventParam("quantity", ethereum.Value.fromUnsignedBigInt(quantity))
  );
  event.parameters.push(
    new ethereum.EventParam("minPrice", ethereum.Value.fromUnsignedBigInt(minPrice))
  );

  return event;
}

export function createOrderMatchedEvent(
  roundId: BigInt,
  orderId: BigInt,
  trader: Address,
  matchedQuantity: BigInt,
  price: BigInt,
  isBid: boolean
): OrderMatchedEvent {
  let event = changetype<OrderMatchedEvent>(newMockEvent());

  event.parameters = new Array();
  event.parameters.push(
    new ethereum.EventParam("roundId", ethereum.Value.fromUnsignedBigInt(roundId))
  );
  event.parameters.push(
    new ethereum.EventParam("orderId", ethereum.Value.fromUnsignedBigInt(orderId))
  );
  event.parameters.push(
    new ethereum.EventParam("trader", ethereum.Value.fromAddress(trader))
  );
  event.parameters.push(
    new ethereum.EventParam("matchedQuantity", ethereum.Value.fromUnsignedBigInt(matchedQuantity))
  );
  event.parameters.push(
    new ethereum.EventParam("price", ethereum.Value.fromUnsignedBigInt(price))
  );
  event.parameters.push(
    new ethereum.EventParam("isBid", ethereum.Value.fromBoolean(isBid))
  );

  return event;
}

export function createAuctionClearedEvent(
  roundId: BigInt,
  clearingPrice: BigInt,
  matchedOrders: BigInt,
  totalVolume: BigInt
): AuctionClearedEvent {
  let event = changetype<AuctionClearedEvent>(newMockEvent());

  event.parameters = new Array();
  event.parameters.push(
    new ethereum.EventParam("roundId", ethereum.Value.fromUnsignedBigInt(roundId))
  );
  event.parameters.push(
    new ethereum.EventParam("clearingPrice", ethereum.Value.fromUnsignedBigInt(clearingPrice))
  );
  event.parameters.push(
    new ethereum.EventParam("matchedOrders", ethereum.Value.fromUnsignedBigInt(matchedOrders))
  );
  event.parameters.push(
    new ethereum.EventParam("totalVolume", ethereum.Value.fromUnsignedBigInt(totalVolume))
  );

  return event;
}

// ============ Escrow Events ============

export function createSettlementCreatedEvent(
  settlementId: BigInt,
  roundId: BigInt,
  buyer: Address,
  seller: Address,
  quantity: BigInt,
  price: BigInt,
  totalAmount: BigInt
): SettlementCreatedEvent {
  let event = changetype<SettlementCreatedEvent>(newMockEvent());

  event.parameters = new Array();
  event.parameters.push(
    new ethereum.EventParam("settlementId", ethereum.Value.fromUnsignedBigInt(settlementId))
  );
  event.parameters.push(
    new ethereum.EventParam("roundId", ethereum.Value.fromUnsignedBigInt(roundId))
  );
  event.parameters.push(
    new ethereum.EventParam("buyer", ethereum.Value.fromAddress(buyer))
  );
  event.parameters.push(
    new ethereum.EventParam("seller", ethereum.Value.fromAddress(seller))
  );
  event.parameters.push(
    new ethereum.EventParam("quantity", ethereum.Value.fromUnsignedBigInt(quantity))
  );
  event.parameters.push(
    new ethereum.EventParam("price", ethereum.Value.fromUnsignedBigInt(price))
  );
  event.parameters.push(
    new ethereum.EventParam("totalAmount", ethereum.Value.fromUnsignedBigInt(totalAmount))
  );

  return event;
}

export function createSettlementCompletedEvent(
  settlementId: BigInt,
  seller: Address,
  sellerAmount: BigInt,
  fee: BigInt,
  burned: BigInt
): SettlementCompletedEvent {
  let event = changetype<SettlementCompletedEvent>(newMockEvent());

  event.parameters = new Array();
  event.parameters.push(
    new ethereum.EventParam("settlementId", ethereum.Value.fromUnsignedBigInt(settlementId))
  );
  event.parameters.push(
    new ethereum.EventParam("seller", ethereum.Value.fromAddress(seller))
  );
  event.parameters.push(
    new ethereum.EventParam("sellerAmount", ethereum.Value.fromUnsignedBigInt(sellerAmount))
  );
  event.parameters.push(
    new ethereum.EventParam("fee", ethereum.Value.fromUnsignedBigInt(fee))
  );
  event.parameters.push(
    new ethereum.EventParam("burned", ethereum.Value.fromUnsignedBigInt(burned))
  );

  return event;
}

export function createDisputeRaisedEvent(
  settlementId: BigInt,
  raisedBy: Address,
  reason: string
): DisputeRaisedEvent {
  let event = changetype<DisputeRaisedEvent>(newMockEvent());

  event.parameters = new Array();
  event.parameters.push(
    new ethereum.EventParam("settlementId", ethereum.Value.fromUnsignedBigInt(settlementId))
  );
  event.parameters.push(
    new ethereum.EventParam("raisedBy", ethereum.Value.fromAddress(raisedBy))
  );
  event.parameters.push(
    new ethereum.EventParam("reason", ethereum.Value.fromString(reason))
  );

  return event;
}

// ============ Reputation Events ============

export function createUserRegisteredEvent(
  user: Address,
  initialReputation: BigInt,
  tier: i32
): UserRegisteredEvent {
  let event = changetype<UserRegisteredEvent>(newMockEvent());

  event.parameters = new Array();
  event.parameters.push(
    new ethereum.EventParam("user", ethereum.Value.fromAddress(user))
  );
  event.parameters.push(
    new ethereum.EventParam("initialReputation", ethereum.Value.fromUnsignedBigInt(initialReputation))
  );
  event.parameters.push(
    new ethereum.EventParam("tier", ethereum.Value.fromI32(tier))
  );

  return event;
}

export function createReputationUpdatedEvent(
  user: Address,
  oldScore: BigInt,
  newScore: BigInt,
  reason: string
): ReputationUpdatedEvent {
  let event = changetype<ReputationUpdatedEvent>(newMockEvent());

  event.parameters = new Array();
  event.parameters.push(
    new ethereum.EventParam("user", ethereum.Value.fromAddress(user))
  );
  event.parameters.push(
    new ethereum.EventParam("oldScore", ethereum.Value.fromUnsignedBigInt(oldScore))
  );
  event.parameters.push(
    new ethereum.EventParam("newScore", ethereum.Value.fromUnsignedBigInt(newScore))
  );
  event.parameters.push(
    new ethereum.EventParam("reason", ethereum.Value.fromString(reason))
  );

  return event;
}
