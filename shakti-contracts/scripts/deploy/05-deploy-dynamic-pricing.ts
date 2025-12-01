/**
 * SHAKTI-CHAIN Deployment Script: DynamicPricing
 *
 * Deploys the dynamic pricing engine with demand/time-of-use modifiers.
 */

import { ethers, network } from "hardhat";
import { saveDeployment, getDeployer, loadDeployment, estimateGasWithBuffer } from "../utils/deployment-helpers";

async function main() {
  console.log("\n========================================");
  console.log("  Deploying DynamicPricing");
  console.log("  Network:", network.name);
  console.log("========================================\n");

  const deployer = await getDeployer();
  console.log("Deployer:", deployer.address);

  // Load dependencies
  const oracleDeployment = await loadDeployment("PriceOracle");
  if (!oracleDeployment) {
    throw new Error("PriceOracle not deployed. Run 04-deploy-oracle.ts first.");
  }
  console.log("PriceOracle address:", oracleDeployment.address);

  // Deploy mock grid oracle for testnet
  let gridOracle: string;

  if (network.name === "localhost" || network.name === "hardhat" || network.name === "amoy") {
    console.log("Deploying MockFrequencyFeed for testnet...");
    const MockFrequencyFeed = await ethers.getContractFactory("MockFrequencyFeed");
    const mockGrid = await MockFrequencyFeed.deploy();
    await mockGrid.waitForDeployment();
    gridOracle = await mockGrid.getAddress();
    console.log("MockFrequencyFeed deployed to:", gridOracle);

    // Save mock deployment
    await saveDeployment("MockGridOracle", {
      address: gridOracle,
      constructorArgs: [],
      deployer: deployer.address,
      network: network.name,
      chainId: network.config.chainId,
      timestamp: new Date().toISOString(),
    });
  } else {
    throw new Error("Mainnet deployment requires Grid Oracle address.");
  }

  // Deploy DynamicPricing
  const DynamicPricing = await ethers.getContractFactory("DynamicPricing");

  // Constructor args: priceOracle, gridOracle, admin
  const constructorArgs = [oracleDeployment.address, gridOracle, deployer.address];

  const deployTx = await DynamicPricing.getDeployTransaction(...constructorArgs);
  const estimatedGas = await estimateGasWithBuffer(deployTx);
  console.log("Estimated gas:", estimatedGas.toString());

  const dynamicPricing = await DynamicPricing.deploy(...constructorArgs, {
    gasLimit: estimatedGas,
  });

  await dynamicPricing.waitForDeployment();
  const pricingAddress = await dynamicPricing.getAddress();

  console.log("\nDynamicPricing deployed to:", pricingAddress);
  console.log("Transaction hash:", dynamicPricing.deploymentTransaction()?.hash);

  // Verify configuration
  console.log("\nPricing Configuration:");
  console.log("  Price Oracle:", oracleDeployment.address);
  console.log("  Grid Oracle:", gridOracle);

  // Save deployment
  await saveDeployment("DynamicPricing", {
    address: pricingAddress,
    constructorArgs: [oracleDeployment.address, gridOracle, deployer.address],
    txHash: dynamicPricing.deploymentTransaction()?.hash,
    deployer: deployer.address,
    network: network.name,
    chainId: network.config.chainId,
    timestamp: new Date().toISOString(),
  });

  console.log("\n✅ DynamicPricing deployment complete!");

  return { dynamicPricing, address: pricingAddress };
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
