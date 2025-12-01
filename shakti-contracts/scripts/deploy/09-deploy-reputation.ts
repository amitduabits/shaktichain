/**
 * SHAKTI-CHAIN Deployment Script: ReputationSystem
 *
 * Deploys the tiered reputation system for prosumers.
 */

import { ethers, network } from "hardhat";
import { saveDeployment, getDeployer, estimateGasWithBuffer } from "../utils/deployment-helpers";

async function main() {
  console.log("\n========================================");
  console.log("  Deploying ReputationSystem");
  console.log("  Network:", network.name);
  console.log("========================================\n");

  const deployer = await getDeployer();
  console.log("Deployer:", deployer.address);

  // Deploy ReputationSystem
  const ReputationSystem = await ethers.getContractFactory("ReputationSystem");

  // Constructor args: admin
  const constructorArgs = [deployer.address];

  const deployTx = await ReputationSystem.getDeployTransaction(...constructorArgs);
  const estimatedGas = await estimateGasWithBuffer(deployTx);
  console.log("Estimated gas:", estimatedGas.toString());

  const reputationSystem = await ReputationSystem.deploy(...constructorArgs, {
    gasLimit: estimatedGas,
  });

  await reputationSystem.waitForDeployment();
  const reputationAddress = await reputationSystem.getAddress();

  console.log("\nReputationSystem deployed to:", reputationAddress);
  console.log("Transaction hash:", reputationSystem.deploymentTransaction()?.hash);

  // Verify configuration
  const startingRep = await reputationSystem.STARTING_REPUTATION();
  const maxRep = await reputationSystem.MAX_REPUTATION();

  console.log("\nReputation Configuration:");
  console.log("  Starting Score:", Number(startingRep));
  console.log("  Maximum Score:", Number(maxRep));

  // Save deployment
  await saveDeployment("ReputationSystem", {
    address: reputationAddress,
    constructorArgs,
    txHash: reputationSystem.deploymentTransaction()?.hash,
    deployer: deployer.address,
    network: network.name,
    chainId: network.config.chainId,
    timestamp: new Date().toISOString(),
  });

  console.log("\n✅ ReputationSystem deployment complete!");

  return { reputationSystem, address: reputationAddress };
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
