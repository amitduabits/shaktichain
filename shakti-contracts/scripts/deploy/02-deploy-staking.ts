/**
 * SHAKTI-CHAIN Deployment Script: StakingPool
 *
 * Deploys the staking pool with configurable APY and lock periods.
 */

import { ethers, network } from "hardhat";
import { saveDeployment, getDeployer, loadDeployment, estimateGasWithBuffer } from "../utils/deployment-helpers";

async function main() {
  console.log("\n========================================");
  console.log("  Deploying StakingPool");
  console.log("  Network:", network.name);
  console.log("========================================\n");

  const deployer = await getDeployer();
  console.log("Deployer:", deployer.address);

  // Load token deployment
  const tokenDeployment = await loadDeployment("ShaktiToken");
  if (!tokenDeployment) {
    throw new Error("ShaktiToken not deployed. Run 01-deploy-token.ts first.");
  }
  console.log("ShaktiToken address:", tokenDeployment.address);

  // Deploy StakingPool
  const StakingPool = await ethers.getContractFactory("StakingPool");

  // Constructor args: stakingToken, admin, initialRewardRate (800 = 8% APY)
  const initialRewardRate = 800; // 8% APY in basis points
  const constructorArgs = [tokenDeployment.address, deployer.address, initialRewardRate];

  const deployTx = await StakingPool.getDeployTransaction(...constructorArgs);
  const estimatedGas = await estimateGasWithBuffer(deployTx);
  console.log("Estimated gas:", estimatedGas.toString());

  const stakingPool = await StakingPool.deploy(...constructorArgs, {
    gasLimit: estimatedGas,
  });

  await stakingPool.waitForDeployment();
  const stakingAddress = await stakingPool.getAddress();

  console.log("\nStakingPool deployed to:", stakingAddress);
  console.log("Transaction hash:", stakingPool.deploymentTransaction()?.hash);

  // Verify configuration
  const minStake = await stakingPool.MINIMUM_STAKE();
  const rewardRate = await stakingPool.annualRewardRate();
  const lock30 = await stakingPool.LOCK_30_DAYS();
  const lock90 = await stakingPool.LOCK_90_DAYS();

  console.log("\nStaking Configuration:");
  console.log("  Minimum Stake:", ethers.formatEther(minStake), "SHAKTI");
  console.log("  Annual Reward Rate:", Number(rewardRate) / 100, "%");
  console.log("  30-Day Lock:", Number(lock30) / 86400, "days");
  console.log("  90-Day Lock:", Number(lock90) / 86400, "days");

  // Save deployment
  await saveDeployment("StakingPool", {
    address: stakingAddress,
    constructorArgs,
    txHash: stakingPool.deploymentTransaction()?.hash,
    deployer: deployer.address,
    network: network.name,
    chainId: network.config.chainId,
    timestamp: new Date().toISOString(),
  });

  console.log("\n✅ StakingPool deployment complete!");

  return { stakingPool, address: stakingAddress };
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
