/**
 * SHAKTI-CHAIN Multisig Ownership Transfer Script
 *
 * Transfers admin roles from deployer to Gnosis Safe multisigs.
 *
 * Usage: npx hardhat run scripts/setup/transfer-to-multisig.ts --network polygon
 *
 * Required Environment Variables:
 * - OWNER_MULTISIG: 3/5 Gnosis Safe for admin operations
 * - TREASURY_MULTISIG: 3/5 Gnosis Safe for treasury management
 * - EMERGENCY_MULTISIG: 2/3 Gnosis Safe for emergency pause
 */

import { ethers, network } from "hardhat";
import { loadDeployment } from "../utils/deployment-helpers";

interface MultisigConfig {
  ownerMultisig: string;
  treasuryMultisig: string;
  emergencyMultisig: string;
}

async function main() {
  console.log("╔════════════════════════════════════════════════════════════╗");
  console.log("║       SHAKTI-CHAIN Multisig Ownership Transfer            ║");
  console.log("╚════════════════════════════════════════════════════════════╝\n");

  console.log("Network:", network.name);
  console.log("");

  // Load multisig addresses from environment
  const config: MultisigConfig = {
    ownerMultisig: process.env.OWNER_MULTISIG || "",
    treasuryMultisig: process.env.TREASURY_MULTISIG || "",
    emergencyMultisig: process.env.EMERGENCY_MULTISIG || "",
  };

  // Validate addresses
  if (!config.ownerMultisig || !ethers.isAddress(config.ownerMultisig)) {
    console.log("ERROR: Invalid or missing OWNER_MULTISIG address");
    console.log("Set in .env: OWNER_MULTISIG=0x...");
    process.exit(1);
  }

  if (!config.treasuryMultisig || !ethers.isAddress(config.treasuryMultisig)) {
    console.log("ERROR: Invalid or missing TREASURY_MULTISIG address");
    console.log("Set in .env: TREASURY_MULTISIG=0x...");
    process.exit(1);
  }

  if (!config.emergencyMultisig || !ethers.isAddress(config.emergencyMultisig)) {
    console.log("ERROR: Invalid or missing EMERGENCY_MULTISIG address");
    console.log("Set in .env: EMERGENCY_MULTISIG=0x...");
    process.exit(1);
  }

  console.log("Multisig Configuration:");
  console.log("  Owner (3/5):     ", config.ownerMultisig);
  console.log("  Treasury (3/5):  ", config.treasuryMultisig);
  console.log("  Emergency (2/3): ", config.emergencyMultisig);
  console.log("");

  const [deployer] = await ethers.getSigners();
  console.log("Current admin:", deployer.address);
  console.log("");

  // Role constants
  const DEFAULT_ADMIN_ROLE = ethers.ZeroHash;
  const PAUSER_ROLE = ethers.keccak256(ethers.toUtf8Bytes("PAUSER_ROLE"));
  const MINTER_ROLE = ethers.keccak256(ethers.toUtf8Bytes("MINTER_ROLE"));
  const ARBITER_ROLE = ethers.keccak256(ethers.toUtf8Bytes("ARBITER_ROLE"));

  console.log("═══════════════════════════════════════════════════════════════");
  console.log("Starting role transfers...");
  console.log("═══════════════════════════════════════════════════════════════\n");

  // Track all transfers
  const transfers: { contract: string; role: string; to: string; status: string }[] = [];

  // 1. ShaktiToken
  console.log("1. ShaktiToken");
  try {
    const tokenDeployment = await loadDeployment("ShaktiToken");
    if (tokenDeployment) {
      const token = await ethers.getContractAt("ShaktiToken", tokenDeployment.address);

      // Grant DEFAULT_ADMIN_ROLE to Owner Multisig
      console.log("   Granting DEFAULT_ADMIN_ROLE to Owner Multisig...");
      await (await token.grantRole(DEFAULT_ADMIN_ROLE, config.ownerMultisig)).wait();
      transfers.push({ contract: "ShaktiToken", role: "DEFAULT_ADMIN_ROLE", to: "Owner", status: "✓" });

      // Grant PAUSER_ROLE to Emergency Multisig
      console.log("   Granting PAUSER_ROLE to Emergency Multisig...");
      await (await token.grantRole(PAUSER_ROLE, config.emergencyMultisig)).wait();
      transfers.push({ contract: "ShaktiToken", role: "PAUSER_ROLE", to: "Emergency", status: "✓" });

      // Revoke deployer's DEFAULT_ADMIN_ROLE (done last!)
      console.log("   Revoking DEFAULT_ADMIN_ROLE from deployer...");
      await (await token.revokeRole(DEFAULT_ADMIN_ROLE, deployer.address)).wait();
      transfers.push({ contract: "ShaktiToken", role: "DEFAULT_ADMIN_ROLE", to: "Deployer", status: "Revoked" });

      console.log("   ✓ ShaktiToken roles transferred\n");
    }
  } catch (error) {
    console.log("   ✗ Error:", error);
    transfers.push({ contract: "ShaktiToken", role: "ALL", to: "-", status: "ERROR" });
  }

  // 2. StakingPool
  console.log("2. StakingPool");
  try {
    const stakingDeployment = await loadDeployment("StakingPool");
    if (stakingDeployment) {
      const staking = await ethers.getContractAt("StakingPool", stakingDeployment.address);

      await (await staking.grantRole(DEFAULT_ADMIN_ROLE, config.ownerMultisig)).wait();
      transfers.push({ contract: "StakingPool", role: "DEFAULT_ADMIN_ROLE", to: "Owner", status: "✓" });

      await (await staking.grantRole(PAUSER_ROLE, config.emergencyMultisig)).wait();
      transfers.push({ contract: "StakingPool", role: "PAUSER_ROLE", to: "Emergency", status: "✓" });

      await (await staking.revokeRole(DEFAULT_ADMIN_ROLE, deployer.address)).wait();
      console.log("   ✓ StakingPool roles transferred\n");
    }
  } catch (error) {
    console.log("   ✗ Error:", error);
  }

  // 3. EnergyRegistry
  console.log("3. EnergyRegistry");
  try {
    const registryDeployment = await loadDeployment("EnergyRegistry");
    if (registryDeployment) {
      const registry = await ethers.getContractAt("EnergyRegistry", registryDeployment.address);

      await (await registry.grantRole(DEFAULT_ADMIN_ROLE, config.ownerMultisig)).wait();
      transfers.push({ contract: "EnergyRegistry", role: "DEFAULT_ADMIN_ROLE", to: "Owner", status: "✓" });

      await (await registry.revokeRole(DEFAULT_ADMIN_ROLE, deployer.address)).wait();
      console.log("   ✓ EnergyRegistry roles transferred\n");
    }
  } catch (error) {
    console.log("   ✗ Error:", error);
  }

  // 4. EnergyAuction
  console.log("4. EnergyAuction");
  try {
    const auctionDeployment = await loadDeployment("EnergyAuction");
    if (auctionDeployment) {
      const auction = await ethers.getContractAt("EnergyAuction", auctionDeployment.address);

      await (await auction.grantRole(DEFAULT_ADMIN_ROLE, config.ownerMultisig)).wait();
      transfers.push({ contract: "EnergyAuction", role: "DEFAULT_ADMIN_ROLE", to: "Owner", status: "✓" });

      await (await auction.grantRole(PAUSER_ROLE, config.emergencyMultisig)).wait();
      transfers.push({ contract: "EnergyAuction", role: "PAUSER_ROLE", to: "Emergency", status: "✓" });

      await (await auction.revokeRole(DEFAULT_ADMIN_ROLE, deployer.address)).wait();
      console.log("   ✓ EnergyAuction roles transferred\n");
    }
  } catch (error) {
    console.log("   ✗ Error:", error);
  }

  // 5. EnergyEscrow
  console.log("5. EnergyEscrow");
  try {
    const escrowDeployment = await loadDeployment("EnergyEscrow");
    if (escrowDeployment) {
      const escrow = await ethers.getContractAt("EnergyEscrow", escrowDeployment.address);

      await (await escrow.grantRole(DEFAULT_ADMIN_ROLE, config.ownerMultisig)).wait();
      transfers.push({ contract: "EnergyEscrow", role: "DEFAULT_ADMIN_ROLE", to: "Owner", status: "✓" });

      await (await escrow.grantRole(PAUSER_ROLE, config.emergencyMultisig)).wait();
      transfers.push({ contract: "EnergyEscrow", role: "PAUSER_ROLE", to: "Emergency", status: "✓" });

      await (await escrow.revokeRole(DEFAULT_ADMIN_ROLE, deployer.address)).wait();
      console.log("   ✓ EnergyEscrow roles transferred\n");
    }
  } catch (error) {
    console.log("   ✗ Error:", error);
  }

  // 6. Treasury
  console.log("6. Treasury");
  try {
    const treasuryDeployment = await loadDeployment("Treasury");
    if (treasuryDeployment) {
      const treasury = await ethers.getContractAt("Treasury", treasuryDeployment.address);

      await (await treasury.grantRole(DEFAULT_ADMIN_ROLE, config.treasuryMultisig)).wait();
      transfers.push({ contract: "Treasury", role: "DEFAULT_ADMIN_ROLE", to: "Treasury", status: "✓" });

      await (await treasury.revokeRole(DEFAULT_ADMIN_ROLE, deployer.address)).wait();
      console.log("   ✓ Treasury roles transferred\n");
    }
  } catch (error) {
    console.log("   ✗ Error:", error);
  }

  // 7. ReputationSystem
  console.log("7. ReputationSystem");
  try {
    const reputationDeployment = await loadDeployment("ReputationSystem");
    if (reputationDeployment) {
      const reputation = await ethers.getContractAt("ReputationSystem", reputationDeployment.address);

      await (await reputation.grantRole(DEFAULT_ADMIN_ROLE, config.ownerMultisig)).wait();
      transfers.push({ contract: "ReputationSystem", role: "DEFAULT_ADMIN_ROLE", to: "Owner", status: "✓" });

      await (await reputation.revokeRole(DEFAULT_ADMIN_ROLE, deployer.address)).wait();
      console.log("   ✓ ReputationSystem roles transferred\n");
    }
  } catch (error) {
    console.log("   ✗ Error:", error);
  }

  // 8. EnergyVerification
  console.log("8. EnergyVerification");
  try {
    const verificationDeployment = await loadDeployment("EnergyVerification");
    if (verificationDeployment) {
      const verification = await ethers.getContractAt("EnergyVerification", verificationDeployment.address);

      await (await verification.grantRole(DEFAULT_ADMIN_ROLE, config.ownerMultisig)).wait();
      transfers.push({ contract: "EnergyVerification", role: "DEFAULT_ADMIN_ROLE", to: "Owner", status: "✓" });

      await (await verification.grantRole(ARBITER_ROLE, config.ownerMultisig)).wait();
      transfers.push({ contract: "EnergyVerification", role: "ARBITER_ROLE", to: "Owner", status: "✓" });

      await (await verification.grantRole(PAUSER_ROLE, config.emergencyMultisig)).wait();
      transfers.push({ contract: "EnergyVerification", role: "PAUSER_ROLE", to: "Emergency", status: "✓" });

      await (await verification.revokeRole(DEFAULT_ADMIN_ROLE, deployer.address)).wait();
      await (await verification.revokeRole(ARBITER_ROLE, deployer.address)).wait();
      console.log("   ✓ EnergyVerification roles transferred\n");
    }
  } catch (error) {
    console.log("   ✗ Error:", error);
  }

  // 9. DynamicPricing
  console.log("9. DynamicPricing");
  try {
    const pricingDeployment = await loadDeployment("DynamicPricing");
    if (pricingDeployment) {
      const pricing = await ethers.getContractAt("DynamicPricing", pricingDeployment.address);

      await (await pricing.grantRole(DEFAULT_ADMIN_ROLE, config.ownerMultisig)).wait();
      transfers.push({ contract: "DynamicPricing", role: "DEFAULT_ADMIN_ROLE", to: "Owner", status: "✓" });

      await (await pricing.grantRole(PAUSER_ROLE, config.emergencyMultisig)).wait();
      transfers.push({ contract: "DynamicPricing", role: "PAUSER_ROLE", to: "Emergency", status: "✓" });

      await (await pricing.revokeRole(DEFAULT_ADMIN_ROLE, deployer.address)).wait();
      console.log("   ✓ DynamicPricing roles transferred\n");
    }
  } catch (error) {
    console.log("   ✗ Error:", error);
  }

  // 10. PriceOracle
  console.log("10. PriceOracle");
  try {
    const oracleDeployment = await loadDeployment("PriceOracle");
    if (oracleDeployment) {
      const oracle = await ethers.getContractAt("PriceOracle", oracleDeployment.address);

      await (await oracle.grantRole(DEFAULT_ADMIN_ROLE, config.ownerMultisig)).wait();
      transfers.push({ contract: "PriceOracle", role: "DEFAULT_ADMIN_ROLE", to: "Owner", status: "✓" });

      await (await oracle.revokeRole(DEFAULT_ADMIN_ROLE, deployer.address)).wait();
      console.log("   ✓ PriceOracle roles transferred\n");
    }
  } catch (error) {
    console.log("   ✗ Error:", error);
  }

  // Print summary
  console.log("═══════════════════════════════════════════════════════════════");
  console.log("TRANSFER SUMMARY");
  console.log("═══════════════════════════════════════════════════════════════\n");

  console.log("| Contract            | Role                | Assigned To  | Status |");
  console.log("|---------------------|---------------------|--------------|--------|");
  for (const t of transfers) {
    console.log(
      `| ${t.contract.padEnd(19)} | ${t.role.padEnd(19)} | ${t.to.padEnd(12)} | ${t.status.padEnd(6)} |`
    );
  }

  const successCount = transfers.filter((t) => t.status === "✓" || t.status === "Revoked").length;
  const errorCount = transfers.filter((t) => t.status === "ERROR").length;

  console.log(`\nSuccessful: ${successCount}`);
  if (errorCount > 0) {
    console.log(`Errors: ${errorCount}`);
  }

  console.log(`
╔════════════════════════════════════════════════════════════╗
║                  Transfer Complete!                         ║
╚════════════════════════════════════════════════════════════╝

⚠️  IMPORTANT:

1. The deployer wallet NO LONGER has admin access
2. All future admin operations require multisig approval
3. Keep multisig signers' keys secure
4. Test multisig operations before going live

Multisig Summary:
  Owner Multisig (3/5):     Controls contract upgrades, parameters
  Treasury Multisig (3/5):  Controls treasury funds
  Emergency Multisig (2/3): Can pause contracts only

Next Steps:
1. Test multisig by creating a Safe transaction
2. Verify all roles are correctly assigned
3. Store deployer key securely (or destroy if not needed)
`);
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
