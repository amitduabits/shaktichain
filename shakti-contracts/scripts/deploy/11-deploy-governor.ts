/**
 * SHAKTI-CHAIN Deployment Script: ShaktiGovernor
 *
 * Deploys the governance contract for protocol decisions.
 */

import { ethers, network } from "hardhat";
import { saveDeployment, getDeployer, loadDeployment, estimateGasWithBuffer } from "../utils/deployment-helpers";

async function main() {
  console.log("\n========================================");
  console.log("  Deploying ShaktiGovernor");
  console.log("  Network:", network.name);
  console.log("========================================\n");

  const deployer = await getDeployer();
  console.log("Deployer:", deployer.address);

  // Load dependencies
  const tokenDeployment = await loadDeployment("ShaktiToken");
  if (!tokenDeployment) {
    throw new Error("ShaktiToken not deployed. Run 01-deploy-token.ts first.");
  }
  console.log("ShaktiToken address:", tokenDeployment.address);

  const timelockDeployment = await loadDeployment("TimelockController");
  if (!timelockDeployment) {
    throw new Error("TimelockController not deployed. Timelock must be deployed before Governor.");
  }
  console.log("TimelockController address:", timelockDeployment.address);

  // Deploy ShaktiGovernor
  const ShaktiGovernor = await ethers.getContractFactory("ShaktiGovernor");

  // Constructor args: token, timelock, votingDelay (blocks), votingPeriod (blocks), proposalThreshold
  const votingDelay = 1;       // 1 block (~2 seconds on Polygon)
  const votingPeriod = 50400;  // ~1 week (2 second blocks)
  const proposalThreshold = ethers.parseEther("100000"); // 100k SHAKTI to propose
  const constructorArgs = [
    tokenDeployment.address,
    timelockDeployment.address,
    votingDelay,
    votingPeriod,
    proposalThreshold,
  ];

  const deployTx = await ShaktiGovernor.getDeployTransaction(...constructorArgs);
  const estimatedGas = await estimateGasWithBuffer(deployTx);
  console.log("Estimated gas:", estimatedGas.toString());

  const shaktiGovernor = await ShaktiGovernor.deploy(...constructorArgs, {
    gasLimit: estimatedGas,
  });

  await shaktiGovernor.waitForDeployment();
  const governorAddress = await shaktiGovernor.getAddress();

  console.log("\nShaktiGovernor deployed to:", governorAddress);
  console.log("Transaction hash:", shaktiGovernor.deploymentTransaction()?.hash);

  // Verify configuration
  const configVotingDelay = await shaktiGovernor.votingDelay();
  const configVotingPeriod = await shaktiGovernor.votingPeriod();
  const configThreshold = await shaktiGovernor.proposalThreshold();
  const quorum = await shaktiGovernor["quorumNumerator()"]();

  console.log("\nGovernor Configuration:");
  console.log("  Voting Delay:", Number(configVotingDelay), "blocks");
  console.log("  Voting Period:", Number(configVotingPeriod), "blocks (~", Math.round(Number(configVotingPeriod) * 2 / 86400), "days)");
  console.log("  Proposal Threshold:", ethers.formatEther(configThreshold), "SHAKTI");
  console.log("  Quorum:", Number(quorum), "%");

  // Save deployment
  await saveDeployment("ShaktiGovernor", {
    address: governorAddress,
    constructorArgs: [
      tokenDeployment.address,
      timelockDeployment.address,
      votingDelay,
      votingPeriod,
      proposalThreshold.toString(),
    ],
    txHash: shaktiGovernor.deploymentTransaction()?.hash,
    deployer: deployer.address,
    network: network.name,
    chainId: network.config.chainId,
    timestamp: new Date().toISOString(),
  });

  console.log("\n✅ ShaktiGovernor deployment complete!");

  return { shaktiGovernor, address: governorAddress };
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
