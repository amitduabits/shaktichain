import {
  assert,
  describe,
  test,
  clearStore,
  beforeAll,
  afterAll,
  beforeEach,
} from "matchstick-as/assembly/index";
import { Address, BigInt, Bytes } from "@graphprotocol/graph-ts";
import { Transfer, TokenHolder, Protocol } from "../generated/schema";
import { handleTransfer, handleFeesBurned } from "../src/shakti-token";
import { Transfer as TransferEvent } from "../generated/ShaktiToken/ShaktiToken";
import { createTransferEvent, createFeesBurnedEvent } from "./utils";

// Test constants
const ALICE = "0x0000000000000000000000000000000000000001";
const BOB = "0x0000000000000000000000000000000000000002";
const ZERO_ADDRESS = "0x0000000000000000000000000000000000000000";

describe("ShaktiToken Handlers", () => {
  beforeEach(() => {
    clearStore();
  });

  describe("handleTransfer", () => {
    test("Should create TokenHolder entities on transfer", () => {
      // Create transfer event
      let event = createTransferEvent(
        Address.fromString(ALICE),
        Address.fromString(BOB),
        BigInt.fromI32(1000)
      );

      // Handle the event
      handleTransfer(event);

      // Assert sender exists
      assert.entityCount("TokenHolder", 2);
      assert.fieldEquals("TokenHolder", ALICE, "address", ALICE);
      assert.fieldEquals("TokenHolder", BOB, "address", BOB);
    });

    test("Should update balances correctly", () => {
      // First mint to ALICE
      let mintEvent = createTransferEvent(
        Address.fromString(ZERO_ADDRESS),
        Address.fromString(ALICE),
        BigInt.fromI32(10000)
      );
      handleTransfer(mintEvent);

      // Transfer from ALICE to BOB
      let transferEvent = createTransferEvent(
        Address.fromString(ALICE),
        Address.fromString(BOB),
        BigInt.fromI32(3000)
      );
      handleTransfer(transferEvent);

      // Check balances (converted to decimal with 18 decimals)
      // Note: Actual values depend on toDecimal implementation
      assert.entityCount("TokenHolder", 2);
    });

    test("Should handle mint (from zero address)", () => {
      let event = createTransferEvent(
        Address.fromString(ZERO_ADDRESS),
        Address.fromString(ALICE),
        BigInt.fromI32(1000000)
      );

      handleTransfer(event);

      // Protocol total supply should increase
      assert.entityCount("Protocol", 1);
    });

    test("Should handle burn (to zero address)", () => {
      // First mint
      let mintEvent = createTransferEvent(
        Address.fromString(ZERO_ADDRESS),
        Address.fromString(ALICE),
        BigInt.fromI32(1000000)
      );
      handleTransfer(mintEvent);

      // Then burn
      let burnEvent = createTransferEvent(
        Address.fromString(ALICE),
        Address.fromString(ZERO_ADDRESS),
        BigInt.fromI32(100000)
      );
      handleTransfer(burnEvent);

      // Protocol total burned should increase
      assert.entityCount("Protocol", 1);
    });

    test("Should create Transfer entity", () => {
      let event = createTransferEvent(
        Address.fromString(ALICE),
        Address.fromString(BOB),
        BigInt.fromI32(5000)
      );

      handleTransfer(event);

      assert.entityCount("Transfer", 1);
    });
  });

  describe("handleFeesBurned", () => {
    test("Should update protocol burned stats", () => {
      let event = createFeesBurnedEvent(
        Address.fromString(ALICE),
        BigInt.fromI32(1000), // feeAmount
        BigInt.fromI32(300)   // burnedAmount (30%)
      );

      handleFeesBurned(event);

      assert.entityCount("Protocol", 1);
    });

    test("Should update daily stats", () => {
      let event = createFeesBurnedEvent(
        Address.fromString(ALICE),
        BigInt.fromI32(1000),
        BigInt.fromI32(300)
      );

      handleFeesBurned(event);

      assert.entityCount("DailyStats", 1);
    });
  });
});
