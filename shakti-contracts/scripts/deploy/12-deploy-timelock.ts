/**
 * SHAKTI-CHAIN Deployment Script: TimelockController
 *
 * Deploys the OpenZeppelin TimelockController for governance execution.
 */

import { ethers, network } from "hardhat";
import { saveDeployment, getDeployer, loadDeployment, estimateGasWithBuffer } from "../utils/deployment-helpers";

async function main() {
  console.log("\n========================================");
  console.log("  Deploying TimelockController");
  console.log("  Network:", network.name);
  console.log("========================================\n");

  const deployer = await getDeployer();
  console.log("Deployer:", deployer.address);

  // Deploy TimelockController
  // Note: Timelock is deployed BEFORE Governor. Governor will be granted proposer role after deployment.
  const TimelockController = await ethers.getContractFactory("TimelockController");

  // Constructor args: minDelay, proposers[], executors[], admin
  const minDelay = 172800;  // 48 hours for testnet (would be longer for mainnet)
  // Deployer is initial proposer - Governor will be added in initialize-contracts.ts
  const proposers = [deployer.address];
  const executors = [ethers.ZeroAddress];         // Anyone can execute after delay
  const admin = deployer.address;                  // Initial admin (will renounce later)

  const constructorArgs = [minDelay, proposers, executors, admin];

  const deployTx = await TimelockController.getDeployTransaction(...constructorArgs);
  const estimatedGas = await estimateGasWithBuffer(deployTx);
  console.log("Estimated gas:", estimatedGas.toString());

  const timelock = await TimelockController.deploy(...constructorArgs, {
    gasLimit: estimatedGas,
  });

  await timelock.waitForDeployment();
  const timelockAddress = await timelock.getAddress();

  console.log("\nTimelockController deployed to:", timelockAddress);
  console.log("Transaction hash:", timelock.deploymentTransaction()?.hash);

  // Verify configuration
  const configMinDelay = await timelock.getMinDelay();
  const PROPOSER_ROLE = await timelock.PROPOSER_ROLE();
  const EXECUTOR_ROLE = await timelock.EXECUTOR_ROLE();
  const CANCELLER_ROLE = await timelock.CANCELLER_ROLE();

  console.log("\nTimelock Configuration:");
  console.log("  Minimum Delay:", Number(configMinDelay) / 3600, "hours");
  console.log("  Proposer Role:", PROPOSER_ROLE);
  console.log("  Executor Role:", EXECUTOR_ROLE);
  console.log("  Canceller Role:", CANCELLER_ROLE);

  // Save deployment
  await saveDeployment("TimelockController", {
    address: timelockAddress,
    constructorArgs: [minDelay, proposers, executors, admin],
    txHash: timelock.deploymentTransaction()?.hash,
    deployer: deployer.address,
    network: network.name,
    chainId: network.config.chainId,
    timestamp: new Date().toISOString(),
  });

  console.log("\n✅ TimelockController deployment complete!");

  return { timelock, address: timelockAddress };
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
