import { ethers, upgrades, network } from "hardhat";
import * as fs from "fs";
import * as path from "path";

interface UpgradeableDeployment {
  network: string;
  chainId: number;
  contracts: {
    ShaktiTokenV2: {
      proxy: string;
      implementation: string;
      admin: string;
    };
    EnergyAuctionUpgradeable: {
      proxy: string;
      implementation: string;
      admin: string;
    };
    EnergyEscrowUpgradeable: {
      proxy: string;
      implementation: string;
      admin: string;
    };
    ReputationSystemUpgradeable: {
      proxy: string;
      implementation: string;
      admin: string;
    };
  };
  deployer: string;
  timestamp: string;
}

async function main(): Promise<void> {
  console.log("\n🔷 SHAKTI-CHAIN Upgradeable Contracts Deployment");
  console.log("=".repeat(60));
  console.log("Pattern: UUPS (Universal Upgradeable Proxy Standard)");
  console.log("=".repeat(60));

  // Get network info
  const networkName = network.name;
  const chainId = (await ethers.provider.getNetwork()).chainId;
  console.log(`\n📡 Network: ${networkName} (Chain ID: ${chainId})`);

  // Get deployer
  const [deployer] = await ethers.getSigners();
  console.log(`👤 Deployer: ${deployer.address}`);

  // Check balance
  const balance = await ethers.provider.getBalance(deployer.address);
  console.log(`💰 Balance: ${ethers.formatEther(balance)} ETH/MATIC`);

  if (balance === 0n) {
    throw new Error("Deployer has no funds. Please fund the account.");
  }

  const deployment: UpgradeableDeployment = {
    network: networkName,
    chainId: Number(chainId),
    contracts: {
      ShaktiTokenV2: { proxy: "", implementation: "", admin: "" },
      EnergyAuctionUpgradeable: { proxy: "", implementation: "", admin: "" },
      EnergyEscrowUpgradeable: { proxy: "", implementation: "", admin: "" },
      ReputationSystemUpgradeable: { proxy: "", implementation: "", admin: "" },
    },
    deployer: deployer.address,
    timestamp: new Date().toISOString(),
  };

  // ============ Deploy ShaktiTokenV2 ============
  console.log("\n" + "─".repeat(60));
  console.log("📦 Deploying ShaktiTokenV2 (Upgradeable)...");
  console.log("─".repeat(60));

  const ShaktiTokenV2 = await ethers.getContractFactory("ShaktiTokenV2");

  const tokenProxy = await upgrades.deployProxy(
    ShaktiTokenV2,
    [deployer.address, deployer.address], // initialHolder, admin
    {
      initializer: "initialize",
      kind: "uups",
    }
  );
  await tokenProxy.waitForDeployment();

  const tokenProxyAddress = await tokenProxy.getAddress();
  const tokenImplAddress = await upgrades.erc1967.getImplementationAddress(tokenProxyAddress);
  const tokenAdminAddress = await upgrades.erc1967.getAdminAddress(tokenProxyAddress);

  console.log(`   ✅ Proxy: ${tokenProxyAddress}`);
  console.log(`   📋 Implementation: ${tokenImplAddress}`);
  console.log(`   🔐 Admin: ${tokenAdminAddress}`);

  deployment.contracts.ShaktiTokenV2 = {
    proxy: tokenProxyAddress,
    implementation: tokenImplAddress,
    admin: tokenAdminAddress,
  };

  // ============ Deploy EnergyAuctionUpgradeable ============
  console.log("\n" + "─".repeat(60));
  console.log("📦 Deploying EnergyAuctionUpgradeable...");
  console.log("─".repeat(60));

  const EnergyAuctionUpgradeable = await ethers.getContractFactory("EnergyAuctionUpgradeable");

  // Configuration for auction
  const minPrice = ethers.parseEther("0.002"); // 2 INR/kWh
  const maxPrice = ethers.parseEther("0.015"); // 15 INR/kWh

  const auctionProxy = await upgrades.deployProxy(
    EnergyAuctionUpgradeable,
    [
      tokenProxyAddress,      // shaktiToken
      ethers.ZeroAddress,     // registry (can be set later)
      deployer.address,       // admin
      minPrice,
      maxPrice,
    ],
    {
      initializer: "initialize",
      kind: "uups",
    }
  );
  await auctionProxy.waitForDeployment();

  const auctionProxyAddress = await auctionProxy.getAddress();
  const auctionImplAddress = await upgrades.erc1967.getImplementationAddress(auctionProxyAddress);
  const auctionAdminAddress = await upgrades.erc1967.getAdminAddress(auctionProxyAddress);

  console.log(`   ✅ Proxy: ${auctionProxyAddress}`);
  console.log(`   📋 Implementation: ${auctionImplAddress}`);
  console.log(`   🔐 Admin: ${auctionAdminAddress}`);

  deployment.contracts.EnergyAuctionUpgradeable = {
    proxy: auctionProxyAddress,
    implementation: auctionImplAddress,
    admin: auctionAdminAddress,
  };

  // ============ Deploy EnergyEscrowUpgradeable ============
  console.log("\n" + "─".repeat(60));
  console.log("📦 Deploying EnergyEscrowUpgradeable...");
  console.log("─".repeat(60));

  const EnergyEscrowUpgradeable = await ethers.getContractFactory("EnergyEscrowUpgradeable");

  const escrowProxy = await upgrades.deployProxy(
    EnergyEscrowUpgradeable,
    [
      tokenProxyAddress,      // shaktiToken
      auctionProxyAddress,    // auction
      deployer.address,       // admin
    ],
    {
      initializer: "initialize",
      kind: "uups",
    }
  );
  await escrowProxy.waitForDeployment();

  const escrowProxyAddress = await escrowProxy.getAddress();
  const escrowImplAddress = await upgrades.erc1967.getImplementationAddress(escrowProxyAddress);
  const escrowAdminAddress = await upgrades.erc1967.getAdminAddress(escrowProxyAddress);

  console.log(`   ✅ Proxy: ${escrowProxyAddress}`);
  console.log(`   📋 Implementation: ${escrowImplAddress}`);
  console.log(`   🔐 Admin: ${escrowAdminAddress}`);

  deployment.contracts.EnergyEscrowUpgradeable = {
    proxy: escrowProxyAddress,
    implementation: escrowImplAddress,
    admin: escrowAdminAddress,
  };

  // ============ Deploy ReputationSystemUpgradeable ============
  console.log("\n" + "─".repeat(60));
  console.log("📦 Deploying ReputationSystemUpgradeable...");
  console.log("─".repeat(60));

  const ReputationSystemUpgradeable = await ethers.getContractFactory("ReputationSystemUpgradeable");

  const reputationProxy = await upgrades.deployProxy(
    ReputationSystemUpgradeable,
    [deployer.address], // admin
    {
      initializer: "initialize",
      kind: "uups",
    }
  );
  await reputationProxy.waitForDeployment();

  const reputationProxyAddress = await reputationProxy.getAddress();
  const reputationImplAddress = await upgrades.erc1967.getImplementationAddress(reputationProxyAddress);
  const reputationAdminAddress = await upgrades.erc1967.getAdminAddress(reputationProxyAddress);

  console.log(`   ✅ Proxy: ${reputationProxyAddress}`);
  console.log(`   📋 Implementation: ${reputationImplAddress}`);
  console.log(`   🔐 Admin: ${reputationAdminAddress}`);

  deployment.contracts.ReputationSystemUpgradeable = {
    proxy: reputationProxyAddress,
    implementation: reputationImplAddress,
    admin: reputationAdminAddress,
  };

  // ============ Save Deployment Info ============
  const deploymentsDir = path.join(__dirname, "..", "deployments");
  if (!fs.existsSync(deploymentsDir)) {
    fs.mkdirSync(deploymentsDir, { recursive: true });
  }

  const deploymentFile = path.join(deploymentsDir, `${networkName}-upgradeable-deployment.json`);
  fs.writeFileSync(deploymentFile, JSON.stringify(deployment, null, 2));
  console.log(`\n💾 Deployment info saved to: ${deploymentFile}`);

  // ============ Summary ============
  console.log("\n" + "=".repeat(60));
  console.log("🎉 UPGRADEABLE CONTRACTS DEPLOYMENT COMPLETE");
  console.log("=".repeat(60));
  console.log("\n📋 Deployed Contracts:");
  console.log(`   ShaktiTokenV2:              ${tokenProxyAddress}`);
  console.log(`   EnergyAuctionUpgradeable:   ${auctionProxyAddress}`);
  console.log(`   EnergyEscrowUpgradeable:    ${escrowProxyAddress}`);
  console.log(`   ReputationSystemUpgradeable: ${reputationProxyAddress}`);

  console.log("\n📝 Next Steps:");
  console.log("   1. Transfer UPGRADER_ROLE to governance timelock");
  console.log("   2. Verify contracts on block explorer");
  console.log("   3. Test upgrade process on testnet first");
  console.log("   4. Set up monitoring for proxy events");
  console.log("=".repeat(60) + "\n");
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("\n❌ Deployment failed:");
    console.error(error);
    process.exit(1);
  });
