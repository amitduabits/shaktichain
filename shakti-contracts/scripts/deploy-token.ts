import { ethers, network } from "hardhat";
import * as fs from "fs";
import * as path from "path";

interface DeploymentInfo {
  network: string;
  chainId: number;
  contractAddress: string;
  adminAddress: string;
  holderAddress: string;
  transactionHash: string;
  blockNumber: number;
  timestamp: string;
  gasUsed: string;
  gasPrice: string;
}

async function main(): Promise<void> {
  console.log("\n🔷 SHAKTI Token Deployment Script");
  console.log("=".repeat(50));

  // Get network info
  const networkName = network.name;
  const chainId = (await ethers.provider.getNetwork()).chainId;
  console.log(`\n📡 Network: ${networkName} (Chain ID: ${chainId})`);

  // Get signers
  const [deployer] = await ethers.getSigners();
  console.log(`\n👤 Deployer: ${deployer.address}`);

  // Check balance
  const balance = await ethers.provider.getBalance(deployer.address);
  console.log(`💰 Balance: ${ethers.formatEther(balance)} ETH/MATIC`);

  if (balance === 0n) {
    throw new Error("Deployer has no funds. Please fund the account before deployment.");
  }

  // Configuration
  // In production, these should be different addresses for security
  const adminAddress = deployer.address; // Controls roles
  const holderAddress = deployer.address; // Receives initial supply

  console.log(`\n⚙️  Configuration:`);
  console.log(`   Admin: ${adminAddress}`);
  console.log(`   Initial Token Holder: ${holderAddress}`);

  // Deploy contract
  console.log(`\n🚀 Deploying ShaktiToken...`);

  const ShaktiTokenFactory = await ethers.getContractFactory("ShaktiToken");

  // Estimate gas
  const deployTx = await ShaktiTokenFactory.getDeployTransaction(adminAddress, holderAddress);
  const estimatedGas = await ethers.provider.estimateGas(deployTx);
  const feeData = await ethers.provider.getFeeData();
  const gasPrice = feeData.gasPrice || 0n;

  console.log(`   Estimated Gas: ${estimatedGas.toString()}`);
  console.log(`   Gas Price: ${ethers.formatUnits(gasPrice, "gwei")} gwei`);
  console.log(`   Estimated Cost: ${ethers.formatEther(estimatedGas * gasPrice)} ETH/MATIC`);

  // Deploy
  const token = await ShaktiTokenFactory.deploy(adminAddress, holderAddress);
  console.log(`\n⏳ Waiting for deployment transaction...`);
  console.log(`   TX Hash: ${token.deploymentTransaction()?.hash}`);

  await token.waitForDeployment();
  const contractAddress = await token.getAddress();

  // Get transaction receipt
  const txHash = token.deploymentTransaction()?.hash;
  const receipt = txHash ? await ethers.provider.getTransactionReceipt(txHash) : null;

  console.log(`\n✅ ShaktiToken deployed successfully!`);
  console.log(`   Contract Address: ${contractAddress}`);
  console.log(`   Block Number: ${receipt?.blockNumber}`);
  console.log(`   Gas Used: ${receipt?.gasUsed.toString()}`);

  // Verify deployment
  console.log(`\n🔍 Verifying deployment...`);

  const name = await token.name();
  const symbol = await token.symbol();
  const totalSupply = await token.totalSupply();
  const holderBalance = await token.balanceOf(holderAddress);

  console.log(`   Name: ${name}`);
  console.log(`   Symbol: ${symbol}`);
  console.log(`   Total Supply: ${ethers.formatEther(totalSupply)} SHAKTI`);
  console.log(`   Holder Balance: ${ethers.formatEther(holderBalance)} SHAKTI`);

  // Verify roles
  const DEFAULT_ADMIN_ROLE = ethers.ZeroHash;
  const MINTER_ROLE = ethers.keccak256(ethers.toUtf8Bytes("MINTER_ROLE"));
  const PAUSER_ROLE = ethers.keccak256(ethers.toUtf8Bytes("PAUSER_ROLE"));
  const BURNER_ROLE = ethers.keccak256(ethers.toUtf8Bytes("BURNER_ROLE"));

  const hasAdminRole = await token.hasRole(DEFAULT_ADMIN_ROLE, adminAddress);
  const hasMinterRole = await token.hasRole(MINTER_ROLE, adminAddress);
  const hasPauserRole = await token.hasRole(PAUSER_ROLE, adminAddress);
  const hasBurnerRole = await token.hasRole(BURNER_ROLE, adminAddress);

  console.log(`\n🔐 Role Verification:`);
  console.log(`   Admin has DEFAULT_ADMIN_ROLE: ${hasAdminRole}`);
  console.log(`   Admin has MINTER_ROLE: ${hasMinterRole}`);
  console.log(`   Admin has PAUSER_ROLE: ${hasPauserRole}`);
  console.log(`   Admin has BURNER_ROLE: ${hasBurnerRole}`);

  // Save deployment info
  const deploymentInfo: DeploymentInfo = {
    network: networkName,
    chainId: Number(chainId),
    contractAddress,
    adminAddress,
    holderAddress,
    transactionHash: txHash || "",
    blockNumber: receipt?.blockNumber || 0,
    timestamp: new Date().toISOString(),
    gasUsed: receipt?.gasUsed.toString() || "0",
    gasPrice: gasPrice.toString(),
  };

  // Save to file
  const deploymentsDir = path.join(__dirname, "..", "deployments");
  if (!fs.existsSync(deploymentsDir)) {
    fs.mkdirSync(deploymentsDir, { recursive: true });
  }

  const deploymentFile = path.join(deploymentsDir, `${networkName}-deployment.json`);
  fs.writeFileSync(deploymentFile, JSON.stringify(deploymentInfo, null, 2));
  console.log(`\n💾 Deployment info saved to: ${deploymentFile}`);

  // Print verification command for Polygonscan
  if (networkName === "polygonMumbai" || networkName === "polygonMainnet") {
    console.log(`\n📋 To verify on Polygonscan, run:`);
    console.log(`   npx hardhat verify --network ${networkName} ${contractAddress} ${adminAddress} ${holderAddress}`);
  }

  console.log("\n" + "=".repeat(50));
  console.log("🎉 Deployment Complete!\n");

  return;
}

// Execute
main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("\n❌ Deployment failed:");
    console.error(error);
    process.exit(1);
  });
