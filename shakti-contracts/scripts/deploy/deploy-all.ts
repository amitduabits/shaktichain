/**
 * SHAKTI-CHAIN Deployment Script: Deploy All Contracts
 *
 * Orchestrates the deployment of all SHAKTI-CHAIN contracts in order.
 */

import { ethers, network } from "hardhat";
import { getDeployer, loadAllDeployments, printDeploymentSummary, sleep, getNetworkConfig } from "../utils/deployment-helpers";

// Import individual deployment scripts
import deployToken from "./01-deploy-token";
import deployStaking from "./02-deploy-staking";
import deployRegistry from "./03-deploy-registry";
import deployOracle from "./04-deploy-oracle";
import deployDynamicPricing from "./05-deploy-dynamic-pricing";
import deployAuction from "./06-deploy-auction";
import deployEscrow from "./07-deploy-escrow";
import deployTreasury from "./08-deploy-treasury";
import deployReputation from "./09-deploy-reputation";
import deployVerification from "./10-deploy-verification";
import deployGovernor from "./11-deploy-governor";
import deployTimelock from "./12-deploy-timelock";

async function main() {
  console.log("\n╔════════════════════════════════════════════════════════════╗");
  console.log("║           SHAKTI-CHAIN Full Deployment                      ║");
  console.log("╚════════════════════════════════════════════════════════════╝\n");

  const networkConfig = getNetworkConfig();
  console.log("Network:", networkConfig.name);
  console.log("Chain ID:", networkConfig.chainId);
  console.log("Is Testnet:", networkConfig.isTestnet);
  console.log("");

  const deployer = await getDeployer();
  const balance = await ethers.provider.getBalance(deployer.address);

  console.log("Deployer:", deployer.address);
  console.log("Balance:", ethers.formatEther(balance), "MATIC");
  console.log("");

  // Minimum balance check (0.5 MATIC for testnet)
  const minBalance = ethers.parseEther("0.5");
  if (balance < minBalance) {
    throw new Error(`Insufficient balance. Need at least ${ethers.formatEther(minBalance)} MATIC`);
  }

  const deployedContracts: Record<string, string> = {};
  const startTime = Date.now();

  try {
    // Step 1: Deploy ShaktiToken
    console.log("\n[1/12] Deploying ShaktiToken...");
    const { address: tokenAddress } = await deployToken();
    deployedContracts["ShaktiToken"] = tokenAddress;
    await sleep(2000);

    // Step 2: Deploy StakingPool
    console.log("\n[2/12] Deploying StakingPool...");
    const { address: stakingAddress } = await deployStaking();
    deployedContracts["StakingPool"] = stakingAddress;
    await sleep(2000);

    // Step 3: Deploy EnergyRegistry
    console.log("\n[3/12] Deploying EnergyRegistry...");
    const { address: registryAddress } = await deployRegistry();
    deployedContracts["EnergyRegistry"] = registryAddress;
    await sleep(2000);

    // Step 4: Deploy PriceOracle
    console.log("\n[4/12] Deploying PriceOracle...");
    const { address: oracleAddress } = await deployOracle();
    deployedContracts["PriceOracle"] = oracleAddress;
    await sleep(2000);

    // Step 5: Deploy DynamicPricing
    console.log("\n[5/12] Deploying DynamicPricing...");
    const { address: pricingAddress } = await deployDynamicPricing();
    deployedContracts["DynamicPricing"] = pricingAddress;
    await sleep(2000);

    // Step 6: Deploy EnergyAuction
    console.log("\n[6/12] Deploying EnergyAuction...");
    const { address: auctionAddress } = await deployAuction();
    deployedContracts["EnergyAuction"] = auctionAddress;
    await sleep(2000);

    // Step 7: Deploy EnergyEscrow
    console.log("\n[7/12] Deploying EnergyEscrow...");
    const { address: escrowAddress } = await deployEscrow();
    deployedContracts["EnergyEscrow"] = escrowAddress;
    await sleep(2000);

    // Step 8: Deploy Treasury
    console.log("\n[8/12] Deploying Treasury...");
    const { address: treasuryAddress } = await deployTreasury();
    deployedContracts["Treasury"] = treasuryAddress;
    await sleep(2000);

    // Step 9: Deploy ReputationSystem
    console.log("\n[9/12] Deploying ReputationSystem...");
    const { address: reputationAddress } = await deployReputation();
    deployedContracts["ReputationSystem"] = reputationAddress;
    await sleep(2000);

    // Step 10: Deploy EnergyVerification
    console.log("\n[10/12] Deploying EnergyVerification...");
    const { address: verificationAddress } = await deployVerification();
    deployedContracts["EnergyVerification"] = verificationAddress;
    await sleep(2000);

    // Step 11: Deploy TimelockController (must be before Governor)
    console.log("\n[11/12] Deploying TimelockController...");
    const { address: timelockAddress } = await deployTimelock();
    deployedContracts["TimelockController"] = timelockAddress;
    await sleep(2000);

    // Step 12: Deploy ShaktiGovernor (requires Timelock)
    console.log("\n[12/12] Deploying ShaktiGovernor...");
    const { address: governorAddress } = await deployGovernor();
    deployedContracts["ShaktiGovernor"] = governorAddress;

    const endTime = Date.now();
    const duration = (endTime - startTime) / 1000;

    // Print final summary
    console.log("\n╔════════════════════════════════════════════════════════════╗");
    console.log("║                  Deployment Complete!                       ║");
    console.log("╚════════════════════════════════════════════════════════════╝\n");

    console.log("Deployed Contracts:");
    console.log("─".repeat(60));
    for (const [name, address] of Object.entries(deployedContracts)) {
      console.log(`${name.padEnd(25)} ${address}`);
    }
    console.log("─".repeat(60));
    console.log(`Total Time: ${duration.toFixed(1)} seconds`);
    console.log("");

    const finalBalance = await ethers.provider.getBalance(deployer.address);
    const gasUsed = balance - finalBalance;
    console.log("Gas Cost:", ethers.formatEther(gasUsed), "MATIC");
    console.log("Remaining Balance:", ethers.formatEther(finalBalance), "MATIC");

    console.log("\n📋 Next Steps:");
    console.log("1. Run: npx hardhat run scripts/setup/initialize-contracts.ts --network", network.name);
    console.log("2. Run: npx hardhat run scripts/verify/verify-all.ts --network", network.name);
    console.log("3. Check deployments in: deployments/", network.name);

  } catch (error) {
    console.error("\n❌ Deployment failed!");
    console.error(error);

    console.log("\nPartially deployed contracts:");
    for (const [name, address] of Object.entries(deployedContracts)) {
      console.log(`  ${name}: ${address}`);
    }

    throw error;
  }
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
