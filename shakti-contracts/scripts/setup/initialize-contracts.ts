/**
 * SHAKTI-CHAIN Post-Deployment Initialization
 *
 * Sets up roles, grants permissions, and initializes parameters.
 */

import { ethers, network } from "hardhat";
import { getDeployer, loadAllDeployments, sleep } from "../utils/deployment-helpers";

async function main() {
  console.log("\n╔════════════════════════════════════════════════════════════╗");
  console.log("║           SHAKTI-CHAIN Contract Initialization              ║");
  console.log("╚════════════════════════════════════════════════════════════╝\n");

  const deployer = await getDeployer();
  console.log("Admin:", deployer.address);
  console.log("Network:", network.name);
  console.log("");

  // Load all deployments
  const deployments = await loadAllDeployments();

  if (Object.keys(deployments).length === 0) {
    throw new Error("No deployments found. Run deploy-all.ts first.");
  }

  console.log("Loaded deployments:", Object.keys(deployments).join(", "));
  console.log("");

  // Get contract instances
  const shaktiToken = await ethers.getContractAt("ShaktiToken", deployments.ShaktiToken.address);
  const stakingPool = await ethers.getContractAt("StakingPool", deployments.StakingPool.address);
  const energyAuction = await ethers.getContractAt("EnergyAuction", deployments.EnergyAuction.address);
  const energyEscrow = await ethers.getContractAt("EnergyEscrow", deployments.EnergyEscrow.address);
  const treasury = await ethers.getContractAt("Treasury", deployments.Treasury.address);
  const reputationSystem = await ethers.getContractAt("ReputationSystem", deployments.ReputationSystem.address);
  const energyRegistry = await ethers.getContractAt("EnergyRegistry", deployments.EnergyRegistry.address);

  console.log("Step 1: Setting up token roles...");
  // Grant MINTER_ROLE to StakingPool for reward distribution
  const MINTER_ROLE = await shaktiToken.MINTER_ROLE();
  if (!(await shaktiToken.hasRole(MINTER_ROLE, deployments.StakingPool.address))) {
    const tx1 = await shaktiToken.grantRole(MINTER_ROLE, deployments.StakingPool.address);
    await tx1.wait();
    console.log("  ✅ Granted MINTER_ROLE to StakingPool");
  } else {
    console.log("  ⏭️  StakingPool already has MINTER_ROLE");
  }
  await sleep(1000);

  console.log("\nStep 2: Setting up escrow roles...");
  // Grant AUCTION_ROLE to EnergyAuction
  const AUCTION_ROLE = await energyEscrow.AUCTION_ROLE();
  if (!(await energyEscrow.hasRole(AUCTION_ROLE, deployments.EnergyAuction.address))) {
    const tx2 = await energyEscrow.grantRole(AUCTION_ROLE, deployments.EnergyAuction.address);
    await tx2.wait();
    console.log("  ✅ Granted AUCTION_ROLE to EnergyAuction");
  } else {
    console.log("  ⏭️  EnergyAuction already has AUCTION_ROLE");
  }
  await sleep(1000);

  console.log("\nStep 3: Setting up auction roles...");
  // Grant OPERATOR_ROLE to admin for auction management
  const OPERATOR_ROLE = await energyAuction.OPERATOR_ROLE();
  if (!(await energyAuction.hasRole(OPERATOR_ROLE, deployer.address))) {
    const tx3 = await energyAuction.grantRole(OPERATOR_ROLE, deployer.address);
    await tx3.wait();
    console.log("  ✅ Granted OPERATOR_ROLE to admin");
  } else {
    console.log("  ⏭️  Admin already has OPERATOR_ROLE");
  }
  await sleep(1000);

  console.log("\nStep 4: Setting up reputation roles...");
  // Grant REPORTER_ROLE to EnergyAuction for trade reporting
  const REPORTER_ROLE = await reputationSystem.REPORTER_ROLE();
  if (!(await reputationSystem.hasRole(REPORTER_ROLE, deployments.EnergyAuction.address))) {
    const tx4 = await reputationSystem.grantRole(REPORTER_ROLE, deployments.EnergyAuction.address);
    await tx4.wait();
    console.log("  ✅ Granted REPORTER_ROLE to EnergyAuction");
  } else {
    console.log("  ⏭️  EnergyAuction already has REPORTER_ROLE");
  }
  await sleep(1000);

  console.log("\nStep 5: Updating treasury address in escrow...");
  // Set treasury address in escrow
  const currentTreasury = await energyEscrow.treasury();
  if (currentTreasury.toLowerCase() !== deployments.Treasury.address.toLowerCase()) {
    const TREASURY_ROLE = await energyEscrow.TREASURY_ROLE();
    await energyEscrow.grantRole(TREASURY_ROLE, deployer.address);
    const tx5 = await energyEscrow.setTreasury(deployments.Treasury.address);
    await tx5.wait();
    console.log("  ✅ Set treasury address in escrow");
  } else {
    console.log("  ⏭️  Treasury already set correctly");
  }
  await sleep(1000);

  console.log("\nStep 6: Funding staking pool with reward tokens...");
  // Transfer tokens to staking pool for rewards
  const stakingBalance = await shaktiToken.balanceOf(deployments.StakingPool.address);
  const requiredBalance = ethers.parseEther("10000000"); // 10M SHAKTI for rewards
  if (stakingBalance < requiredBalance) {
    const deployerBalance = await shaktiToken.balanceOf(deployer.address);
    const toTransfer = requiredBalance - stakingBalance;
    if (deployerBalance >= toTransfer) {
      const tx6 = await shaktiToken.transfer(deployments.StakingPool.address, toTransfer);
      await tx6.wait();
      console.log("  ✅ Transferred", ethers.formatEther(toTransfer), "SHAKTI to StakingPool");
    } else {
      console.log("  ⚠️  Insufficient balance to fund staking pool");
    }
  } else {
    console.log("  ⏭️  StakingPool already funded");
  }
  await sleep(1000);

  console.log("\nStep 7: Creating initial auction round...");
  // Create first auction round (10 minute duration for testing)
  const currentRound = await energyAuction.currentRoundId();
  if (currentRound === BigInt(0)) {
    const duration = 600; // 10 minutes
    const tx7 = await energyAuction.createAuctionRound(duration);
    await tx7.wait();
    console.log("  ✅ Created initial auction round (10 min duration)");
  } else {
    console.log("  ⏭️  Auction round already exists");
  }
  await sleep(1000);

  console.log("\nStep 8: Minting test tokens to team wallets...");
  // For testnet: mint tokens to test wallets
  const testWallets = [
    deployer.address,
    // Add more test wallet addresses here
  ];

  for (const wallet of testWallets) {
    const walletBalance = await shaktiToken.balanceOf(wallet);
    const testAmount = ethers.parseEther("100000"); // 100K SHAKTI per wallet
    if (walletBalance < testAmount) {
      try {
        const tx = await shaktiToken.mint(wallet, testAmount - walletBalance);
        await tx.wait();
        console.log("  ✅ Minted", ethers.formatEther(testAmount - walletBalance), "SHAKTI to", wallet.slice(0, 10) + "...");
      } catch (error: any) {
        console.log("  ⚠️  Could not mint to", wallet.slice(0, 10) + "...", "-", error.message?.slice(0, 50));
      }
    }
  }

  console.log("\n╔════════════════════════════════════════════════════════════╗");
  console.log("║               Initialization Complete!                       ║");
  console.log("╚════════════════════════════════════════════════════════════╝\n");

  // Print role summary
  console.log("Role Summary:");
  console.log("─".repeat(60));
  console.log(`ShaktiToken MINTER_ROLE  → StakingPool`);
  console.log(`EnergyEscrow AUCTION_ROLE → EnergyAuction`);
  console.log(`EnergyAuction OPERATOR_ROLE → Admin`);
  console.log(`ReputationSystem REPORTER_ROLE → EnergyAuction`);
  console.log("─".repeat(60));

  console.log("\n📋 Next Steps:");
  console.log("1. Run verification: npx hardhat run scripts/verify/verify-all.ts --network", network.name);
  console.log("2. Test the contracts using the frontend or scripts");
  console.log("3. See TESTNET-GUIDE.md for testing instructions");
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
