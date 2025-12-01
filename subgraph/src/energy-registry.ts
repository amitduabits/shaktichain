import { BigInt, BigDecimal, Address, Bytes } from "@graphprotocol/graph-ts";
import {
  EVRegistered as EVRegisteredEvent,
  EVUpdated as EVUpdatedEvent,
  EVDeregistered as EVDeregisteredEvent,
  EnergyDeliveryRecorded as EnergyDeliveryRecordedEvent,
} from "../generated/EnergyRegistry/EnergyRegistry";
import { EV, Prosumer, Protocol, DailyStats } from "../generated/schema";
import {
  ZERO_BD,
  ZERO_BI,
  ONE_BI,
  toDecimal,
  getOrCreateProtocol,
  getOrCreateProsumer,
  getOrCreateDailyStats,
} from "./helpers";

// ============ EV Registration ============

export function handleEVRegistered(event: EVRegisteredEvent): void {
  let owner = event.params.owner;
  let vehicleId = event.params.vehicleId;
  let batteryCapacity = event.params.batteryCapacity;
  let maxChargingRate = event.params.maxChargingRate;
  let maxDischargingRate = event.params.maxDischargingRate;
  let timestamp = event.block.timestamp;

  // Create EV entity
  let evId = vehicleId.toHexString();
  let ev = new EV(evId);
  ev.vehicleId = vehicleId.toHexString();
  ev.owner = owner.toHexString();
  ev.batteryCapacity = batteryCapacity;
  ev.maxChargingRate = maxChargingRate;
  ev.maxDischargingRate = maxDischargingRate;
  ev.currentSoC = ZERO_BI;
  ev.isAvailable = true;
  ev.isRegistered = true;
  ev.totalEnergyProvided = ZERO_BD;
  ev.totalEnergyConsumed = ZERO_BD;
  ev.totalEarnings = ZERO_BD;
  ev.registeredAt = timestamp;
  ev.lastUpdatedAt = timestamp;
  ev.save();

  // Update prosumer type
  let prosumer = getOrCreateProsumer(owner, timestamp);
  prosumer.type = "EV_OWNER";
  prosumer.lastActivityAt = timestamp;
  prosumer.save();

  // Update protocol
  let protocol = getOrCreateProtocol();
  protocol.totalEVs = protocol.totalEVs + 1;
  protocol.lastUpdatedAt = timestamp;
  protocol.save();

  // Update daily stats
  let dailyStats = getOrCreateDailyStats(timestamp);
  dailyStats.activeEVs = dailyStats.activeEVs + 1;
  dailyStats.save();
}

export function handleEVUpdated(event: EVUpdatedEvent): void {
  let owner = event.params.owner;
  let vehicleId = event.params.vehicleId;
  let currentSoC = event.params.currentSoC;
  let timestamp = event.block.timestamp;

  let evId = vehicleId.toHexString();
  let ev = EV.load(evId);

  if (ev != null) {
    ev.currentSoC = currentSoC;
    ev.lastUpdatedAt = timestamp;
    ev.save();
  }
}

export function handleEVDeregistered(event: EVDeregisteredEvent): void {
  let owner = event.params.owner;
  let vehicleId = event.params.vehicleId;
  let timestamp = event.block.timestamp;

  let evId = vehicleId.toHexString();
  let ev = EV.load(evId);

  if (ev != null) {
    ev.isRegistered = false;
    ev.isAvailable = false;
    ev.lastUpdatedAt = timestamp;
    ev.save();

    // Update protocol
    let protocol = getOrCreateProtocol();
    protocol.totalEVs = protocol.totalEVs - 1;
    protocol.lastUpdatedAt = timestamp;
    protocol.save();
  }
}

// ============ Energy Delivery ============

export function handleEnergyDeliveryRecorded(event: EnergyDeliveryRecordedEvent): void {
  let vehicleId = event.params.vehicleId;
  let energyAmount = toDecimal(event.params.energyAmount);
  let isProviding = event.params.isProviding;
  let timestamp = event.block.timestamp;

  let evId = vehicleId.toHexString();
  let ev = EV.load(evId);

  if (ev != null) {
    if (isProviding) {
      // EV is providing energy to the grid (V2G discharge)
      ev.totalEnergyProvided = ev.totalEnergyProvided.plus(energyAmount);
    } else {
      // EV is consuming energy (charging)
      ev.totalEnergyConsumed = ev.totalEnergyConsumed.plus(energyAmount);
    }
    ev.lastUpdatedAt = timestamp;
    ev.save();

    // Update owner prosumer
    let ownerAddress = Address.fromString(ev.owner);
    let prosumer = getOrCreateProsumer(ownerAddress, timestamp);
    prosumer.totalVolume = prosumer.totalVolume.plus(energyAmount);
    prosumer.lastActivityAt = timestamp;
    prosumer.save();
  }
}
