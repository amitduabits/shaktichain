/**
 * SHAKTI-CHAIN Unpause Script
 *
 * Unpauses all paused contracts after incident resolution.
 * Requires PAUSER_ROLE on all contracts.
 *
 * Usage: npx hardhat run scripts/emergency/unpause-all.ts --network polygon
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
  console.log("║              UNPAUSE - ALL CONTRACTS                       ║");
  console.log("╚════════════════════════════════════════════════════════════╝\n");

  console.log("Network:", network.name);
  console.log("Time:", new Date().toISOString());

  const [signer] = await ethers.getSigners();
  console.log("Executing as:", signer.address);
  console.log("");

  // Safety confirmation for mainnet
  if (network.name === "polygon") {
    console.log("⚠️  WARNING: You are about to unpause contracts on MAINNET!");
    console.log("Make sure:");
    console.log("  1. The incident has been fully resolved");
    console.log("  2. Fix has been deployed and verified");
    console.log("  3. Team approval obtained (3/5 multisig)");
    console.log("");
  }

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

      // Check if already unpaused
      const isPaused = await contract.paused();
      if (!isPaused) {
        console.log(`${contractName}: Already ACTIVE`);
        results.push({ name: contractName, status: "ALREADY_ACTIVE" });
        continue;
      }

      // Check if signer has PAUSER_ROLE
      const PAUSER_ROLE = await contract.PAUSER_ROLE();
      const hasRole = await contract.hasRole(PAUSER_ROLE, signer.address);
      if (!hasRole) {
        console.log(`${contractName}: NO PAUSER_ROLE - Cannot unpause`);
        results.push({ name: contractName, status: "NO_ROLE" });
        continue;
      }

      // Unpause the contract
      console.log(`Unpausing ${contractName}...`);
      const tx = await contract.unpause();
      await tx.wait();
      console.log(`${contractName}: ACTIVE (tx: ${tx.hash})`);
      results.push({ name: contractName, status: "UNPAUSED", txHash: tx.hash });
    } catch (error) {
      console.log(`${contractName}: ERROR - ${error}`);
      results.push({ name: contractName, status: "ERROR" });
    }
  }

  // Summary
  console.log("\n════════════════════════════════════════════════════════════");
  console.log("UNPAUSE SUMMARY");
  console.log("════════════════════════════════════════════════════════════\n");

  console.log("| Contract             | Status         |");
  console.log("|----------------------|----------------|");
  for (const result of results) {
    console.log(`| ${result.name.padEnd(20)} | ${result.status.padEnd(14)} |`);
  }

  const activeCount = results.filter((r) => r.status === "UNPAUSED" || r.status === "ALREADY_ACTIVE").length;
  const failedCount = results.filter((r) => r.status === "ERROR" || r.status === "NO_ROLE").length;

  console.log(`\nActive: ${activeCount}/${PAUSABLE_CONTRACTS.length}`);
  if (failedCount > 0) {
    console.log(`\n⚠️  WARNING: ${failedCount} contract(s) could not be unpaused!`);
  }

  console.log("\n✅ Unpause complete.");
  console.log("\nNext steps:");
  console.log("1. Monitor contracts closely for 24 hours");
  console.log("2. Verify all functionality working");
  console.log("3. Update status page and notify users");
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
