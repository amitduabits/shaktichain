import { ethers, network } from "hardhat";
import * as fs from "fs";
import * as path from "path";

interface DeploymentInfo {
  network: string;
  chainId: number;
  stakingPoolAddress: string;
  stakingTokenAddress: string;
  adminAddress: string;
  rewardRate: number;
  transactionHash: string;
  blockNumber: number;
  timestamp: string;
  gasUsed: string;
}

async function main(): Promise<void> {
  console.log("\n🔷 SHAKTI Staking Pool Deployment Script");
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

  // Load ShaktiToken deployment info
  const deploymentsDir = path.join(__dirname, "..", "deployments");
  const tokenDeploymentFile = path.join(deploymentsDir, `${networkName}-deployment.json`);

  let stakingTokenAddress: string;

  if (fs.existsSync(tokenDeploymentFile)) {
    const tokenDeployment = JSON.parse(fs.readFileSync(tokenDeploymentFile, "utf-8"));
    stakingTokenAddress = tokenDeployment.contractAddress;
    console.log(`\n📄 Found existing ShaktiToken deployment: ${stakingTokenAddress}`);
  } else {
    // For localhost/testing, deploy a new token
    console.log(`\n⚠️  No ShaktiToken deployment found for ${networkName}`);
    console.log(`   Deploying new ShaktiToken for testing...`);

    const ShaktiTokenFactory = await ethers.getContractFactory("ShaktiToken");
    const token = await ShaktiTokenFactory.deploy(deployer.address, deployer.address);
    await token.waitForDeployment();
    stakingTokenAddress = await token.getAddress();
    console.log(`   ShaktiToken deployed to: ${stakingTokenAddress}`);
  }

  // Configuration
  const adminAddress = deployer.address;
  const initialRewardRate = 800; // 8% APY in basis points

  console.log(`\n⚙️  Configuration:`);
  console.log(`   Staking Token: ${stakingTokenAddress}`);
  console.log(`   Admin: ${adminAddress}`);
  console.log(`   Initial Reward Rate: ${initialRewardRate / 100}% APY`);

  // Deploy StakingPool
  console.log(`\n🚀 Deploying StakingPool...`);

  const StakingPoolFactory = await ethers.getContractFactory("StakingPool");

  // Estimate gas
  const deployTx = await StakingPoolFactory.getDeployTransaction(
    stakingTokenAddress,
    adminAddress,
    initialRewardRate
  );
  const estimatedGas = await ethers.provider.estimateGas(deployTx);
  const feeData = await ethers.provider.getFeeData();
  const gasPrice = feeData.gasPrice || 0n;

  console.log(`   Estimated Gas: ${estimatedGas.toString()}`);
  console.log(`   Gas Price: ${ethers.formatUnits(gasPrice, "gwei")} gwei`);
  console.log(`   Estimated Cost: ${ethers.formatEther(estimatedGas * gasPrice)} ETH/MATIC`);

  // Deploy
  const stakingPool = await StakingPoolFactory.deploy(
    stakingTokenAddress,
    adminAddress,
    initialRewardRate
  );

  console.log(`\n⏳ Waiting for deployment transaction...`);
  console.log(`   TX Hash: ${stakingPool.deploymentTransaction()?.hash}`);

  await stakingPool.waitForDeployment();
  const stakingPoolAddress = await stakingPool.getAddress();

  // Get receipt
  const txHash = stakingPool.deploymentTransaction()?.hash;
  const receipt = txHash ? await ethers.provider.getTransactionReceipt(txHash) : null;

  console.log(`\n✅ StakingPool deployed successfully!`);
  console.log(`   Contract Address: ${stakingPoolAddress}`);
  console.log(`   Block Number: ${receipt?.blockNumber}`);
  console.log(`   Gas Used: ${receipt?.gasUsed.toString()}`);

  // Verify deployment
  console.log(`\n🔍 Verifying deployment...`);

  const storedToken = await stakingPool.stakingToken();
  const storedRate = await stakingPool.annualRewardRate();
  const totalStaked = await stakingPool.totalStaked();

  console.log(`   Staking Token: ${storedToken}`);
  console.log(`   Annual Reward Rate: ${Number(storedRate) / 100}%`);
  console.log(`   Total Staked: ${ethers.formatEther(totalStaked)} SHAKTI`);

  // Verify roles
  const GOVERNANCE_ROLE = ethers.keccak256(ethers.toUtf8Bytes("GOVERNANCE_ROLE"));
  const PAUSER_ROLE = ethers.keccak256(ethers.toUtf8Bytes("PAUSER_ROLE"));

  const hasGovernance = await stakingPool.hasRole(GOVERNANCE_ROLE, adminAddress);
  const hasPauser = await stakingPool.hasRole(PAUSER_ROLE, adminAddress);

  console.log(`\n🔐 Role Verification:`);
  console.log(`   Admin has GOVERNANCE_ROLE: ${hasGovernance}`);
  console.log(`   Admin has PAUSER_ROLE: ${hasPauser}`);

  // Fund staking pool with rewards (for localhost)
  if (networkName === "localhost" || networkName === "hardhat") {
    console.log(`\n💰 Funding staking pool with rewards...`);
    const token = await ethers.getContractAt("ShaktiToken", stakingTokenAddress);
    const rewardFunding = ethers.parseEther("10000000"); // 10M tokens for rewards

    const deployerBalance = await token.balanceOf(deployer.address);
    if (deployerBalance >= rewardFunding) {
      await token.transfer(stakingPoolAddress, rewardFunding);
      console.log(`   Transferred ${ethers.formatEther(rewardFunding)} SHAKTI for rewards`);
    } else {
      console.log(`   ⚠️  Insufficient balance to fund rewards pool`);
    }
  }

  // Save deployment info
  const deploymentInfo: DeploymentInfo = {
    network: networkName,
    chainId: Number(chainId),
    stakingPoolAddress,
    stakingTokenAddress,
    adminAddress,
    rewardRate: initialRewardRate,
    transactionHash: txHash || "",
    blockNumber: receipt?.blockNumber || 0,
    timestamp: new Date().toISOString(),
    gasUsed: receipt?.gasUsed.toString() || "0",
  };

  if (!fs.existsSync(deploymentsDir)) {
    fs.mkdirSync(deploymentsDir, { recursive: true });
  }

  const deploymentFile = path.join(deploymentsDir, `${networkName}-staking-deployment.json`);
  fs.writeFileSync(deploymentFile, JSON.stringify(deploymentInfo, null, 2));
  console.log(`\n💾 Deployment info saved to: ${deploymentFile}`);

  // Print verification command
  if (networkName === "polygonMumbai" || networkName === "polygonMainnet") {
    console.log(`\n📋 To verify on Polygonscan, run:`);
    console.log(`   npx hardhat verify --network ${networkName} ${stakingPoolAddress} ${stakingTokenAddress} ${adminAddress} ${initialRewardRate}`);
  }

  // Print next steps
  console.log("\n" + "=".repeat(50));
  console.log("📝 Next Steps:");
  console.log("   1. Fund the staking pool with reward tokens");
  console.log("   2. Configure additional governance addresses");
  console.log("   3. Verify contract on block explorer");
  console.log("   4. Test staking functionality");
  console.log("=".repeat(50));
  console.log("🎉 Staking Pool Deployment Complete!\n");

  return;
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("\n❌ Deployment failed:");
    console.error(error);
    process.exit(1);
  });
