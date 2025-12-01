/**
 * SHAKTI-CHAIN Pause Status Verification Script
 *
 * Checks the pause status of all pausable contracts.
 *
 * Usage: npx hardhat run scripts/emergency/verify-pause.ts --network polygon
 */

import { ethers, network } from "hardhat";
import { loadDeployment } from "../utils/deployment-helpers";

const PAUSABLE_CONTRACTS = [
  "ShaktiToken",
  "StakingPool",
  "EnergyAuction",
  "EnergyEscrow",
  "EnergyVerification",
  "DynamicPricing",
];

async function main() {
  console.log("╔════════════════════════════════════════════════════════════╗");
  console.log("║              PAUSE STATUS VERIFICATION                     ║");
  console.log("╚════════════════════════════════════════════════════════════╝\n");

  console.log("Network:", network.name);
  console.log("Time:", new Date().toISOString());
  console.log("");

  console.log("Checking pause status...\n");

  const results: { name: string; address: string; status: string }[] = [];
  let pausedCount = 0;
  let activeCount = 0;

  for (const contractName of PAUSABLE_CONTRACTS) {
    try {
      const deployment = await loadDeployment(contractName);
      if (!deployment) {
        console.log(`${contractName}: NOT DEPLOYED`);
        results.push({ name: contractName, address: "N/A", status: "NOT_DEPLOYED" });
        continue;
      }

      const contract = await ethers.getContractAt(contractName, deployment.address);
      const isPaused = await contract.paused();

      const status = isPaused ? "PAUSED" : "ACTIVE";
      const emoji = isPaused ? "🔴" : "🟢";

      console.log(`${emoji} ${contractName}: ${status}`);
      results.push({ name: contractName, address: deployment.address, status });

      if (isPaused) {
        pausedCount++;
      } else {
        activeCount++;
      }
    } catch (error) {
      console.log(`❌ ${contractName}: ERROR - ${error}`);
      results.push({ name: contractName, address: "N/A", status: "ERROR" });
    }
  }

  // Summary
  console.log("\n════════════════════════════════════════════════════════════");
  console.log("SUMMARY");
  console.log("════════════════════════════════════════════════════════════\n");

  console.log(`Active Contracts:  ${activeCount}`);
  console.log(`Paused Contracts:  ${pausedCount}`);
  console.log(`Total:             ${PAUSABLE_CONTRACTS.length}`);

  if (pausedCount === PAUSABLE_CONTRACTS.length) {
    console.log("\n⚠️  ALL CONTRACTS ARE PAUSED");
  } else if (pausedCount > 0) {
    console.log("\n⚠️  SOME CONTRACTS ARE PAUSED");
  } else {
    console.log("\n✅ All contracts are active");
  }
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
