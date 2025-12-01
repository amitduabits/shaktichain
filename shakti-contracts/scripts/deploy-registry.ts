import { ethers, network } from "hardhat";
import * as fs from "fs";
import * as path from "path";

interface DeploymentInfo {
  network: string;
  chainId: number;
  registryAddress: string;
  adminAddress: string;
  transactionHash: string;
  blockNumber: number;
  timestamp: string;
  gasUsed: string;
}

async function main(): Promise<void> {
  console.log("\n🔷 SHAKTI Energy Registry Deployment Script");
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

  // Configuration
  const adminAddress = deployer.address;

  console.log(`\n⚙️  Configuration:`);
  console.log(`   Admin: ${adminAddress}`);

  // Deploy EnergyRegistry
  console.log(`\n🚀 Deploying EnergyRegistry...`);

  const EnergyRegistryFactory = await ethers.getContractFactory("EnergyRegistry");

  // Estimate gas
  const deployTx = await EnergyRegistryFactory.getDeployTransaction(adminAddress);
  const estimatedGas = await ethers.provider.estimateGas(deployTx);
  const feeData = await ethers.provider.getFeeData();
  const gasPrice = feeData.gasPrice || 0n;

  console.log(`   Estimated Gas: ${estimatedGas.toString()}`);
  console.log(`   Gas Price: ${ethers.formatUnits(gasPrice, "gwei")} gwei`);
  console.log(`   Estimated Cost: ${ethers.formatEther(estimatedGas * gasPrice)} ETH/MATIC`);

  // Deploy
  const registry = await EnergyRegistryFactory.deploy(adminAddress);

  console.log(`\n⏳ Waiting for deployment transaction...`);
  console.log(`   TX Hash: ${registry.deploymentTransaction()?.hash}`);

  await registry.waitForDeployment();
  const registryAddress = await registry.getAddress();

  // Get receipt
  const txHash = registry.deploymentTransaction()?.hash;
  const receipt = txHash ? await ethers.provider.getTransactionReceipt(txHash) : null;

  console.log(`\n✅ EnergyRegistry deployed successfully!`);
  console.log(`   Contract Address: ${registryAddress}`);
  console.log(`   Block Number: ${receipt?.blockNumber}`);
  console.log(`   Gas Used: ${receipt?.gasUsed.toString()}`);

  // Verify deployment
  console.log(`\n🔍 Verifying deployment...`);

  const totalProsumers = await registry.totalProsumers();
  const totalEVs = await registry.totalEVs();
  const totalDISCOMs = await registry.totalDISCOMs();

  console.log(`   Total Prosumers: ${totalProsumers}`);
  console.log(`   Total EVs: ${totalEVs}`);
  console.log(`   Total DISCOMs: ${totalDISCOMs}`);

  // Verify roles
  const REGISTRAR_ROLE = ethers.keccak256(ethers.toUtf8Bytes("REGISTRAR_ROLE"));
  const VERIFIER_ROLE = ethers.keccak256(ethers.toUtf8Bytes("VERIFIER_ROLE"));
  const DISCOM_MANAGER_ROLE = ethers.keccak256(ethers.toUtf8Bytes("DISCOM_MANAGER_ROLE"));

  const hasRegistrar = await registry.hasRole(REGISTRAR_ROLE, adminAddress);
  const hasVerifier = await registry.hasRole(VERIFIER_ROLE, adminAddress);
  const hasDiscomManager = await registry.hasRole(DISCOM_MANAGER_ROLE, adminAddress);

  console.log(`\n🔐 Role Verification:`);
  console.log(`   Admin has REGISTRAR_ROLE: ${hasRegistrar}`);
  console.log(`   Admin has VERIFIER_ROLE: ${hasVerifier}`);
  console.log(`   Admin has DISCOM_MANAGER_ROLE: ${hasDiscomManager}`);

  // Setup initial DISCOM for testing (localhost only)
  if (networkName === "localhost" || networkName === "hardhat") {
    console.log(`\n🏢 Setting up initial DISCOM...`);

    const licenseHash = ethers.keccak256(ethers.toUtf8Bytes("SHAKTI_DISCOM_LICENSE"));
    const tx = await registry.registerDISCOM(licenseHash, "Demo Region");
    const receipt = await tx.wait();

    const event = receipt?.logs.find((log: any) => {
      try {
        return registry.interface.parseLog(log)?.name === "DISCOMRegistered";
      } catch {
        return false;
      }
    });

    if (event) {
      const parsed = registry.interface.parseLog(event);
      console.log(`   DISCOM ID: ${parsed?.args?.[0]}`);
      console.log(`   Region: ${parsed?.args?.[1]}`);
    }
  }

  // Save deployment info
  const deploymentsDir = path.join(__dirname, "..", "deployments");
  if (!fs.existsSync(deploymentsDir)) {
    fs.mkdirSync(deploymentsDir, { recursive: true });
  }

  const deploymentInfo: DeploymentInfo = {
    network: networkName,
    chainId: Number(chainId),
    registryAddress,
    adminAddress,
    transactionHash: txHash || "",
    blockNumber: receipt?.blockNumber || 0,
    timestamp: new Date().toISOString(),
    gasUsed: receipt?.gasUsed.toString() || "0",
  };

  const deploymentFile = path.join(deploymentsDir, `${networkName}-registry-deployment.json`);
  fs.writeFileSync(deploymentFile, JSON.stringify(deploymentInfo, null, 2));
  console.log(`\n💾 Deployment info saved to: ${deploymentFile}`);

  // Print verification command
  if (networkName === "polygonMumbai" || networkName === "polygonMainnet") {
    console.log(`\n📋 To verify on Polygonscan, run:`);
    console.log(`   npx hardhat verify --network ${networkName} ${registryAddress} ${adminAddress}`);
  }

  // Print next steps
  console.log("\n" + "=".repeat(50));
  console.log("📝 Next Steps:");
  console.log("   1. Register DISCOMs for your service regions");
  console.log("   2. Grant REGISTRAR_ROLE to prosumer registration services");
  console.log("   3. Grant VERIFIER_ROLE to KYC verification services");
  console.log("   4. Integrate with frontend for prosumer registration");
  console.log("=".repeat(50));
  console.log("🎉 Energy Registry Deployment Complete!\n");

  return;
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("\n❌ Deployment failed:");
    console.error(error);
    process.exit(1);
  });
