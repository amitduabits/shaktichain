/**
 * SHAKTI-CHAIN Deployment Script: ShaktiToken
 *
 * Deploys the ERC20 token with permit, burn, and role-based access.
 */

import { ethers, network } from "hardhat";
import { saveDeployment, getDeployer, estimateGasWithBuffer } from "../utils/deployment-helpers";

async function main() {
  console.log("\n========================================");
  console.log("  Deploying ShaktiToken");
  console.log("  Network:", network.name);
  console.log("========================================\n");

  const deployer = await getDeployer();
  console.log("Deployer:", deployer.address);
  console.log("Balance:", ethers.formatEther(await ethers.provider.getBalance(deployer.address)), "MATIC\n");

  // Deploy ShaktiToken
  const ShaktiToken = await ethers.getContractFactory("ShaktiToken");

  // Constructor args: defaultAdmin, minter
  const constructorArgs = [deployer.address, deployer.address];

  // Estimate gas
  const deployTx = await ShaktiToken.getDeployTransaction(...constructorArgs);
  const estimatedGas = await estimateGasWithBuffer(deployTx);
  console.log("Estimated gas:", estimatedGas.toString());

  const shaktiToken = await ShaktiToken.deploy(...constructorArgs, {
    gasLimit: estimatedGas,
  });

  await shaktiToken.waitForDeployment();
  const tokenAddress = await shaktiToken.getAddress();

  console.log("\nShaktiToken deployed to:", tokenAddress);
  console.log("Transaction hash:", shaktiToken.deploymentTransaction()?.hash);

  // Verify initial state
  const name = await shaktiToken.name();
  const symbol = await shaktiToken.symbol();
  const totalSupply = await shaktiToken.totalSupply();
  const maxSupply = await shaktiToken.MAX_SUPPLY();

  console.log("\nToken Details:");
  console.log("  Name:", name);
  console.log("  Symbol:", symbol);
  console.log("  Initial Supply:", ethers.formatEther(totalSupply), "SHAKTI");
  console.log("  Max Supply:", ethers.formatEther(maxSupply), "SHAKTI");

  // Save deployment
  await saveDeployment("ShaktiToken", {
    address: tokenAddress,
    constructorArgs,
    txHash: shaktiToken.deploymentTransaction()?.hash,
    deployer: deployer.address,
    network: network.name,
    chainId: network.config.chainId,
    timestamp: new Date().toISOString(),
  });

  console.log("\n✅ ShaktiToken deployment complete!");

  return { shaktiToken, address: tokenAddress };
}

// Execute if running directly
if (require.main === module) {
  main()
    .then(() => process.exit(0))
    .catch((error) => {
      console.error(error);
      process.exit(1);
    });
}

export default main;
