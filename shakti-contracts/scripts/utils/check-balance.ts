/**
 * SHAKTI-CHAIN Utility: Check Wallet Balance
 */

import { ethers, network } from "hardhat";
import { loadAllDeployments } from "./deployment-helpers";

async function main() {
  console.log("\n========================================");
  console.log("  Wallet Balance Check");
  console.log("  Network:", network.name);
  console.log("========================================\n");

  const [deployer] = await ethers.getSigners();
  const balance = await ethers.provider.getBalance(deployer.address);

  console.log("Address:", deployer.address);
  console.log("MATIC Balance:", ethers.formatEther(balance), "MATIC");

  // Check SHAKTI balance if token is deployed
  try {
    const deployments = await loadAllDeployments();
    if (deployments.ShaktiToken) {
      const token = await ethers.getContractAt("ShaktiToken", deployments.ShaktiToken.address);
      const tokenBalance = await token.balanceOf(deployer.address);
      const symbol = await token.symbol();
      console.log(`${symbol} Balance:`, ethers.formatEther(tokenBalance), symbol);
    }
  } catch {
    // Token not deployed yet
  }

  // Estimate deployment cost
  const gasPrice = await ethers.provider.getFeeData();
  console.log("\nGas Info:");
  console.log("  Gas Price:", ethers.formatUnits(gasPrice.gasPrice || 0, "gwei"), "gwei");
  console.log("  Max Fee:", ethers.formatUnits(gasPrice.maxFeePerGas || 0, "gwei"), "gwei");

  // Estimated cost for full deployment
  const estimatedGas = BigInt(20_000_000); // ~20M gas for all contracts
  const estimatedCost = estimatedGas * (gasPrice.gasPrice || BigInt(35_000_000_000));
  console.log("\nEstimated Full Deployment Cost:", ethers.formatEther(estimatedCost), "MATIC");

  if (balance < estimatedCost) {
    console.log("\n⚠️  Warning: Balance may be insufficient for full deployment.");
    console.log("   Get more test MATIC from faucets.");
  } else {
    console.log("\n✅ Balance sufficient for deployment.");
  }
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
