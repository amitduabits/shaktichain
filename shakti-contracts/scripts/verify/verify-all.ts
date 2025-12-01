/**
 * SHAKTI-CHAIN Contract Verification Script
 *
 * Verifies all deployed contracts on Polygonscan.
 */

import { run, network } from "hardhat";
import { loadAllDeployments, sleep, DeploymentInfo } from "../utils/deployment-helpers";

interface VerificationResult {
  contract: string;
  address: string;
  success: boolean;
  error?: string;
}

async function verifyContract(
  contractName: string,
  deployment: DeploymentInfo
): Promise<VerificationResult> {
  console.log(`\nVerifying ${contractName} at ${deployment.address}...`);

  try {
    await run("verify:verify", {
      address: deployment.address,
      constructorArguments: deployment.constructorArgs,
    });

    console.log(`✅ ${contractName} verified successfully!`);
    return { contract: contractName, address: deployment.address, success: true };
  } catch (error: any) {
    const message = error.message || String(error);

    // Check if already verified
    if (message.includes("Already Verified") || message.includes("already verified")) {
      console.log(`⏭️  ${contractName} already verified`);
      return { contract: contractName, address: deployment.address, success: true };
    }

    console.log(`❌ ${contractName} verification failed: ${message.slice(0, 100)}`);
    return { contract: contractName, address: deployment.address, success: false, error: message };
  }
}

async function main() {
  console.log("\n╔════════════════════════════════════════════════════════════╗");
  console.log("║           SHAKTI-CHAIN Contract Verification                ║");
  console.log("╚════════════════════════════════════════════════════════════╝\n");

  console.log("Network:", network.name);

  if (network.name === "hardhat" || network.name === "localhost") {
    console.log("\n⚠️  Cannot verify contracts on local network.");
    console.log("Deploy to a testnet and run verification again.");
    return;
  }

  // Load all deployments
  const deployments = await loadAllDeployments();

  if (Object.keys(deployments).length === 0) {
    throw new Error("No deployments found. Run deploy-all.ts first.");
  }

  console.log("Found", Object.keys(deployments).length, "contracts to verify");
  console.log("");

  const results: VerificationResult[] = [];

  // Verification order (dependencies first)
  const verificationOrder = [
    "ShaktiToken",
    "StakingPool",
    "EnergyRegistry",
    "PriceOracle",
    "DynamicPricing",
    "EnergyAuction",
    "EnergyEscrow",
    "Treasury",
    "ReputationSystem",
    "EnergyVerification",
    "ShaktiGovernor",
    "TimelockController",
  ];

  for (const contractName of verificationOrder) {
    const deployment = deployments[contractName];
    if (!deployment) {
      console.log(`⏭️  Skipping ${contractName} (not deployed)`);
      continue;
    }

    const result = await verifyContract(contractName, deployment);
    results.push(result);

    // Wait between verifications to avoid rate limiting
    await sleep(5000);
  }

  // Print summary
  console.log("\n╔════════════════════════════════════════════════════════════╗");
  console.log("║               Verification Summary                           ║");
  console.log("╚════════════════════════════════════════════════════════════╝\n");

  const successful = results.filter((r) => r.success);
  const failed = results.filter((r) => !r.success);

  console.log(`✅ Verified: ${successful.length}/${results.length}`);
  console.log(`❌ Failed: ${failed.length}/${results.length}`);
  console.log("");

  if (failed.length > 0) {
    console.log("Failed Verifications:");
    console.log("─".repeat(60));
    for (const result of failed) {
      console.log(`${result.contract}: ${result.error?.slice(0, 80)}`);
    }
    console.log("─".repeat(60));
  }

  // Generate verification links
  const explorerBase = getExplorerUrl();
  console.log("\n📋 Contract Links:");
  console.log("─".repeat(60));
  for (const result of results) {
    if (result.success) {
      console.log(`${result.contract.padEnd(25)} ${explorerBase}/address/${result.address}`);
    }
  }
  console.log("─".repeat(60));
}

function getExplorerUrl(): string {
  const explorers: Record<string, string> = {
    mumbai: "https://mumbai.polygonscan.com",
    amoy: "https://amoy.polygonscan.com",
    polygon: "https://polygonscan.com",
    mainnet: "https://etherscan.io",
    sepolia: "https://sepolia.etherscan.io",
  };

  return explorers[network.name] || `https://${network.name}.etherscan.io`;
}

if (require.main === module) {
  main()
    .then(() => process.exit(0))
    .catch((error) => {
      console.error(error);
      process.exit(1);
    });
}

export default main;
