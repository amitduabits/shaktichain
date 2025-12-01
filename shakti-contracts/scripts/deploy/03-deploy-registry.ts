/**
 * SHAKTI-CHAIN Deployment Script: EnergyRegistry
 *
 * Deploys the prosumer registry for energy providers and consumers.
 */

import { ethers, network } from "hardhat";
import { saveDeployment, getDeployer, estimateGasWithBuffer } from "../utils/deployment-helpers";

async function main() {
  console.log("\n========================================");
  console.log("  Deploying EnergyRegistry");
  console.log("  Network:", network.name);
  console.log("========================================\n");

  const deployer = await getDeployer();
  console.log("Deployer:", deployer.address);

  // Deploy EnergyRegistry
  const EnergyRegistry = await ethers.getContractFactory("EnergyRegistry");

  // Constructor args: admin
  const constructorArgs = [deployer.address];

  const deployTx = await EnergyRegistry.getDeployTransaction(...constructorArgs);
  const estimatedGas = await estimateGasWithBuffer(deployTx);
  console.log("Estimated gas:", estimatedGas.toString());

  const energyRegistry = await EnergyRegistry.deploy(...constructorArgs, {
    gasLimit: estimatedGas,
  });

  await energyRegistry.waitForDeployment();
  const registryAddress = await energyRegistry.getAddress();

  console.log("\nEnergyRegistry deployed to:", registryAddress);
  console.log("Transaction hash:", energyRegistry.deploymentTransaction()?.hash);

  // Verify configuration
  const maxEVsPerProsumer = await energyRegistry.MAX_EVS_PER_PROSUMER();

  console.log("\nRegistry Configuration:");
  console.log("  Max EVs per Prosumer:", Number(maxEVsPerProsumer));

  // Save deployment
  await saveDeployment("EnergyRegistry", {
    address: registryAddress,
    constructorArgs,
    txHash: energyRegistry.deploymentTransaction()?.hash,
    deployer: deployer.address,
    network: network.name,
    chainId: network.config.chainId,
    timestamp: new Date().toISOString(),
  });

  console.log("\n✅ EnergyRegistry deployment complete!");

  return { energyRegistry, address: registryAddress };
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
