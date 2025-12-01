import { ethers, network } from "hardhat";
import * as fs from "fs";
import * as path from "path";

interface DeploymentInfo {
  network: string;
  chainId: number;
  escrowAddress: string;
  tokenAddress: string;
  treasuryAddress: string;
  adminAddress: string;
  platformFee: string;
  feeBurnPercentage: string;
  transactionHash: string;
  blockNumber: number;
  timestamp: string;
  gasUsed: string;
}

async function main(): Promise<void> {
  console.log("\n🔷 SHAKTI Energy Escrow Deployment Script");
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

  // Configuration
  // Platform fee: 2% (200 basis points)
  // Fee burn percentage: 30% (3000 basis points of fee is burned)
  const platformFee = 200; // 2%
  const feeBurnPercentage = 3000; // 30% of fees burned
  const treasuryAddress = deployer.address; // Use deployer as treasury initially

  console.log(`\n⚙️  Configuration:`);
  console.log(`   Token: ${tokenAddress}`);
  console.log(`   Treasury: ${treasuryAddress}`);
  console.log(`   Platform Fee: ${platformFee / 100}% (${platformFee} basis points)`);
  console.log(`   Fee Burn: ${feeBurnPercentage / 100}% of fees burned`);
  console.log(`   Dispute Window: 24 hours`);

  // Deploy EnergyEscrow
  console.log(`\n🚀 Deploying EnergyEscrow...`);

  const EnergyEscrowFactory = await ethers.getContractFactory("EnergyEscrow");

  // Estimate gas
  const deployTx = await EnergyEscrowFactory.getDeployTransaction(
    tokenAddress,
    treasuryAddress,
    deployer.address,
    platformFee,
    feeBurnPercentage
  );
  const estimatedGas = await ethers.provider.estimateGas(deployTx);
  const feeData = await ethers.provider.getFeeData();
  const gasPrice = feeData.gasPrice || 0n;

  console.log(`   Estimated Gas: ${estimatedGas.toString()}`);
  console.log(`   Gas Price: ${ethers.formatUnits(gasPrice, "gwei")} gwei`);
  console.log(`   Estimated Cost: ${ethers.formatEther(estimatedGas * gasPrice)} ETH/MATIC`);

  // Deploy
  const escrow = await EnergyEscrowFactory.deploy(
    tokenAddress,
    treasuryAddress,
    deployer.address,
    platformFee,
    feeBurnPercentage
  );

  console.log(`\n⏳ Waiting for deployment transaction...`);
  console.log(`   TX Hash: ${escrow.deploymentTransaction()?.hash}`);

  await escrow.waitForDeployment();
  const escrowAddress = await escrow.getAddress();

  // Get receipt
  const txHash = escrow.deploymentTransaction()?.hash;
  const receipt = txHash ? await ethers.provider.getTransactionReceipt(txHash) : null;

  console.log(`\n✅ EnergyEscrow deployed successfully!`);
  console.log(`   Contract Address: ${escrowAddress}`);
  console.log(`   Block Number: ${receipt?.blockNumber}`);
  console.log(`   Gas Used: ${receipt?.gasUsed.toString()}`);

  // Verify deployment
  console.log(`\n🔍 Verifying deployment...`);

  const storedFee = await escrow.platformFeePercentage();
  const storedBurn = await escrow.feeBurnPercentage();
  const storedTreasury = await escrow.treasury();

  console.log(`   Platform Fee: ${Number(storedFee) / 100}%`);
  console.log(`   Burn Percentage: ${Number(storedBurn) / 100}%`);
  console.log(`   Treasury: ${storedTreasury}`);

  // Verify roles
  const ARBITER_ROLE = ethers.keccak256(ethers.toUtf8Bytes("ARBITER_ROLE"));
  const AUCTION_ROLE = ethers.keccak256(ethers.toUtf8Bytes("AUCTION_ROLE"));
  const TREASURY_ROLE = ethers.keccak256(ethers.toUtf8Bytes("TREASURY_ROLE"));

  const hasArbiter = await escrow.hasRole(ARBITER_ROLE, deployer.address);
  const hasTreasury = await escrow.hasRole(TREASURY_ROLE, deployer.address);

  console.log(`\n🔐 Role Verification:`);
  console.log(`   Admin has ARBITER_ROLE: ${hasArbiter}`);
  console.log(`   Admin has TREASURY_ROLE: ${hasTreasury}`);

  // Load auction deployment to grant AUCTION_ROLE
  const auctionDeploymentFile = path.join(deploymentsDir, `${networkName}-auction-deployment.json`);
  if (fs.existsSync(auctionDeploymentFile)) {
    const auctionDeployment = JSON.parse(fs.readFileSync(auctionDeploymentFile, "utf-8"));
    console.log(`\n🔗 Granting AUCTION_ROLE to EnergyAuction...`);
    const tx = await escrow.setAuctionContract(auctionDeployment.auctionAddress);
    await tx.wait();
    console.log(`   Granted AUCTION_ROLE to: ${auctionDeployment.auctionAddress}`);
  }

  // Calculate sample fees
  console.log(`\n💰 Fee Calculation Example:`);
  const sampleAmount = ethers.parseEther("1000"); // 1000 SHAKTI
  const [pFee, burnAmt, treasuryAmt, sellerAmt] = await escrow.calculateFees(sampleAmount);
  console.log(`   For 1000 SHAKTI transaction:`);
  console.log(`   - Platform Fee: ${ethers.formatEther(pFee)} SHAKTI`);
  console.log(`   - Burn Amount: ${ethers.formatEther(burnAmt)} SHAKTI`);
  console.log(`   - Treasury Gets: ${ethers.formatEther(treasuryAmt)} SHAKTI`);
  console.log(`   - Seller Gets: ${ethers.formatEther(sellerAmt)} SHAKTI`);

  // Save deployment info
  if (!fs.existsSync(deploymentsDir)) {
    fs.mkdirSync(deploymentsDir, { recursive: true });
  }

  const deploymentInfo: DeploymentInfo = {
    network: networkName,
    chainId: Number(chainId),
    escrowAddress,
    tokenAddress,
    treasuryAddress,
    adminAddress: deployer.address,
    platformFee: platformFee.toString(),
    feeBurnPercentage: feeBurnPercentage.toString(),
    transactionHash: txHash || "",
    blockNumber: receipt?.blockNumber || 0,
    timestamp: new Date().toISOString(),
    gasUsed: receipt?.gasUsed.toString() || "0",
  };

  const deploymentFile = path.join(deploymentsDir, `${networkName}-escrow-deployment.json`);
  fs.writeFileSync(deploymentFile, JSON.stringify(deploymentInfo, null, 2));
  console.log(`\n💾 Deployment info saved to: ${deploymentFile}`);

  // Print verification command
  if (networkName === "polygonMumbai" || networkName === "polygonMainnet") {
    console.log(`\n📋 To verify on Polygonscan, run:`);
    console.log(`   npx hardhat verify --network ${networkName} ${escrowAddress} ${tokenAddress} ${treasuryAddress} ${deployer.address} ${platformFee} ${feeBurnPercentage}`);
  }

  // Print next steps
  console.log("\n" + "=".repeat(50));
  console.log("📝 Next Steps:");
  console.log("   1. Grant AUCTION_ROLE to EnergyAuction contract");
  console.log("   2. Grant ARBITER_ROLE to dispute arbiters");
  console.log("   3. Update treasury address if needed");
  console.log("   4. Configure EnergyAuction to use this escrow");
  console.log("=".repeat(50));
  console.log("🎉 Energy Escrow Deployment Complete!\n");

  return;
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("\n❌ Deployment failed:");
    console.error(error);
    process.exit(1);
  });
