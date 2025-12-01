/**
 * SHAKTI-CHAIN Deployment Script: EnergyAuction
 *
 * Deploys the McAfee double auction for energy trading.
 */

import { ethers, network } from "hardhat";
import { saveDeployment, getDeployer, loadDeployment, estimateGasWithBuffer } from "../utils/deployment-helpers";

async function main() {
  console.log("\n========================================");
  console.log("  Deploying EnergyAuction");
  console.log("  Network:", network.name);
  console.log("========================================\n");

  const deployer = await getDeployer();
  console.log("Deployer:", deployer.address);

  // Load dependencies
  const tokenDeployment = await loadDeployment("ShaktiToken");
  const registryDeployment = await loadDeployment("EnergyRegistry");

  if (!tokenDeployment) {
    throw new Error("ShaktiToken not deployed. Run 01-deploy-token.ts first.");
  }
  if (!registryDeployment) {
    throw new Error("EnergyRegistry not deployed. Run 03-deploy-registry.ts first.");
  }

  console.log("ShaktiToken address:", tokenDeployment.address);
  console.log("EnergyRegistry address:", registryDeployment.address);

  // Deploy EnergyAuction
  const EnergyAuction = await ethers.getContractFactory("EnergyAuction");

  // Constructor args: paymentToken, registry, admin, minPrice, maxPrice
  const minPrice = ethers.parseEther("0.001");  // 0.001 SHAKTI/kWh
  const maxPrice = ethers.parseEther("0.01");   // 0.01 SHAKTI/kWh
  const constructorArgs = [
    tokenDeployment.address,
    registryDeployment.address,
    deployer.address,
    minPrice,
    maxPrice,
  ];

  const deployTx = await EnergyAuction.getDeployTransaction(...constructorArgs);
  const estimatedGas = await estimateGasWithBuffer(deployTx);
  console.log("Estimated gas:", estimatedGas.toString());

  const energyAuction = await EnergyAuction.deploy(...constructorArgs, {
    gasLimit: estimatedGas,
  });

  await energyAuction.waitForDeployment();
  const auctionAddress = await energyAuction.getAddress();

  console.log("\nEnergyAuction deployed to:", auctionAddress);
  console.log("Transaction hash:", energyAuction.deploymentTransaction()?.hash);

  // Verify configuration
  const configMinPrice = await energyAuction.minPrice();
  const configMaxPrice = await energyAuction.maxPrice();
  const batchSize = await energyAuction.BATCH_SIZE();

  console.log("\nAuction Configuration:");
  console.log("  Min Price:", ethers.formatEther(configMinPrice), "SHAKTI/kWh");
  console.log("  Max Price:", ethers.formatEther(configMaxPrice), "SHAKTI/kWh");
  console.log("  Batch Size:", Number(batchSize), "orders");

  // Save deployment
  await saveDeployment("EnergyAuction", {
    address: auctionAddress,
    constructorArgs: [
      tokenDeployment.address,
      registryDeployment.address,
      deployer.address,
      minPrice.toString(),
      maxPrice.toString(),
    ],
    txHash: energyAuction.deploymentTransaction()?.hash,
    deployer: deployer.address,
    network: network.name,
    chainId: network.config.chainId,
    timestamp: new Date().toISOString(),
  });

  console.log("\n✅ EnergyAuction deployment complete!");

  return { energyAuction, address: auctionAddress };
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
