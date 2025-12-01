/**
 * SHAKTI-CHAIN Utility: Mint Test Tokens
 *
 * Mints SHAKTI tokens to specified addresses for testing.
 */

import { ethers, network } from "hardhat";
import { loadDeployment } from "./deployment-helpers";

async function main() {
  console.log("\n========================================");
  console.log("  Mint Test Tokens");
  console.log("  Network:", network.name);
  console.log("========================================\n");

  const [deployer] = await ethers.getSigners();
  console.log("Minter:", deployer.address);

  // Load token deployment
  const tokenDeployment = await loadDeployment("ShaktiToken");
  if (!tokenDeployment) {
    throw new Error("ShaktiToken not deployed. Run deployment first.");
  }

  const token = await ethers.getContractAt("ShaktiToken", tokenDeployment.address);
  const symbol = await token.symbol();

  console.log("Token:", tokenDeployment.address);
  console.log("");

  // Addresses to mint to (add your test addresses here)
  const recipients = [
    { address: deployer.address, amount: "100000" }, // 100K SHAKTI
    // Add more test addresses below:
    // { address: "0x...", amount: "50000" },
  ];

  // Check if deployer has MINTER_ROLE
  const MINTER_ROLE = await token.MINTER_ROLE();
  const hasMinterRole = await token.hasRole(MINTER_ROLE, deployer.address);

  if (!hasMinterRole) {
    console.log("❌ Deployer does not have MINTER_ROLE");
    console.log("   Grant role with: token.grantRole(MINTER_ROLE, address)");
    return;
  }

  console.log("Minting tokens...\n");

  for (const recipient of recipients) {
    const amount = ethers.parseEther(recipient.amount);
    const currentBalance = await token.balanceOf(recipient.address);

    if (currentBalance >= amount) {
      console.log(`⏭️  ${recipient.address.slice(0, 10)}... already has ${ethers.formatEther(currentBalance)} ${symbol}`);
      continue;
    }

    const toMint = amount - currentBalance;

    try {
      const tx = await token.mint(recipient.address, toMint);
      await tx.wait();
      console.log(`✅ Minted ${ethers.formatEther(toMint)} ${symbol} to ${recipient.address.slice(0, 10)}...`);
    } catch (error: any) {
      console.log(`❌ Failed to mint to ${recipient.address.slice(0, 10)}...: ${error.message?.slice(0, 50)}`);
    }
  }

  console.log("\n✅ Minting complete!");

  // Print final balances
  console.log("\nFinal Balances:");
  console.log("─".repeat(60));
  for (const recipient of recipients) {
    const balance = await token.balanceOf(recipient.address);
    console.log(`${recipient.address.slice(0, 10)}...  ${ethers.formatEther(balance).padStart(15)} ${symbol}`);
  }
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
