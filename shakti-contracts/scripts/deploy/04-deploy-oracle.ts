/**
 * SHAKTI-CHAIN Deployment Script: PriceOracle
 *
 * Deploys the price oracle with Chainlink integration support.
 */

import { ethers, network } from "hardhat";
import { saveDeployment, getDeployer, estimateGasWithBuffer } from "../utils/deployment-helpers";

async function main() {
  console.log("\n========================================");
  console.log("  Deploying PriceOracle");
  console.log("  Network:", network.name);
  console.log("========================================\n");

  const deployer = await getDeployer();
  console.log("Deployer:", deployer.address);

  // For testnet/localhost, deploy a mock Chainlink price feed
  let primaryFeed: string;
  const backupFeed = ethers.ZeroAddress;

  if (network.name === "localhost" || network.name === "hardhat" || network.name === "amoy") {
    console.log("Deploying MockAggregatorV3 for testnet...");
    const MockAggregator = await ethers.getContractFactory("MockAggregatorV3");
    // Constructor: decimals, description, initialAnswer
    // Initial price: 5 INR per kWh = 5 * 1e8 (8 decimals like Chainlink)
    const decimals = 8;
    const description = "IEX/INR Electricity Price";
    const initialPrice = 5 * 1e8;
    const mock = await MockAggregator.deploy(decimals, description, initialPrice);
    await mock.waitForDeployment();
    primaryFeed = await mock.getAddress();
    console.log("MockAggregatorV3 deployed to:", primaryFeed);

    // Save mock deployment
    await saveDeployment("MockPriceFeed", {
      address: primaryFeed,
      constructorArgs: [decimals, description, initialPrice],
      deployer: deployer.address,
      network: network.name,
      chainId: network.config.chainId,
      timestamp: new Date().toISOString(),
    });
  } else {
    // For mainnet, use actual Chainlink feed addresses
    // This should be configured via environment variables
    throw new Error("Mainnet deployment requires Chainlink price feed address. Set CHAINLINK_PRICE_FEED env var.");
  }

  // Deploy PriceOracle
  const PriceOracle = await ethers.getContractFactory("PriceOracle");

  // Constructor args: primaryFeed, backupFeed, admin, minPrice, maxPrice
  // Prices in 8 decimal format (like Chainlink)
  const minPrice = 1 * 1e8;   // 1 INR/kWh
  const maxPrice = 20 * 1e8;  // 20 INR/kWh
  const constructorArgs = [primaryFeed, backupFeed, deployer.address, minPrice, maxPrice];

  const deployTx = await PriceOracle.getDeployTransaction(...constructorArgs);
  const estimatedGas = await estimateGasWithBuffer(deployTx);
  console.log("Estimated gas:", estimatedGas.toString());

  const priceOracle = await PriceOracle.deploy(...constructorArgs, {
    gasLimit: estimatedGas,
  });

  await priceOracle.waitForDeployment();
  const oracleAddress = await priceOracle.getAddress();

  console.log("\nPriceOracle deployed to:", oracleAddress);
  console.log("Transaction hash:", priceOracle.deploymentTransaction()?.hash);

  // Verify configuration
  const minPriceSet = await priceOracle.minPrice();
  const maxPriceSet = await priceOracle.maxPrice();

  console.log("\nOracle Configuration:");
  console.log("  Min Price:", Number(minPriceSet) / 1e8, "INR/kWh");
  console.log("  Max Price:", Number(maxPriceSet) / 1e8, "INR/kWh");
  console.log("  Primary Feed:", primaryFeed);
  console.log("  Backup Feed:", backupFeed === ethers.ZeroAddress ? "None" : backupFeed);

  // Save deployment
  await saveDeployment("PriceOracle", {
    address: oracleAddress,
    constructorArgs: [primaryFeed, backupFeed, deployer.address, minPrice, maxPrice],
    txHash: priceOracle.deploymentTransaction()?.hash,
    deployer: deployer.address,
    network: network.name,
    chainId: network.config.chainId,
    timestamp: new Date().toISOString(),
  });

  console.log("\n✅ PriceOracle deployment complete!");

  return { priceOracle, address: oracleAddress };
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
