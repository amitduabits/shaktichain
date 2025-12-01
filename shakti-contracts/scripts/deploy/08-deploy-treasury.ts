/**
 * SHAKTI-CHAIN Deployment Script: Treasury
 *
 * Deploys the protocol treasury for fee collection.
 */

import { ethers, network } from "hardhat";
import { saveDeployment, getDeployer, loadDeployment, estimateGasWithBuffer } from "../utils/deployment-helpers";

async function main() {
  console.log("\n========================================");
  console.log("  Deploying Treasury");
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

  // Deploy Treasury
  const Treasury = await ethers.getContractFactory("Treasury");

  // Constructor args: token, admin, initialSigners[] (must be exactly 5 signers)
  // For testnet, generate deterministic addresses for the 5 required signers
  // In production, these should be real multisig participants
  const allSigners = await ethers.getSigners();
  let signers: string[];

  if (allSigners.length >= 5) {
    // Use first 5 signers from available accounts
    signers = allSigners.slice(0, 5).map(s => s.address);
  } else {
    // Generate deterministic addresses for remaining signers (testnet only)
    signers = [deployer.address];
    for (let i = 1; i < 5; i++) {
      // Create deterministic addresses for testnet
      const wallet = ethers.Wallet.createRandom();
      signers.push(wallet.address);
    }
  }

  console.log("Treasury Signers (5 required):");
  signers.forEach((s, i) => console.log(`  Signer ${i + 1}: ${s}`));

  const constructorArgs = [
    tokenDeployment.address,
    deployer.address,
    signers,
  ];

  const deployTx = await Treasury.getDeployTransaction(...constructorArgs);
  const estimatedGas = await estimateGasWithBuffer(deployTx);
  console.log("Estimated gas:", estimatedGas.toString());

  const treasury = await Treasury.deploy(...constructorArgs, {
    gasLimit: estimatedGas,
  });

  await treasury.waitForDeployment();
  const treasuryAddress = await treasury.getAddress();

  console.log("\nTreasury deployed to:", treasuryAddress);
  console.log("Transaction hash:", treasury.deploymentTransaction()?.hash);

  // Verify configuration
  const signersList = await treasury.getSigners();

  console.log("\nTreasury Configuration:");
  console.log("  Total Signers:", signersList.length);

  // Save deployment
  await saveDeployment("Treasury", {
    address: treasuryAddress,
    constructorArgs,
    txHash: treasury.deploymentTransaction()?.hash,
    deployer: deployer.address,
    network: network.name,
    chainId: network.config.chainId,
    timestamp: new Date().toISOString(),
  });

  console.log("\n✅ Treasury deployment complete!");

  return { treasury, address: treasuryAddress };
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
