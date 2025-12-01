import { ethers, upgrades, network } from "hardhat";
import * as fs from "fs";
import * as path from "path";

interface UpgradeInfo {
  network: string;
  chainId: number;
  contract: string;
  proxy: string;
  oldImplementation: string;
  newImplementation: string;
  upgrader: string;
  timestamp: string;
  transactionHash: string;
  blockNumber: number;
}

/**
 * Upgrade EnergyAuctionUpgradeable to a new implementation
 *
 * Usage:
 *   npx hardhat run scripts/upgrade-auction.ts --network <network>
 *
 * Prerequisites:
 *   1. Deploy the proxy first using deploy-upgradeable.ts
 *   2. Ensure caller has UPGRADER_ROLE
 *   3. Create a new version of the contract (e.g., EnergyAuctionUpgradeableV2)
 */
async function main(): Promise<void> {
  console.log("\n🔷 SHAKTI-CHAIN Contract Upgrade Script");
  console.log("=".repeat(60));
  console.log("Upgrading: EnergyAuctionUpgradeable");
  console.log("=".repeat(60));

  // Get network info
  const networkName = network.name;
  const chainId = (await ethers.provider.getNetwork()).chainId;
  console.log(`\n📡 Network: ${networkName} (Chain ID: ${chainId})`);

  // Get upgrader
  const [upgrader] = await ethers.getSigners();
  console.log(`👤 Upgrader: ${upgrader.address}`);

  // Load existing deployment
  const deploymentsDir = path.join(__dirname, "..", "deployments");
  const deploymentFile = path.join(deploymentsDir, `${networkName}-upgradeable-deployment.json`);

  if (!fs.existsSync(deploymentFile)) {
    throw new Error(`No deployment found at ${deploymentFile}. Run deploy-upgradeable.ts first.`);
  }

  const deployment = JSON.parse(fs.readFileSync(deploymentFile, "utf-8"));
  const proxyAddress = deployment.contracts.EnergyAuctionUpgradeable.proxy;
  const oldImplAddress = deployment.contracts.EnergyAuctionUpgradeable.implementation;

  console.log(`\n📋 Current Deployment:`);
  console.log(`   Proxy Address: ${proxyAddress}`);
  console.log(`   Current Implementation: ${oldImplAddress}`);

  // Verify upgrader has UPGRADER_ROLE
  const auctionProxy = await ethers.getContractAt("EnergyAuctionUpgradeable", proxyAddress);
  const UPGRADER_ROLE = await auctionProxy.UPGRADER_ROLE();
  const hasRole = await auctionProxy.hasRole(UPGRADER_ROLE, upgrader.address);

  if (!hasRole) {
    throw new Error(`Account ${upgrader.address} does not have UPGRADER_ROLE. Cannot upgrade.`);
  }
  console.log(`   ✅ Upgrader has UPGRADER_ROLE`);

  // Pre-upgrade checks
  console.log("\n🔍 Pre-Upgrade Validation...");

  // Read current state (for verification after upgrade)
  const currentRoundId = await auctionProxy.currentRoundId();
  const minPrice = await auctionProxy.minPrice();
  const maxPrice = await auctionProxy.maxPrice();

  console.log(`   Current Round ID: ${currentRoundId}`);
  console.log(`   Min Price: ${ethers.formatEther(minPrice)} INR/Wh`);
  console.log(`   Max Price: ${ethers.formatEther(maxPrice)} INR/Wh`);

  // Validate storage layout compatibility
  console.log("\n📦 Validating storage layout compatibility...");

  // Note: In production, you'd have a new contract version like EnergyAuctionUpgradeableV2
  // For this example, we're upgrading to the same contract (which verifies the process works)
  const NewImplementation = await ethers.getContractFactory("EnergyAuctionUpgradeable");

  // Use OpenZeppelin's validateUpgrade to check storage compatibility
  // This will throw if there are storage layout issues
  await upgrades.validateUpgrade(proxyAddress, NewImplementation, {
    kind: "uups",
  });
  console.log(`   ✅ Storage layout is compatible`);

  // Perform the upgrade
  console.log("\n🚀 Performing upgrade...");

  const upgradedProxy = await upgrades.upgradeProxy(proxyAddress, NewImplementation, {
    kind: "uups",
  });
  await upgradedProxy.waitForDeployment();

  // Get new implementation address
  const newImplAddress = await upgrades.erc1967.getImplementationAddress(proxyAddress);

  console.log(`   ✅ Upgrade successful!`);
  console.log(`   New Implementation: ${newImplAddress}`);

  // Post-upgrade verification
  console.log("\n🔍 Post-Upgrade Verification...");

  // Verify state is preserved
  const postRoundId = await auctionProxy.currentRoundId();
  const postMinPrice = await auctionProxy.minPrice();
  const postMaxPrice = await auctionProxy.maxPrice();

  const statePreserved =
    currentRoundId === postRoundId &&
    minPrice === postMinPrice &&
    maxPrice === postMaxPrice;

  if (!statePreserved) {
    console.error("   ❌ WARNING: State mismatch detected!");
    console.error(`      Round ID: ${currentRoundId} -> ${postRoundId}`);
    console.error(`      Min Price: ${minPrice} -> ${postMinPrice}`);
    console.error(`      Max Price: ${maxPrice} -> ${postMaxPrice}`);
  } else {
    console.log(`   ✅ State preserved correctly`);
  }

  // Verify the proxy still works
  const version = await auctionProxy.version();
  console.log(`   Contract Version: ${version}`);

  // Get transaction details
  // Note: In a real scenario, you'd capture the upgrade transaction
  const currentBlock = await ethers.provider.getBlockNumber();

  // Save upgrade info
  const upgradeInfo: UpgradeInfo = {
    network: networkName,
    chainId: Number(chainId),
    contract: "EnergyAuctionUpgradeable",
    proxy: proxyAddress,
    oldImplementation: oldImplAddress,
    newImplementation: newImplAddress,
    upgrader: upgrader.address,
    timestamp: new Date().toISOString(),
    transactionHash: "", // Would capture from tx
    blockNumber: currentBlock,
  };

  // Save to upgrades history
  const upgradesDir = path.join(deploymentsDir, "upgrades");
  if (!fs.existsSync(upgradesDir)) {
    fs.mkdirSync(upgradesDir, { recursive: true });
  }

  const upgradeFile = path.join(
    upgradesDir,
    `${networkName}-auction-upgrade-${Date.now()}.json`
  );
  fs.writeFileSync(upgradeFile, JSON.stringify(upgradeInfo, null, 2));

  // Update main deployment file
  deployment.contracts.EnergyAuctionUpgradeable.implementation = newImplAddress;
  fs.writeFileSync(deploymentFile, JSON.stringify(deployment, null, 2));

  console.log(`\n💾 Upgrade info saved to: ${upgradeFile}`);
  console.log(`   Main deployment updated: ${deploymentFile}`);

  // Summary
  console.log("\n" + "=".repeat(60));
  console.log("🎉 UPGRADE COMPLETE");
  console.log("=".repeat(60));
  console.log(`   Contract: EnergyAuctionUpgradeable`);
  console.log(`   Proxy: ${proxyAddress}`);
  console.log(`   Old Impl: ${oldImplAddress}`);
  console.log(`   New Impl: ${newImplAddress}`);
  console.log(`   State Preserved: ${statePreserved ? "Yes" : "NO - CHECK IMMEDIATELY"}`);
  console.log("=".repeat(60) + "\n");
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("\n❌ Upgrade failed:");
    console.error(error);
    process.exit(1);
  });
