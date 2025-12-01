/**
 * SHAKTI-CHAIN Deployment Script: EnergyVerification
 *
 * Deploys the energy verification contract for trade validation.
 */

import { ethers, network } from "hardhat";
import { saveDeployment, getDeployer, loadDeployment, estimateGasWithBuffer } from "../utils/deployment-helpers";

async function main() {
  console.log("\n========================================");
  console.log("  Deploying EnergyVerification");
  console.log("  Network:", network.name);
  console.log("========================================\n");

  const deployer = await getDeployer();
  console.log("Deployer:", deployer.address);

  // Deploy EnergyVerification
  const EnergyVerification = await ethers.getContractFactory("EnergyVerification");

  // Constructor args: admin only
  const constructorArgs = [deployer.address];

  const deployTx = await EnergyVerification.getDeployTransaction(...constructorArgs);
  const estimatedGas = await estimateGasWithBuffer(deployTx);
  console.log("Estimated gas:", estimatedGas.toString());

  const energyVerification = await EnergyVerification.deploy(...constructorArgs, {
    gasLimit: estimatedGas,
  });

  await energyVerification.waitForDeployment();
  const verificationAddress = await energyVerification.getAddress();

  console.log("\nEnergyVerification deployed to:", verificationAddress);
  console.log("Transaction hash:", energyVerification.deploymentTransaction()?.hash);

  // Verify configuration
  const deliveryWindow = await energyVerification.DELIVERY_WINDOW();
  const quantityTolerance = await energyVerification.QUANTITY_TOLERANCE();

  console.log("\nVerification Configuration:");
  console.log("  Delivery Window:", Number(deliveryWindow) / 3600, "hours");
  console.log("  Quantity Tolerance:", Number(quantityTolerance) / 100, "%");

  // Save deployment
  await saveDeployment("EnergyVerification", {
    address: verificationAddress,
    constructorArgs,
    txHash: energyVerification.deploymentTransaction()?.hash,
    deployer: deployer.address,
    network: network.name,
    chainId: network.config.chainId,
    timestamp: new Date().toISOString(),
  });

  console.log("\n✅ EnergyVerification deployment complete!");

  return { energyVerification, address: verificationAddress };
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
