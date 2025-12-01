import { ethers, network } from "hardhat";
import * as fs from "fs";
import * as path from "path";

interface DeploymentInfo {
  network: string;
  chainId: number;
  dynamicPricingAddress: string;
  priceOracleAddress: string;
  gridOracleAddress: string;
  adminAddress: string;
  transactionHash: string;
  blockNumber: number;
  timestamp: string;
  gasUsed: string;
}

async function main(): Promise<void> {
  console.log("\n🔷 SHAKTI Dynamic Pricing Deployment Script");
  console.log("=".repeat(50));

  // Get network info
  const networkName = network.name;
  const chainId = (await ethers.provider.getNetwork()).chainId;
  console.log(`\n📡 Network: ${networkName} (Chain ID: ${chainId})`);

  // Get deployer
  const [deployer] = await ethers.getSigners();
  console.log(`\n👤 Deployer: ${deployer.address}`);

  // Check balance
  const balance = await ethers.provider.getBalance(deployer.address);
  console.log(`💰 Balance: ${ethers.formatEther(balance)} ETH/MATIC`);

  if (balance === 0n) {
    throw new Error("Deployer has no funds. Please fund the account before deployment.");
  }

  // Load oracle deployments
  const deploymentsDir = path.join(__dirname, "..", "deployments");
  let priceOracleAddress: string;
  let gridOracleAddress: string;

  const oracleDeploymentFile = path.join(deploymentsDir, `${networkName}-oracles-deployment.json`);
  if (fs.existsSync(oracleDeploymentFile)) {
    const oracleDeployment = JSON.parse(fs.readFileSync(oracleDeploymentFile, "utf-8"));
    priceOracleAddress = oracleDeployment.priceOracleAddress;
    gridOracleAddress = oracleDeployment.gridOracleAddress;
    console.log(`\n📄 Found PriceOracle: ${priceOracleAddress}`);
    console.log(`📄 Found GridStatusOracle: ${gridOracleAddress}`);
  } else {
    console.log(`\n⚠️  No oracle deployment found. Deploying new oracles...`);

    // Deploy mock feeds
    const MockAggregator = await ethers.getContractFactory("MockAggregatorV3");
    const priceFeed = await MockAggregator.deploy(8, "IEX/INR Price", 500n * BigInt(1e8));
    await priceFeed.waitForDeployment();
    const frequencyFeed = await MockAggregator.deploy(3, "Grid Frequency", 50000);
    await frequencyFeed.waitForDeployment();

    console.log(`   Mock Price Feed: ${await priceFeed.getAddress()}`);
    console.log(`   Mock Frequency Feed: ${await frequencyFeed.getAddress()}`);

    // Deploy PriceOracle
    const PriceOracle = await ethers.getContractFactory("PriceOracle");
    const priceOracle = await PriceOracle.deploy(
      await priceFeed.getAddress(),
      ethers.ZeroAddress,
      deployer.address,
      200n * BigInt(1e8),  // Min: 2 INR
      1500n * BigInt(1e8)  // Max: 15 INR
    );
    await priceOracle.waitForDeployment();
    priceOracleAddress = await priceOracle.getAddress();
    console.log(`   PriceOracle: ${priceOracleAddress}`);

    // Deploy GridStatusOracle
    const GridStatusOracle = await ethers.getContractFactory("GridStatusOracle");
    const gridOracle = await GridStatusOracle.deploy(
      await frequencyFeed.getAddress(),
      deployer.address,
      50000
    );
    await gridOracle.waitForDeployment();
    gridOracleAddress = await gridOracle.getAddress();
    console.log(`   GridStatusOracle: ${gridOracleAddress}`);
  }

  console.log(`\n⚙️  Configuration:`);
  console.log(`   Price Oracle: ${priceOracleAddress}`);
  console.log(`   Grid Oracle: ${gridOracleAddress}`);

  // Deploy DynamicPricing
  console.log(`\n🚀 Deploying DynamicPricing...`);

  const DynamicPricing = await ethers.getContractFactory("DynamicPricing");

  // Estimate gas
  const deployTx = await DynamicPricing.getDeployTransaction(
    priceOracleAddress,
    gridOracleAddress,
    deployer.address
  );
  const estimatedGas = await ethers.provider.estimateGas(deployTx);
  const feeData = await ethers.provider.getFeeData();
  const gasPrice = feeData.gasPrice || 0n;

  console.log(`   Estimated Gas: ${estimatedGas.toString()}`);
  console.log(`   Gas Price: ${ethers.formatUnits(gasPrice, "gwei")} gwei`);
  console.log(`   Estimated Cost: ${ethers.formatEther(estimatedGas * gasPrice)} ETH/MATIC`);

  // Deploy
  const dynamicPricing = await DynamicPricing.deploy(
    priceOracleAddress,
    gridOracleAddress,
    deployer.address
  );

  console.log(`\n⏳ Waiting for deployment transaction...`);
  console.log(`   TX Hash: ${dynamicPricing.deploymentTransaction()?.hash}`);

  await dynamicPricing.waitForDeployment();
  const dynamicPricingAddress = await dynamicPricing.getAddress();

  // Get receipt
  const txHash = dynamicPricing.deploymentTransaction()?.hash;
  const receipt = txHash ? await ethers.provider.getTransactionReceipt(txHash) : null;

  console.log(`\n✅ DynamicPricing deployed successfully!`);
  console.log(`   Contract Address: ${dynamicPricingAddress}`);
  console.log(`   Block Number: ${receipt?.blockNumber}`);
  console.log(`   Gas Used: ${receipt?.gasUsed.toString()}`);

  // Verify deployment
  console.log(`\n🔍 Verifying deployment...`);

  const maxDailyChange = await dynamicPricing.maxDailyChange();
  const autoSeason = await dynamicPricing.autoSeasonDetection();

  console.log(`   Max Daily Change: ${Number(maxDailyChange) / 100}%`);
  console.log(`   Auto Season Detection: ${autoSeason}`);

  // Check multipliers
  console.log(`\n📊 Default Multipliers:`);

  // Demand
  const surplusMult = await dynamicPricing.demandMultipliers(0);
  const balancedMult = await dynamicPricing.demandMultipliers(2);
  const surgeMult = await dynamicPricing.demandMultipliers(5);
  console.log(`   Demand - Surplus: ${Number(surplusMult) / 100}%`);
  console.log(`   Demand - Balanced: ${Number(balancedMult) / 100}%`);
  console.log(`   Demand - Surge: ${Number(surgeMult) / 100}%`);

  // Time-of-use
  const offPeakMult = await dynamicPricing.timeOfUseMultipliers(0);
  const shoulderMult = await dynamicPricing.timeOfUseMultipliers(1);
  const peakMult = await dynamicPricing.timeOfUseMultipliers(2);
  console.log(`   ToU - Off-Peak: ${Number(offPeakMult) / 100}%`);
  console.log(`   ToU - Shoulder: ${Number(shoulderMult) / 100}%`);
  console.log(`   ToU - Peak: ${Number(peakMult) / 100}%`);

  // Seasonal
  const summerMult = await dynamicPricing.seasonalMultipliers(0);
  const monsoonMult = await dynamicPricing.seasonalMultipliers(1);
  const winterMult = await dynamicPricing.seasonalMultipliers(3);
  console.log(`   Season - Summer: ${Number(summerMult) / 100}%`);
  console.log(`   Season - Monsoon: ${Number(monsoonMult) / 100}%`);
  console.log(`   Season - Winter: ${Number(winterMult) / 100}%`);

  // Test price calculation
  console.log(`\n💰 Sample Price Calculations:`);

  const basePriceTest = 500n * BigInt(1e8); // 5 INR

  // Off-peak + Surplus
  const offPeakSurplus = await dynamicPricing.calculateDynamicPrice(basePriceTest, 3, 3000);
  console.log(`   Off-Peak + Surplus: ${Number(offPeakSurplus) / 1e8 / 100} INR/kWh`);

  // Standard + Balanced
  const stdBalanced = await dynamicPricing.calculateDynamicPrice(basePriceTest, 12, 10000);
  console.log(`   Standard + Balanced: ${Number(stdBalanced) / 1e8 / 100} INR/kWh`);

  // Peak + Surge
  const peakSurge = await dynamicPricing.calculateDynamicPrice(basePriceTest, 20, 25000);
  console.log(`   Peak + Surge: ${Number(peakSurge) / 1e8 / 100} INR/kWh`);

  // Initialize daily price if localhost
  if (networkName === "localhost" || networkName === "hardhat") {
    console.log(`\n🔧 Initializing daily price tracking...`);
    const OPERATOR_ROLE = await dynamicPricing.OPERATOR_ROLE();
    await dynamicPricing.grantRole(OPERATOR_ROLE, deployer.address);
    await dynamicPricing.resetDailyPrice();
    console.log(`   Daily price initialized`);
  }

  // Save deployment info
  if (!fs.existsSync(deploymentsDir)) {
    fs.mkdirSync(deploymentsDir, { recursive: true });
  }

  const deploymentInfo: DeploymentInfo = {
    network: networkName,
    chainId: Number(chainId),
    dynamicPricingAddress,
    priceOracleAddress,
    gridOracleAddress,
    adminAddress: deployer.address,
    transactionHash: txHash || "",
    blockNumber: receipt?.blockNumber || 0,
    timestamp: new Date().toISOString(),
    gasUsed: receipt?.gasUsed.toString() || "0",
  };

  const deploymentFile = path.join(deploymentsDir, `${networkName}-dynamic-pricing-deployment.json`);
  fs.writeFileSync(deploymentFile, JSON.stringify(deploymentInfo, null, 2));
  console.log(`\n💾 Deployment info saved to: ${deploymentFile}`);

  // Print verification command
  if (networkName === "polygonMumbai" || networkName === "polygonMainnet") {
    console.log(`\n📋 To verify on Polygonscan, run:`);
    console.log(`   npx hardhat verify --network ${networkName} ${dynamicPricingAddress} ${priceOracleAddress} ${gridOracleAddress} ${deployer.address}`);
  }

  // Print next steps
  console.log("\n" + "=".repeat(50));
  console.log("📝 Next Steps:");
  console.log("   1. Grant GOVERNANCE_ROLE to governance multisig");
  console.log("   2. Grant OPERATOR_ROLE to automation service");
  console.log("   3. Connect EnergyAuction to use DynamicPricing");
  console.log("   4. Set up Chainlink Automation for price updates");
  console.log("   5. Monitor and adjust multipliers based on market");
  console.log("=".repeat(50));
  console.log("🎉 Dynamic Pricing Deployment Complete!\n");

  return;
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("\n❌ Deployment failed:");
    console.error(error);
    process.exit(1);
  });
