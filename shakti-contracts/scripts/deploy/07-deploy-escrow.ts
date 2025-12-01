/**
 * SHAKTI-CHAIN Deployment Script: EnergyEscrow
 *
 * Deploys the escrow contract for secure trade settlement.
 */

import { ethers, network } from "hardhat";
import { saveDeployment, getDeployer, loadDeployment, estimateGasWithBuffer } from "../utils/deployment-helpers";

async function main() {
  console.log("\n========================================");
  console.log("  Deploying EnergyEscrow");
  console.log("  Network:", network.name);
  console.log("========================================\n");

  const deployer = await getDeployer();
  console.log("Deployer:", deployer.address);

  // Load dependencies
  const tokenDeployment = await loadDeployment("ShaktiToken");
  if (!tokenDeployment) {
    throw new Error("ShaktiToken not deployed. Run 01-deploy-token.ts first.");
  }
  console.log("ShaktiToken address:", tokenDeployment.address);

  // Deploy EnergyEscrow
  const EnergyEscrow = await ethers.getContractFactory("EnergyEscrow");

  // Constructor args: paymentToken, treasury, admin, platformFee (basis points), feeBurn (basis points)
  // 2% platform fee, 30% of fee burned
  const platformFee = 200;  // 2%
  const feeBurn = 3000;     // 30% of fee burned
  const constructorArgs = [
    tokenDeployment.address,
    deployer.address, // treasury (will be updated later)
    deployer.address, // admin
    platformFee,
    feeBurn,
  ];

  const deployTx = await EnergyEscrow.getDeployTransaction(...constructorArgs);
  const estimatedGas = await estimateGasWithBuffer(deployTx);
  console.log("Estimated gas:", estimatedGas.toString());

  const energyEscrow = await EnergyEscrow.deploy(...constructorArgs, {
    gasLimit: estimatedGas,
  });

  await energyEscrow.waitForDeployment();
  const escrowAddress = await energyEscrow.getAddress();

  console.log("\nEnergyEscrow deployed to:", escrowAddress);
  console.log("Transaction hash:", energyEscrow.deploymentTransaction()?.hash);

  // Verify configuration
  const configPlatformFee = await energyEscrow.platformFeePercentage();
  const configFeeBurn = await energyEscrow.feeBurnPercentage();
  const disputeWindow = await energyEscrow.DISPUTE_WINDOW();

  console.log("\nEscrow Configuration:");
  console.log("  Platform Fee:", Number(configPlatformFee) / 100, "%");
  console.log("  Fee Burn Rate:", Number(configFeeBurn) / 100, "%");
  console.log("  Dispute Window:", Number(disputeWindow) / 3600, "hours");

  // Save deployment
  await saveDeployment("EnergyEscrow", {
    address: escrowAddress,
    constructorArgs,
    txHash: energyEscrow.deploymentTransaction()?.hash,
    deployer: deployer.address,
    network: network.name,
    chainId: network.config.chainId,
    timestamp: new Date().toISOString(),
  });

  console.log("\n✅ EnergyEscrow deployment complete!");

  return { energyEscrow, address: escrowAddress };
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
