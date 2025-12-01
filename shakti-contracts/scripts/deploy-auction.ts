import { ethers, network } from "hardhat";
import * as fs from "fs";
import * as path from "path";

interface DeploymentInfo {
  network: string;
  chainId: number;
  auctionAddress: string;
  tokenAddress: string;
  registryAddress: string;
  adminAddress: string;
  minPrice: string;
  maxPrice: string;
  transactionHash: string;
  blockNumber: number;
  timestamp: string;
  gasUsed: string;
}

async function main(): Promise<void> {
  console.log("\n🔷 SHAKTI Energy Auction Deployment Script");
  console.log("=".repeat(50));

  // Get network info
  const networkName = network.name;
  const chainId = (await ethers.provider.getNetwork()).chainId;
  console.log(`\n📡 Network: ${networkName} (Chain ID: ${chainId})`);

  // Get deployer
  const [deployer] = await ethers.getSigners();
  console.log(`\n👤 Deployer: ${deployer.address}`);

  // Check balance
  const balance = await ethers.provider.getBalance(deployer.address);
  console.log(`💰 Balance: ${ethers.formatEther(balance)} ETH/MATIC`);

  if (balance === 0n) {
    throw new Error("Deployer has no funds. Please fund the account before deployment.");
  }

  // Load dependencies
  const deploymentsDir = path.join(__dirname, "..", "deployments");
  let tokenAddress: string;
  let registryAddress: string = ethers.ZeroAddress;

  // Load token deployment
  const tokenDeploymentFile = path.join(deploymentsDir, `${networkName}-deployment.json`);
  if (fs.existsSync(tokenDeploymentFile)) {
    const tokenDeployment = JSON.parse(fs.readFileSync(tokenDeploymentFile, "utf-8"));
    tokenAddress = tokenDeployment.contractAddress;
    console.log(`\n📄 Found ShaktiToken: ${tokenAddress}`);
  } else {
    console.log(`\n⚠️  No ShaktiToken deployment found, deploying new one...`);
    const ShaktiTokenFactory = await ethers.getContractFactory("ShaktiToken");
    const token = await ShaktiTokenFactory.deploy(deployer.address, deployer.address);
    await token.waitForDeployment();
    tokenAddress = await token.getAddress();
    console.log(`   ShaktiToken deployed to: ${tokenAddress}`);
  }

  // Load registry deployment
  const registryDeploymentFile = path.join(deploymentsDir, `${networkName}-registry-deployment.json`);
  if (fs.existsSync(registryDeploymentFile)) {
    const registryDeployment = JSON.parse(fs.readFileSync(registryDeploymentFile, "utf-8"));
    registryAddress = registryDeployment.registryAddress;
    console.log(`📄 Found EnergyRegistry: ${registryAddress}`);
  }

  // Configuration
  // Price bounds: 2-15 INR/kWh (converted to per Wh with 18 decimals)
  // 2 INR/kWh = 0.002 INR/Wh = 2e15 wei per Wh
  const minPrice = ethers.parseEther("0.002"); // 2 INR/kWh
  const maxPrice = ethers.parseEther("0.015"); // 15 INR/kWh

  console.log(`\n⚙️  Configuration:`);
  console.log(`   Token: ${tokenAddress}`);
  console.log(`   Registry: ${registryAddress}`);
  console.log(`   Min Price: ${ethers.formatEther(minPrice)} INR/Wh (${2} INR/kWh)`);
  console.log(`   Max Price: ${ethers.formatEther(maxPrice)} INR/Wh (${15} INR/kWh)`);

  // Deploy EnergyAuction
  console.log(`\n🚀 Deploying EnergyAuction...`);

  const EnergyAuctionFactory = await ethers.getContractFactory("EnergyAuction");

  // Estimate gas
  const deployTx = await EnergyAuctionFactory.getDeployTransaction(
    tokenAddress,
    registryAddress,
    deployer.address,
    minPrice,
    maxPrice
  );
  const estimatedGas = await ethers.provider.estimateGas(deployTx);
  const feeData = await ethers.provider.getFeeData();
  const gasPrice = feeData.gasPrice || 0n;

  console.log(`   Estimated Gas: ${estimatedGas.toString()}`);
  console.log(`   Gas Price: ${ethers.formatUnits(gasPrice, "gwei")} gwei`);
  console.log(`   Estimated Cost: ${ethers.formatEther(estimatedGas * gasPrice)} ETH/MATIC`);

  // Deploy
  const auction = await EnergyAuctionFactory.deploy(
    tokenAddress,
    registryAddress,
    deployer.address,
    minPrice,
    maxPrice
  );

  console.log(`\n⏳ Waiting for deployment transaction...`);
  console.log(`   TX Hash: ${auction.deploymentTransaction()?.hash}`);

  await auction.waitForDeployment();
  const auctionAddress = await auction.getAddress();

  // Get receipt
  const txHash = auction.deploymentTransaction()?.hash;
  const receipt = txHash ? await ethers.provider.getTransactionReceipt(txHash) : null;

  console.log(`\n✅ EnergyAuction deployed successfully!`);
  console.log(`   Contract Address: ${auctionAddress}`);
  console.log(`   Block Number: ${receipt?.blockNumber}`);
  console.log(`   Gas Used: ${receipt?.gasUsed.toString()}`);

  // Verify deployment
  console.log(`\n🔍 Verifying deployment...`);

  const storedMinPrice = await auction.minPrice();
  const storedMaxPrice = await auction.maxPrice();
  const storedToken = await auction.shaktiToken();

  console.log(`   Token: ${storedToken}`);
  console.log(`   Min Price: ${ethers.formatEther(storedMinPrice)} INR/Wh`);
  console.log(`   Max Price: ${ethers.formatEther(storedMaxPrice)} INR/Wh`);

  // Verify roles
  const AUCTIONEER_ROLE = ethers.keccak256(ethers.toUtf8Bytes("AUCTIONEER_ROLE"));
  const OPERATOR_ROLE = ethers.keccak256(ethers.toUtf8Bytes("OPERATOR_ROLE"));

  const hasAuctioneer = await auction.hasRole(AUCTIONEER_ROLE, deployer.address);
  const hasOperator = await auction.hasRole(OPERATOR_ROLE, deployer.address);

  console.log(`\n🔐 Role Verification:`);
  console.log(`   Admin has AUCTIONEER_ROLE: ${hasAuctioneer}`);
  console.log(`   Admin has OPERATOR_ROLE: ${hasOperator}`);

  // Create test auction round for localhost
  if (networkName === "localhost" || networkName === "hardhat") {
    console.log(`\n🏪 Creating test auction round...`);
    const duration = 10 * 60; // 10 minutes
    const tx = await auction.createAuctionRound(duration);
    await tx.wait();
    console.log(`   Created auction round #${await auction.currentRoundId()}`);
    console.log(`   Duration: ${duration / 60} minutes`);
  }

  // Save deployment info
  if (!fs.existsSync(deploymentsDir)) {
    fs.mkdirSync(deploymentsDir, { recursive: true });
  }

  const deploymentInfo: DeploymentInfo = {
    network: networkName,
    chainId: Number(chainId),
    auctionAddress,
    tokenAddress,
    registryAddress,
    adminAddress: deployer.address,
    minPrice: minPrice.toString(),
    maxPrice: maxPrice.toString(),
    transactionHash: txHash || "",
    blockNumber: receipt?.blockNumber || 0,
    timestamp: new Date().toISOString(),
    gasUsed: receipt?.gasUsed.toString() || "0",
  };

  const deploymentFile = path.join(deploymentsDir, `${networkName}-auction-deployment.json`);
  fs.writeFileSync(deploymentFile, JSON.stringify(deploymentInfo, null, 2));
  console.log(`\n💾 Deployment info saved to: ${deploymentFile}`);

  // Print verification command
  if (networkName === "polygonMumbai" || networkName === "polygonMainnet") {
    console.log(`\n📋 To verify on Polygonscan, run:`);
    console.log(`   npx hardhat verify --network ${networkName} ${auctionAddress} ${tokenAddress} ${registryAddress} ${deployer.address} ${minPrice} ${maxPrice}`);
  }

  // Print next steps
  console.log("\n" + "=".repeat(50));
  console.log("📝 Next Steps:");
  console.log("   1. Grant AUCTIONEER_ROLE to auction operators");
  console.log("   2. Grant OPERATOR_ROLE to clearing bots");
  console.log("   3. Create first auction round");
  console.log("   4. Integrate with frontend for order submission");
  console.log("=".repeat(50));
  console.log("🎉 Energy Auction Deployment Complete!\n");

  return;
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("\n❌ Deployment failed:");
    console.error(error);
    process.exit(1);
  });
