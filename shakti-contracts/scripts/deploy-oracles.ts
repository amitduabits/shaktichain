import { ethers, network } from "hardhat";
import * as fs from "fs";
import * as path from "path";

interface OracleDeploymentInfo {
  network: string;
  chainId: number;
  priceOracleAddress: string;
  gridOracleAddress: string;
  mockPriceFeedAddress: string;
  mockFrequencyFeedAddress: string;
  adminAddress: string;
  transactionHashes: {
    priceOracle: string;
    gridOracle: string;
  };
  timestamp: string;
}

// Chainlink Price Feed addresses (Polygon)
const CHAINLINK_FEEDS = {
  // Note: These are placeholder addresses. In production, use actual Chainlink feeds
  // or Chainlink Functions for custom IEX data
  polygonMainnet: {
    // No direct electricity price feed - would use Chainlink Functions
    priceFeed: ethers.ZeroAddress,
    frequencyFeed: ethers.ZeroAddress,
  },
  polygonMumbai: {
    // Testnet - use mock feeds
    priceFeed: ethers.ZeroAddress,
    frequencyFeed: ethers.ZeroAddress,
  },
  localhost: {
    priceFeed: ethers.ZeroAddress,
    frequencyFeed: ethers.ZeroAddress,
  },
  hardhat: {
    priceFeed: ethers.ZeroAddress,
    frequencyFeed: ethers.ZeroAddress,
  },
};

async function main(): Promise<void> {
  console.log("\n🔷 SHAKTI Oracle Deployment Script");
  console.log("=".repeat(50));

  // Get network info
  const networkName = network.name as keyof typeof CHAINLINK_FEEDS;
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

  // Configuration
  const PRICE_PRECISION = BigInt(1e8);
  const MIN_PRICE = 200n * PRICE_PRECISION;  // 2 INR/kWh
  const MAX_PRICE = 1500n * PRICE_PRECISION; // 15 INR/kWh
  const SAMPLE_PRICE = 500n * PRICE_PRECISION; // 5 INR/kWh initial
  const PEAK_CAPACITY = 50000n; // 50,000 MW

  console.log(`\n⚙️  Configuration:`);
  console.log(`   Min Price: 2 INR/kWh`);
  console.log(`   Max Price: 15 INR/kWh`);
  console.log(`   Peak Grid Capacity: ${PEAK_CAPACITY} MW`);

  // Deploy mock feeds for testing (or use real feeds in production)
  let priceFeedAddress: string;
  let frequencyFeedAddress: string;

  const feedConfig = CHAINLINK_FEEDS[networkName] || CHAINLINK_FEEDS.localhost;

  if (feedConfig.priceFeed === ethers.ZeroAddress) {
    console.log(`\n📊 Deploying Mock Price Feed...`);
    const MockAggregator = await ethers.getContractFactory("MockAggregatorV3");
    const mockPriceFeed = await MockAggregator.deploy(
      8,
      "IEX/INR Electricity Price",
      SAMPLE_PRICE
    );
    await mockPriceFeed.waitForDeployment();
    priceFeedAddress = await mockPriceFeed.getAddress();
    console.log(`   Mock Price Feed: ${priceFeedAddress}`);
  } else {
    priceFeedAddress = feedConfig.priceFeed;
    console.log(`\n📊 Using Chainlink Price Feed: ${priceFeedAddress}`);
  }

  if (feedConfig.frequencyFeed === ethers.ZeroAddress) {
    console.log(`\n📊 Deploying Mock Frequency Feed...`);
    const MockAggregator = await ethers.getContractFactory("MockAggregatorV3");
    const mockFreqFeed = await MockAggregator.deploy(
      3,
      "Grid Frequency mHz",
      50000 // 50.000 Hz
    );
    await mockFreqFeed.waitForDeployment();
    frequencyFeedAddress = await mockFreqFeed.getAddress();
    console.log(`   Mock Frequency Feed: ${frequencyFeedAddress}`);
  } else {
    frequencyFeedAddress = feedConfig.frequencyFeed;
    console.log(`\n📊 Using Chainlink Frequency Feed: ${frequencyFeedAddress}`);
  }

  // Deploy PriceOracle
  console.log(`\n🚀 Deploying PriceOracle...`);

  const PriceOracle = await ethers.getContractFactory("PriceOracle");
  const priceOracle = await PriceOracle.deploy(
    priceFeedAddress,
    ethers.ZeroAddress, // No backup feed initially
    deployer.address,
    MIN_PRICE,
    MAX_PRICE
  );

  console.log(`   TX Hash: ${priceOracle.deploymentTransaction()?.hash}`);
  await priceOracle.waitForDeployment();
  const priceOracleAddress = await priceOracle.getAddress();

  console.log(`   ✅ PriceOracle deployed: ${priceOracleAddress}`);

  // Deploy GridStatusOracle
  console.log(`\n🚀 Deploying GridStatusOracle...`);

  const GridStatusOracle = await ethers.getContractFactory("GridStatusOracle");
  const gridOracle = await GridStatusOracle.deploy(
    frequencyFeedAddress,
    deployer.address,
    PEAK_CAPACITY
  );

  console.log(`   TX Hash: ${gridOracle.deploymentTransaction()?.hash}`);
  await gridOracle.waitForDeployment();
  const gridOracleAddress = await gridOracle.getAddress();

  console.log(`   ✅ GridStatusOracle deployed: ${gridOracleAddress}`);

  // Verify deployments
  console.log(`\n🔍 Verifying deployments...`);

  // PriceOracle verification
  const storedMinPrice = await priceOracle.minPrice();
  const storedMaxPrice = await priceOracle.maxPrice();
  console.log(`   PriceOracle Min Price: ${storedMinPrice / PRICE_PRECISION} INR/kWh`);
  console.log(`   PriceOracle Max Price: ${storedMaxPrice / PRICE_PRECISION} INR/kWh`);

  // GridStatusOracle verification
  const storedCapacity = await gridOracle.peakCapacity();
  console.log(`   GridOracle Peak Capacity: ${storedCapacity} MW`);

  // Check default multipliers
  console.log(`\n📈 Hour Multipliers (IST):`);
  console.log(`   Off-peak (00-06): ${await priceOracle.hourMultipliers(3)} / 10000`);
  console.log(`   Standard (06-18): ${await priceOracle.hourMultipliers(12)} / 10000`);
  console.log(`   Peak (18-22): ${await priceOracle.hourMultipliers(20)} / 10000`);

  // Test oracle functions
  console.log(`\n🧪 Testing oracle functions...`);

  // Get spot price
  const [spotPrice, timestamp] = await priceOracle.getSpotPrice();
  console.log(`   Spot Price: ${spotPrice / PRICE_PRECISION} INR/kWh`);

  // Get effective price at different hours
  const effectivePeak = await priceOracle.getEffectivePrice(20);
  const effectiveOffPeak = await priceOracle.getEffectivePrice(3);
  console.log(`   Effective Price (peak): ${effectivePeak / PRICE_PRECISION} INR/kWh`);
  console.log(`   Effective Price (off-peak): ${effectiveOffPeak / PRICE_PRECISION} INR/kWh`);

  // Get grid status
  const gridStatus = await gridOracle.getFullStatus();
  console.log(`   Grid Frequency: ${Number(gridStatus.frequency) / 1000} Hz`);
  console.log(`   Demand Level: ${["LOW", "NORMAL", "HIGH", "CRITICAL"][gridStatus.demandLevel]}`);
  console.log(`   Grid Condition: ${["STABLE", "UNDER_FREQ", "OVER_FREQ", "STRESSED", "EMERGENCY"][gridStatus.condition]}`);

  // Save deployment info
  const deploymentsDir = path.join(__dirname, "..", "deployments");
  if (!fs.existsSync(deploymentsDir)) {
    fs.mkdirSync(deploymentsDir, { recursive: true });
  }

  const deploymentInfo: OracleDeploymentInfo = {
    network: networkName,
    chainId: Number(chainId),
    priceOracleAddress,
    gridOracleAddress,
    mockPriceFeedAddress: priceFeedAddress,
    mockFrequencyFeedAddress: frequencyFeedAddress,
    adminAddress: deployer.address,
    transactionHashes: {
      priceOracle: priceOracle.deploymentTransaction()?.hash || "",
      gridOracle: gridOracle.deploymentTransaction()?.hash || "",
    },
    timestamp: new Date().toISOString(),
  };

  const deploymentFile = path.join(deploymentsDir, `${networkName}-oracles-deployment.json`);
  fs.writeFileSync(deploymentFile, JSON.stringify(deploymentInfo, null, 2));
  console.log(`\n💾 Deployment info saved to: ${deploymentFile}`);

  // Print verification commands
  if (networkName === "polygonMumbai" || networkName === "polygonMainnet") {
    console.log(`\n📋 To verify on Polygonscan, run:`);
    console.log(`   npx hardhat verify --network ${networkName} ${priceOracleAddress} ${priceFeedAddress} ${ethers.ZeroAddress} ${deployer.address} ${MIN_PRICE} ${MAX_PRICE}`);
    console.log(`   npx hardhat verify --network ${networkName} ${gridOracleAddress} ${frequencyFeedAddress} ${deployer.address} ${PEAK_CAPACITY}`);
  }

  // Print next steps
  console.log("\n" + "=".repeat(50));
  console.log("📝 Next Steps:");
  console.log("   1. Grant PRICE_UPDATER_ROLE to Chainlink Automation/Functions");
  console.log("   2. Grant GRID_UPDATER_ROLE to grid monitoring service");
  console.log("   3. Configure EnergyAuction to use PriceOracle");
  console.log("   4. Set up Chainlink Functions for IEX price feed");
  console.log("   5. Connect grid frequency monitoring to GridStatusOracle");
  console.log("=".repeat(50));
  console.log("🎉 Oracle Deployment Complete!\n");

  return;
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("\n❌ Deployment failed:");
    console.error(error);
    process.exit(1);
  });
