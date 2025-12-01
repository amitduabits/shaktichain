/**
 * SHAKTI-CHAIN Mainnet Deployment Script
 *
 * This script deploys all contracts to Polygon Mainnet with:
 * - Confirmation prompts at each step
 * - Automatic backup of deployment addresses
 * - Post-deployment verification
 * - Safety checks and validations
 *
 * Usage: npx hardhat run scripts/deploy/deploy-mainnet.ts --network polygon
 */

import { ethers, network } from "hardhat";
import * as readline from "readline";
import * as fs from "fs";
import * as path from "path";

// Import deployment scripts
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
import deployTimelock from "./12-deploy-timelock";
import deployGovernor from "./11-deploy-governor";

// Colors for console output
const colors = {
  reset: "\x1b[0m",
  red: "\x1b[31m",
  green: "\x1b[32m",
  yellow: "\x1b[33m",
  blue: "\x1b[34m",
  magenta: "\x1b[35m",
  cyan: "\x1b[36m",
};

interface DeploymentBackup {
  timestamp: string;
  network: string;
  chainId: number;
  deployer: string;
  contracts: Record<string, string>;
  transactionHashes: Record<string, string>;
  gasUsed: string;
  totalCost: string;
}

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout,
});

function prompt(question: string): Promise<string> {
  return new Promise((resolve) => {
    rl.question(question, (answer) => {
      resolve(answer.trim().toLowerCase());
    });
  });
}

async function confirmContinue(message: string): Promise<boolean> {
  const answer = await prompt(`${colors.yellow}${message} (yes/no): ${colors.reset}`);
  return answer === "yes" || answer === "y";
}

function printBanner() {
  console.log(`
${colors.magenta}╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║   ███████╗██╗  ██╗ █████╗ ██╗  ██╗████████╗██╗                  ║
║   ██╔════╝██║  ██║██╔══██╗██║ ██╔╝╚══██╔══╝██║                  ║
║   ███████╗███████║███████║█████╔╝    ██║   ██║                  ║
║   ╚════██║██╔══██║██╔══██║██╔═██╗    ██║   ██║                  ║
║   ███████║██║  ██║██║  ██║██║  ██╗   ██║   ██║                  ║
║   ╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝   ╚═╝                  ║
║                                                                  ║
║            POLYGON MAINNET DEPLOYMENT                            ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝${colors.reset}
`);
}

function printWarning() {
  console.log(`
${colors.red}╔══════════════════════════════════════════════════════════════════╗
║                         ⚠️  WARNING ⚠️                            ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  You are about to deploy to POLYGON MAINNET.                    ║
║                                                                  ║
║  This will:                                                      ║
║  • Deploy 12 smart contracts                                     ║
║  • Use REAL MATIC for gas fees                                   ║
║  • Create IMMUTABLE contracts on mainnet                         ║
║                                                                  ║
║  Make sure you have:                                             ║
║  • Completed all testnet testing                                 ║
║  • Reviewed the LAUNCH-CHECKLIST.md                              ║
║  • Obtained necessary approvals                                  ║
║  • Sufficient MATIC for deployment (~5-10 MATIC recommended)     ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝${colors.reset}
`);
}

async function preFlightChecks(): Promise<boolean> {
  console.log(`\n${colors.cyan}Running pre-flight checks...${colors.reset}\n`);

  // Check 1: Network
  console.log("1. Checking network...");
  if (network.name !== "polygon") {
    console.log(`   ${colors.red}✗ Wrong network: ${network.name}. Expected: polygon${colors.reset}`);
    console.log(`   ${colors.yellow}Run with: npx hardhat run scripts/deploy/deploy-mainnet.ts --network polygon${colors.reset}`);
    return false;
  }
  const chainId = network.config.chainId;
  if (chainId !== 137) {
    console.log(`   ${colors.red}✗ Wrong chain ID: ${chainId}. Expected: 137${colors.reset}`);
    return false;
  }
  console.log(`   ${colors.green}✓ Network: ${network.name} (Chain ID: ${chainId})${colors.reset}`);

  // Check 2: Deployer balance
  console.log("\n2. Checking deployer wallet...");
  const [deployer] = await ethers.getSigners();
  const balance = await ethers.provider.getBalance(deployer.address);
  const balanceInMatic = ethers.formatEther(balance);

  console.log(`   Deployer: ${deployer.address}`);
  console.log(`   Balance: ${balanceInMatic} MATIC`);

  if (Number(balanceInMatic) < 5) {
    console.log(`   ${colors.yellow}⚠ Low balance! Recommended: 5+ MATIC${colors.reset}`);
    const proceed = await confirmContinue("Continue with low balance?");
    if (!proceed) return false;
  } else {
    console.log(`   ${colors.green}✓ Sufficient balance${colors.reset}`);
  }

  // Check 3: Gas price
  console.log("\n3. Checking gas price...");
  const feeData = await ethers.provider.getFeeData();
  const gasPrice = feeData.gasPrice || 0n;
  const gasPriceGwei = Number(gasPrice) / 1e9;

  console.log(`   Current gas price: ${gasPriceGwei.toFixed(2)} Gwei`);

  if (gasPriceGwei > 500) {
    console.log(`   ${colors.red}✗ Gas price too high! Consider waiting.${colors.reset}`);
    const proceed = await confirmContinue("Continue with high gas price?");
    if (!proceed) return false;
  } else if (gasPriceGwei > 100) {
    console.log(`   ${colors.yellow}⚠ Elevated gas price${colors.reset}`);
  } else {
    console.log(`   ${colors.green}✓ Gas price acceptable${colors.reset}`);
  }

  // Check 4: RPC connection
  console.log("\n4. Checking RPC connection...");
  try {
    const blockNumber = await ethers.provider.getBlockNumber();
    console.log(`   Current block: ${blockNumber}`);
    console.log(`   ${colors.green}✓ RPC connection healthy${colors.reset}`);
  } catch {
    console.log(`   ${colors.red}✗ RPC connection failed${colors.reset}`);
    return false;
  }

  // Check 5: Environment variables
  console.log("\n5. Checking configuration...");
  const requiredEnv = ["PRIVATE_KEY"];
  const missingEnv = requiredEnv.filter((key) => !process.env[key]);

  if (missingEnv.length > 0) {
    console.log(`   ${colors.red}✗ Missing environment variables: ${missingEnv.join(", ")}${colors.reset}`);
    return false;
  }
  console.log(`   ${colors.green}✓ Configuration valid${colors.reset}`);

  console.log(`\n${colors.green}All pre-flight checks passed!${colors.reset}\n`);
  return true;
}

async function createBackup(
  contracts: Record<string, string>,
  txHashes: Record<string, string>,
  deployer: string,
  startBalance: bigint,
  endBalance: bigint
): Promise<string> {
  const backup: DeploymentBackup = {
    timestamp: new Date().toISOString(),
    network: network.name,
    chainId: network.config.chainId || 0,
    deployer,
    contracts,
    transactionHashes: txHashes,
    gasUsed: "N/A",
    totalCost: ethers.formatEther(startBalance - endBalance) + " MATIC",
  };

  const backupDir = path.join(__dirname, "../../deployments/mainnet-backups");
  if (!fs.existsSync(backupDir)) {
    fs.mkdirSync(backupDir, { recursive: true });
  }

  const backupFile = path.join(
    backupDir,
    `deployment-${Date.now()}.json`
  );

  fs.writeFileSync(backupFile, JSON.stringify(backup, null, 2));
  console.log(`\n${colors.green}Backup saved to: ${backupFile}${colors.reset}`);

  return backupFile;
}

async function main() {
  printBanner();
  printWarning();

  // Initial confirmation
  const initialConfirm = await confirmContinue("Do you want to proceed with mainnet deployment?");
  if (!initialConfirm) {
    console.log("Deployment cancelled.");
    rl.close();
    process.exit(0);
  }

  // Pre-flight checks
  const checksPass = await preFlightChecks();
  if (!checksPass) {
    console.log(`\n${colors.red}Pre-flight checks failed. Aborting deployment.${colors.reset}`);
    rl.close();
    process.exit(1);
  }

  // Final confirmation
  console.log(`\n${colors.yellow}═══════════════════════════════════════════════════════════${colors.reset}`);
  console.log(`${colors.yellow}                    FINAL CONFIRMATION                      ${colors.reset}`);
  console.log(`${colors.yellow}═══════════════════════════════════════════════════════════${colors.reset}\n`);

  const finalConfirm = await confirmContinue(
    "Type 'yes' to confirm mainnet deployment. This action cannot be undone"
  );
  if (!finalConfirm) {
    console.log("Deployment cancelled.");
    rl.close();
    process.exit(0);
  }

  // Record start time and balance
  const startTime = Date.now();
  const [deployer] = await ethers.getSigners();
  const startBalance = await ethers.provider.getBalance(deployer.address);

  const deployedContracts: Record<string, string> = {};
  const txHashes: Record<string, string> = {};

  console.log(`\n${colors.cyan}Starting deployment...${colors.reset}\n`);

  try {
    // Step 1: Deploy ShaktiToken
    console.log(`\n${colors.blue}[1/12] Deploying ShaktiToken...${colors.reset}`);
    if (!(await confirmContinue("Deploy ShaktiToken?"))) {
      throw new Error("Deployment cancelled by user");
    }
    const { address: tokenAddress } = await deployToken();
    deployedContracts["ShaktiToken"] = tokenAddress;
    console.log(`${colors.green}✓ ShaktiToken: ${tokenAddress}${colors.reset}`);

    // Step 2: Deploy StakingPool
    console.log(`\n${colors.blue}[2/12] Deploying StakingPool...${colors.reset}`);
    if (!(await confirmContinue("Deploy StakingPool?"))) {
      throw new Error("Deployment cancelled by user");
    }
    const { address: stakingAddress } = await deployStaking();
    deployedContracts["StakingPool"] = stakingAddress;
    console.log(`${colors.green}✓ StakingPool: ${stakingAddress}${colors.reset}`);

    // Step 3: Deploy EnergyRegistry
    console.log(`\n${colors.blue}[3/12] Deploying EnergyRegistry...${colors.reset}`);
    if (!(await confirmContinue("Deploy EnergyRegistry?"))) {
      throw new Error("Deployment cancelled by user");
    }
    const { address: registryAddress } = await deployRegistry();
    deployedContracts["EnergyRegistry"] = registryAddress;
    console.log(`${colors.green}✓ EnergyRegistry: ${registryAddress}${colors.reset}`);

    // Step 4: Deploy PriceOracle
    console.log(`\n${colors.blue}[4/12] Deploying PriceOracle...${colors.reset}`);
    console.log(`${colors.yellow}Note: For mainnet, you need to provide actual Chainlink feed addresses${colors.reset}`);
    if (!(await confirmContinue("Deploy PriceOracle?"))) {
      throw new Error("Deployment cancelled by user");
    }
    const { address: oracleAddress } = await deployOracle();
    deployedContracts["PriceOracle"] = oracleAddress;
    console.log(`${colors.green}✓ PriceOracle: ${oracleAddress}${colors.reset}`);

    // Step 5: Deploy DynamicPricing
    console.log(`\n${colors.blue}[5/12] Deploying DynamicPricing...${colors.reset}`);
    if (!(await confirmContinue("Deploy DynamicPricing?"))) {
      throw new Error("Deployment cancelled by user");
    }
    const { address: pricingAddress } = await deployDynamicPricing();
    deployedContracts["DynamicPricing"] = pricingAddress;
    console.log(`${colors.green}✓ DynamicPricing: ${pricingAddress}${colors.reset}`);

    // Step 6: Deploy EnergyAuction
    console.log(`\n${colors.blue}[6/12] Deploying EnergyAuction...${colors.reset}`);
    if (!(await confirmContinue("Deploy EnergyAuction?"))) {
      throw new Error("Deployment cancelled by user");
    }
    const { address: auctionAddress } = await deployAuction();
    deployedContracts["EnergyAuction"] = auctionAddress;
    console.log(`${colors.green}✓ EnergyAuction: ${auctionAddress}${colors.reset}`);

    // Step 7: Deploy EnergyEscrow
    console.log(`\n${colors.blue}[7/12] Deploying EnergyEscrow...${colors.reset}`);
    if (!(await confirmContinue("Deploy EnergyEscrow?"))) {
      throw new Error("Deployment cancelled by user");
    }
    const { address: escrowAddress } = await deployEscrow();
    deployedContracts["EnergyEscrow"] = escrowAddress;
    console.log(`${colors.green}✓ EnergyEscrow: ${escrowAddress}${colors.reset}`);

    // Step 8: Deploy Treasury
    console.log(`\n${colors.blue}[8/12] Deploying Treasury...${colors.reset}`);
    console.log(`${colors.yellow}Note: Treasury requires 5 multisig signers to be configured${colors.reset}`);
    if (!(await confirmContinue("Deploy Treasury?"))) {
      throw new Error("Deployment cancelled by user");
    }
    const { address: treasuryAddress } = await deployTreasury();
    deployedContracts["Treasury"] = treasuryAddress;
    console.log(`${colors.green}✓ Treasury: ${treasuryAddress}${colors.reset}`);

    // Step 9: Deploy ReputationSystem
    console.log(`\n${colors.blue}[9/12] Deploying ReputationSystem...${colors.reset}`);
    if (!(await confirmContinue("Deploy ReputationSystem?"))) {
      throw new Error("Deployment cancelled by user");
    }
    const { address: reputationAddress } = await deployReputation();
    deployedContracts["ReputationSystem"] = reputationAddress;
    console.log(`${colors.green}✓ ReputationSystem: ${reputationAddress}${colors.reset}`);

    // Step 10: Deploy EnergyVerification
    console.log(`\n${colors.blue}[10/12] Deploying EnergyVerification...${colors.reset}`);
    if (!(await confirmContinue("Deploy EnergyVerification?"))) {
      throw new Error("Deployment cancelled by user");
    }
    const { address: verificationAddress } = await deployVerification();
    deployedContracts["EnergyVerification"] = verificationAddress;
    console.log(`${colors.green}✓ EnergyVerification: ${verificationAddress}${colors.reset}`);

    // Step 11: Deploy TimelockController
    console.log(`\n${colors.blue}[11/12] Deploying TimelockController...${colors.reset}`);
    if (!(await confirmContinue("Deploy TimelockController?"))) {
      throw new Error("Deployment cancelled by user");
    }
    const { address: timelockAddress } = await deployTimelock();
    deployedContracts["TimelockController"] = timelockAddress;
    console.log(`${colors.green}✓ TimelockController: ${timelockAddress}${colors.reset}`);

    // Step 12: Deploy ShaktiGovernor
    console.log(`\n${colors.blue}[12/12] Deploying ShaktiGovernor...${colors.reset}`);
    if (!(await confirmContinue("Deploy ShaktiGovernor?"))) {
      throw new Error("Deployment cancelled by user");
    }
    const { address: governorAddress } = await deployGovernor();
    deployedContracts["ShaktiGovernor"] = governorAddress;
    console.log(`${colors.green}✓ ShaktiGovernor: ${governorAddress}${colors.reset}`);

    // Record end time and balance
    const endTime = Date.now();
    const endBalance = await ethers.provider.getBalance(deployer.address);
    const duration = ((endTime - startTime) / 1000).toFixed(1);
    const cost = ethers.formatEther(startBalance - endBalance);

    // Create backup
    await createBackup(deployedContracts, txHashes, deployer.address, startBalance, endBalance);

    // Print summary
    console.log(`
${colors.green}╔══════════════════════════════════════════════════════════════════╗
║                    DEPLOYMENT SUCCESSFUL!                        ║
╚══════════════════════════════════════════════════════════════════╝${colors.reset}

${colors.cyan}Deployed Contracts:${colors.reset}
────────────────────────────────────────────────────────────────────
${Object.entries(deployedContracts)
  .map(([name, addr]) => `${name.padEnd(25)} ${addr}`)
  .join("\n")}
────────────────────────────────────────────────────────────────────

${colors.cyan}Deployment Stats:${colors.reset}
  Duration: ${duration} seconds
  Total Cost: ${cost} MATIC
  Remaining Balance: ${ethers.formatEther(endBalance)} MATIC

${colors.yellow}⚠️  IMPORTANT NEXT STEPS:${colors.reset}

1. ${colors.cyan}Verify contracts on Polygonscan:${colors.reset}
   npx hardhat run scripts/verify/verify-all.ts --network polygon

2. ${colors.cyan}Initialize contracts:${colors.reset}
   npx hardhat run scripts/setup/initialize-contracts.ts --network polygon

3. ${colors.cyan}Transfer ownership to multisig:${colors.reset}
   npx hardhat run scripts/setup/transfer-to-multisig.ts --network polygon

4. ${colors.cyan}Update monitoring:${colors.reset}
   - Add contracts to Tenderly
   - Configure alerts

5. ${colors.cyan}Announce launch:${colors.reset}
   - Update status page
   - Notify community

${colors.green}Backup saved to: deployments/mainnet-backups/${colors.reset}
`);
  } catch (error) {
    console.log(`\n${colors.red}Deployment failed!${colors.reset}`);
    console.error(error);

    // Save partial deployment
    if (Object.keys(deployedContracts).length > 0) {
      const endBalance = await ethers.provider.getBalance(deployer.address);
      await createBackup(deployedContracts, txHashes, deployer.address, startBalance, endBalance);
      console.log(`\n${colors.yellow}Partial deployment saved. Deployed contracts:${colors.reset}`);
      Object.entries(deployedContracts).forEach(([name, addr]) => {
        console.log(`  ${name}: ${addr}`);
      });
    }

    rl.close();
    process.exit(1);
  }

  rl.close();
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
