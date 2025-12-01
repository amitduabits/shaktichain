/**
 * SHAKTI-CHAIN Emergency Pause Script
 *
 * Pauses all pausable contracts in case of emergency.
 * Requires PAUSER_ROLE on all contracts.
 *
 * Usage: npx hardhat run scripts/emergency/pause-all.ts --network polygon
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
  console.log("║              EMERGENCY PAUSE - ALL CONTRACTS               ║");
  console.log("╚════════════════════════════════════════════════════════════╝\n");

  console.log("Network:", network.name);
  console.log("Time:", new Date().toISOString());

  const [signer] = await ethers.getSigners();
  console.log("Executing as:", signer.address);
  console.log("");

  const results: { name: string; status: string; txHash?: string }[] = [];

  for (const contractName of PAUSABLE_CONTRACTS) {
    try {
      const deployment = await loadDeployment(contractName);
      if (!deployment) {
        console.log(`${contractName}: NOT DEPLOYED - Skipping`);
        results.push({ name: contractName, status: "NOT_DEPLOYED" });
        continue;
      }

      const contract = await ethers.getContractAt(contractName, deployment.address);

      // Check if already paused
      const isPaused = await contract.paused();
      if (isPaused) {
        console.log(`${contractName}: Already PAUSED`);
        results.push({ name: contractName, status: "ALREADY_PAUSED" });
        continue;
      }

      // Check if signer has PAUSER_ROLE
      const PAUSER_ROLE = await contract.PAUSER_ROLE();
      const hasRole = await contract.hasRole(PAUSER_ROLE, signer.address);
      if (!hasRole) {
        console.log(`${contractName}: NO PAUSER_ROLE - Cannot pause`);
        results.push({ name: contractName, status: "NO_ROLE" });
        continue;
      }

      // Pause the contract
      console.log(`Pausing ${contractName}...`);
      const tx = await contract.pause();
      await tx.wait();
      console.log(`${contractName}: PAUSED (tx: ${tx.hash})`);
      results.push({ name: contractName, status: "PAUSED", txHash: tx.hash });
    } catch (error) {
      console.log(`${contractName}: ERROR - ${error}`);
      results.push({ name: contractName, status: "ERROR" });
    }
  }

  // Summary
  console.log("\n════════════════════════════════════════════════════════════");
  console.log("PAUSE SUMMARY");
  console.log("════════════════════════════════════════════════════════════\n");

  console.log("| Contract             | Status         |");
  console.log("|----------------------|----------------|");
  for (const result of results) {
    console.log(`| ${result.name.padEnd(20)} | ${result.status.padEnd(14)} |`);
  }

  const pausedCount = results.filter((r) => r.status === "PAUSED" || r.status === "ALREADY_PAUSED").length;
  const failedCount = results.filter((r) => r.status === "ERROR" || r.status === "NO_ROLE").length;

  console.log(`\nPaused: ${pausedCount}/${PAUSABLE_CONTRACTS.length}`);
  if (failedCount > 0) {
    console.log(`\n⚠️  WARNING: ${failedCount} contract(s) could not be paused!`);
  }

  console.log("\n✅ Emergency pause complete.");
  console.log("\nNext steps:");
  console.log("1. Notify the team");
  console.log("2. Begin incident investigation");
  console.log("3. See INCIDENT-RESPONSE.md for procedures");
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
