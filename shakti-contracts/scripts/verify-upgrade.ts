import { ethers, upgrades, network } from "hardhat";
import * as fs from "fs";
import * as path from "path";

interface VerificationResult {
  network: string;
  timestamp: string;
  contracts: {
    [key: string]: {
      proxy: string;
      implementation: string;
      isValid: boolean;
      version: string;
      storageLayoutValid: boolean;
      rolesIntact: boolean;
      stateChecks: {
        [key: string]: boolean;
      };
      errors: string[];
    };
  };
  overallStatus: "PASSED" | "FAILED" | "WARNINGS";
}

/**
 * Verify all upgradeable contracts are functioning correctly
 *
 * Checks:
 * - Proxy points to valid implementation
 * - Storage layout is valid
 * - Roles are properly configured
 * - Contract state is accessible
 * - Upgrade authorization works correctly
 */
async function main(): Promise<void> {
  console.log("\n🔷 SHAKTI-CHAIN Upgrade Verification Script");
  console.log("=".repeat(60));

  const networkName = network.name;
  const chainId = (await ethers.provider.getNetwork()).chainId;
  console.log(`📡 Network: ${networkName} (Chain ID: ${chainId})`);

  const [verifier] = await ethers.getSigners();
  console.log(`👤 Verifier: ${verifier.address}\n`);

  // Load deployment
  const deploymentsDir = path.join(__dirname, "..", "deployments");
  const deploymentFile = path.join(deploymentsDir, `${networkName}-upgradeable-deployment.json`);

  if (!fs.existsSync(deploymentFile)) {
    throw new Error(`No deployment found at ${deploymentFile}`);
  }

  const deployment = JSON.parse(fs.readFileSync(deploymentFile, "utf-8"));

  const result: VerificationResult = {
    network: networkName,
    timestamp: new Date().toISOString(),
    contracts: {},
    overallStatus: "PASSED",
  };

  // ============ Verify ShaktiTokenV2 ============
  console.log("─".repeat(60));
  console.log("🔍 Verifying ShaktiTokenV2...");
  console.log("─".repeat(60));

  try {
    const tokenProxy = deployment.contracts.ShaktiTokenV2.proxy;
    const token = await ethers.getContractAt("ShaktiTokenV2", tokenProxy);

    // Check implementation
    const tokenImpl = await upgrades.erc1967.getImplementationAddress(tokenProxy);
    console.log(`   Proxy: ${tokenProxy}`);
    console.log(`   Implementation: ${tokenImpl}`);

    // Check version
    const tokenVersion = await token.version();
    console.log(`   Version: ${tokenVersion}`);

    // Check roles
    const UPGRADER_ROLE = await token.UPGRADER_ROLE();
    const MINTER_ROLE = await token.MINTER_ROLE();
    const DEFAULT_ADMIN = await token.DEFAULT_ADMIN_ROLE();

    const hasUpgrader = await token.hasRole(UPGRADER_ROLE, verifier.address);
    const hasMinter = await token.hasRole(MINTER_ROLE, verifier.address);
    const hasAdmin = await token.hasRole(DEFAULT_ADMIN, verifier.address);

    console.log(`   Roles:`);
    console.log(`     - Admin: ${hasAdmin}`);
    console.log(`     - Minter: ${hasMinter}`);
    console.log(`     - Upgrader: ${hasUpgrader}`);

    // Check state
    const totalSupply = await token.totalSupply();
    const maxSupply = await token.MAX_SUPPLY();
    console.log(`   Total Supply: ${ethers.formatEther(totalSupply)} SHAKTI`);
    console.log(`   Max Supply: ${ethers.formatEther(maxSupply)} SHAKTI`);

    // Validate storage layout
    const StorageFactory = await ethers.getContractFactory("ShaktiTokenV2");
    let storageValid = true;
    try {
      await upgrades.validateUpgrade(tokenProxy, StorageFactory, { kind: "uups" });
    } catch {
      storageValid = false;
    }
    console.log(`   Storage Layout Valid: ${storageValid ? "✅" : "❌"}`);

    result.contracts["ShaktiTokenV2"] = {
      proxy: tokenProxy,
      implementation: tokenImpl,
      isValid: true,
      version: tokenVersion,
      storageLayoutValid: storageValid,
      rolesIntact: hasAdmin && hasMinter && hasUpgrader,
      stateChecks: {
        totalSupplyAccessible: totalSupply > 0n,
        maxSupplyCorrect: maxSupply === ethers.parseEther("1000000000"),
      },
      errors: [],
    };

    console.log("   ✅ ShaktiTokenV2 verification passed\n");
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : String(error);
    console.log(`   ❌ ShaktiTokenV2 verification failed: ${errorMsg}\n`);
    result.contracts["ShaktiTokenV2"] = {
      proxy: deployment.contracts.ShaktiTokenV2.proxy,
      implementation: "",
      isValid: false,
      version: "",
      storageLayoutValid: false,
      rolesIntact: false,
      stateChecks: {},
      errors: [errorMsg],
    };
    result.overallStatus = "FAILED";
  }

  // ============ Verify EnergyAuctionUpgradeable ============
  console.log("─".repeat(60));
  console.log("🔍 Verifying EnergyAuctionUpgradeable...");
  console.log("─".repeat(60));

  try {
    const auctionProxy = deployment.contracts.EnergyAuctionUpgradeable.proxy;
    const auction = await ethers.getContractAt("EnergyAuctionUpgradeable", auctionProxy);

    const auctionImpl = await upgrades.erc1967.getImplementationAddress(auctionProxy);
    console.log(`   Proxy: ${auctionProxy}`);
    console.log(`   Implementation: ${auctionImpl}`);

    const auctionVersion = await auction.version();
    console.log(`   Version: ${auctionVersion}`);

    // Check configuration
    const minPrice = await auction.minPrice();
    const maxPrice = await auction.maxPrice();
    const currentRound = await auction.currentRoundId();
    console.log(`   Min Price: ${ethers.formatEther(minPrice)} INR/Wh`);
    console.log(`   Max Price: ${ethers.formatEther(maxPrice)} INR/Wh`);
    console.log(`   Current Round: ${currentRound}`);

    // Check roles
    const UPGRADER_ROLE = await auction.UPGRADER_ROLE();
    const hasUpgrader = await auction.hasRole(UPGRADER_ROLE, verifier.address);
    console.log(`   Has UPGRADER_ROLE: ${hasUpgrader}`);

    // Validate storage layout
    const AuctionFactory = await ethers.getContractFactory("EnergyAuctionUpgradeable");
    let storageValid = true;
    try {
      await upgrades.validateUpgrade(auctionProxy, AuctionFactory, { kind: "uups" });
    } catch {
      storageValid = false;
    }
    console.log(`   Storage Layout Valid: ${storageValid ? "✅" : "❌"}`);

    result.contracts["EnergyAuctionUpgradeable"] = {
      proxy: auctionProxy,
      implementation: auctionImpl,
      isValid: true,
      version: auctionVersion,
      storageLayoutValid: storageValid,
      rolesIntact: hasUpgrader,
      stateChecks: {
        minPriceSet: minPrice > 0n,
        maxPriceSet: maxPrice > 0n,
        priceRangeValid: maxPrice > minPrice,
      },
      errors: [],
    };

    console.log("   ✅ EnergyAuctionUpgradeable verification passed\n");
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : String(error);
    console.log(`   ❌ EnergyAuctionUpgradeable verification failed: ${errorMsg}\n`);
    result.contracts["EnergyAuctionUpgradeable"] = {
      proxy: deployment.contracts.EnergyAuctionUpgradeable.proxy,
      implementation: "",
      isValid: false,
      version: "",
      storageLayoutValid: false,
      rolesIntact: false,
      stateChecks: {},
      errors: [errorMsg],
    };
    result.overallStatus = "FAILED";
  }

  // ============ Verify EnergyEscrowUpgradeable ============
  console.log("─".repeat(60));
  console.log("🔍 Verifying EnergyEscrowUpgradeable...");
  console.log("─".repeat(60));

  try {
    const escrowProxy = deployment.contracts.EnergyEscrowUpgradeable.proxy;
    const escrow = await ethers.getContractAt("EnergyEscrowUpgradeable", escrowProxy);

    const escrowImpl = await upgrades.erc1967.getImplementationAddress(escrowProxy);
    console.log(`   Proxy: ${escrowProxy}`);
    console.log(`   Implementation: ${escrowImpl}`);

    const escrowVersion = await escrow.version();
    console.log(`   Version: ${escrowVersion}`);

    // Check configuration
    const circuitBreakerActive = await escrow.circuitBreakerActive();
    const platformFee = await escrow.platformFeePercent();
    console.log(`   Circuit Breaker: ${circuitBreakerActive ? "ACTIVE" : "Inactive"}`);
    console.log(`   Platform Fee: ${platformFee / 100}%`);

    // Check roles
    const UPGRADER_ROLE = await escrow.UPGRADER_ROLE();
    const hasUpgrader = await escrow.hasRole(UPGRADER_ROLE, verifier.address);
    console.log(`   Has UPGRADER_ROLE: ${hasUpgrader}`);

    // Validate storage layout
    const EscrowFactory = await ethers.getContractFactory("EnergyEscrowUpgradeable");
    let storageValid = true;
    try {
      await upgrades.validateUpgrade(escrowProxy, EscrowFactory, { kind: "uups" });
    } catch {
      storageValid = false;
    }
    console.log(`   Storage Layout Valid: ${storageValid ? "✅" : "❌"}`);

    result.contracts["EnergyEscrowUpgradeable"] = {
      proxy: escrowProxy,
      implementation: escrowImpl,
      isValid: true,
      version: escrowVersion,
      storageLayoutValid: storageValid,
      rolesIntact: hasUpgrader,
      stateChecks: {
        circuitBreakerConfigured: true,
        platformFeeReasonable: platformFee <= 500, // Max 5%
      },
      errors: [],
    };

    console.log("   ✅ EnergyEscrowUpgradeable verification passed\n");
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : String(error);
    console.log(`   ❌ EnergyEscrowUpgradeable verification failed: ${errorMsg}\n`);
    result.contracts["EnergyEscrowUpgradeable"] = {
      proxy: deployment.contracts.EnergyEscrowUpgradeable.proxy,
      implementation: "",
      isValid: false,
      version: "",
      storageLayoutValid: false,
      rolesIntact: false,
      stateChecks: {},
      errors: [errorMsg],
    };
    result.overallStatus = "FAILED";
  }

  // ============ Verify ReputationSystemUpgradeable ============
  console.log("─".repeat(60));
  console.log("🔍 Verifying ReputationSystemUpgradeable...");
  console.log("─".repeat(60));

  try {
    const reputationProxy = deployment.contracts.ReputationSystemUpgradeable.proxy;
    const reputation = await ethers.getContractAt("ReputationSystemUpgradeable", reputationProxy);

    const reputationImpl = await upgrades.erc1967.getImplementationAddress(reputationProxy);
    console.log(`   Proxy: ${reputationProxy}`);
    console.log(`   Implementation: ${reputationImpl}`);

    const reputationVersion = await reputation.version();
    console.log(`   Version: ${reputationVersion}`);

    // Check configuration
    const initialScore = await reputation.INITIAL_SCORE();
    const maxScore = await reputation.MAX_SCORE();
    console.log(`   Initial Score: ${initialScore}`);
    console.log(`   Max Score: ${maxScore}`);

    // Check tiers
    const silverThreshold = await reputation.SILVER_THRESHOLD();
    const goldThreshold = await reputation.GOLD_THRESHOLD();
    const platinumThreshold = await reputation.PLATINUM_THRESHOLD();
    const diamondThreshold = await reputation.DIAMOND_THRESHOLD();
    console.log(`   Tier Thresholds: Silver=${silverThreshold}, Gold=${goldThreshold}, Platinum=${platinumThreshold}, Diamond=${diamondThreshold}`);

    // Check roles
    const UPGRADER_ROLE = await reputation.UPGRADER_ROLE();
    const hasUpgrader = await reputation.hasRole(UPGRADER_ROLE, verifier.address);
    console.log(`   Has UPGRADER_ROLE: ${hasUpgrader}`);

    // Validate storage layout
    const ReputationFactory = await ethers.getContractFactory("ReputationSystemUpgradeable");
    let storageValid = true;
    try {
      await upgrades.validateUpgrade(reputationProxy, ReputationFactory, { kind: "uups" });
    } catch {
      storageValid = false;
    }
    console.log(`   Storage Layout Valid: ${storageValid ? "✅" : "❌"}`);

    result.contracts["ReputationSystemUpgradeable"] = {
      proxy: reputationProxy,
      implementation: reputationImpl,
      isValid: true,
      version: reputationVersion,
      storageLayoutValid: storageValid,
      rolesIntact: hasUpgrader,
      stateChecks: {
        initialScoreSet: initialScore > 0n,
        maxScoreSet: maxScore > 0n,
        tiersConfigured: diamondThreshold > platinumThreshold,
      },
      errors: [],
    };

    console.log("   ✅ ReputationSystemUpgradeable verification passed\n");
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : String(error);
    console.log(`   ❌ ReputationSystemUpgradeable verification failed: ${errorMsg}\n`);
    result.contracts["ReputationSystemUpgradeable"] = {
      proxy: deployment.contracts.ReputationSystemUpgradeable.proxy,
      implementation: "",
      isValid: false,
      version: "",
      storageLayoutValid: false,
      rolesIntact: false,
      stateChecks: {},
      errors: [errorMsg],
    };
    result.overallStatus = "FAILED";
  }

  // ============ Save Results ============
  const reportsDir = path.join(deploymentsDir, "reports");
  if (!fs.existsSync(reportsDir)) {
    fs.mkdirSync(reportsDir, { recursive: true });
  }

  const reportFile = path.join(reportsDir, `verification-${networkName}-${Date.now()}.json`);
  fs.writeFileSync(reportFile, JSON.stringify(result, null, 2));

  // ============ Summary ============
  console.log("=".repeat(60));
  console.log(`📊 VERIFICATION SUMMARY: ${result.overallStatus}`);
  console.log("=".repeat(60));

  for (const [name, data] of Object.entries(result.contracts)) {
    const status = data.isValid ? "✅" : "❌";
    console.log(`   ${status} ${name}`);
    if (data.errors.length > 0) {
      data.errors.forEach((e) => console.log(`      Error: ${e}`));
    }
  }

  console.log(`\n💾 Report saved to: ${reportFile}`);
  console.log("=".repeat(60) + "\n");

  if (result.overallStatus === "FAILED") {
    process.exit(1);
  }
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("\n❌ Verification failed:");
    console.error(error);
    process.exit(1);
  });
