import { Address, BigInt, ethereum } from "@graphprotocol/graph-ts";
import { newMockEvent } from "matchstick-as";
import {
  Transfer as TransferEvent,
  FeesBurned as FeesBurnedEvent,
} from "../generated/ShaktiToken/ShaktiToken";

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
  burner: Address,
  totalAmount: BigInt,
  burnedAmount: BigInt
): FeesBurnedEvent {
  let event = changetype<FeesBurnedEvent>(newMockEvent());

  event.parameters = new Array();
  event.parameters.push(
    new ethereum.EventParam("burner", ethereum.Value.fromAddress(burner))
  );
  event.parameters.push(
    new ethereum.EventParam(
      "totalAmount",
      ethereum.Value.fromUnsignedBigInt(totalAmount)
    )
  );
  event.parameters.push(
    new ethereum.EventParam(
      "burnedAmount",
      ethereum.Value.fromUnsignedBigInt(burnedAmount)
    )
  );

  return event;
}
