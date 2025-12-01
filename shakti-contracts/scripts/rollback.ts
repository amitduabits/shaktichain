import { ethers, upgrades, network } from "hardhat";
import * as fs from "fs";
import * as path from "path";
import * as readline from "readline";

interface RollbackInfo {
  network: string;
  chainId: number;
  contract: string;
  proxy: string;
  rolledBackFrom: string;
  rolledBackTo: string;
  executor: string;
  timestamp: string;
  reason: string;
}

/**
 * Rollback an upgradeable contract to a previous implementation
 *
 * ⚠️ WARNING: This is an emergency operation!
 *
 * This script allows rolling back to a previous implementation address.
 * Use only when:
 * - A critical bug is discovered in a new implementation
 * - The upgrade caused unexpected behavior
 * - Emergency situation requires immediate action
 *
 * Prerequisites:
 * - Caller must have UPGRADER_ROLE
 * - Previous implementation must still be deployed
 * - Storage layout must be compatible
 */

const CONTRACTS = [
  "ShaktiTokenV2",
  "EnergyAuctionUpgradeable",
  "EnergyEscrowUpgradeable",
  "ReputationSystemUpgradeable",
] as const;

type ContractName = typeof CONTRACTS[number];

function askQuestion(question: string): Promise<string> {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  return new Promise((resolve) => {
    rl.question(question, (answer) => {
      rl.close();
      resolve(answer);
    });
  });
}

async function main(): Promise<void> {
  console.log("\n⚠️  SHAKTI-CHAIN EMERGENCY ROLLBACK SCRIPT ⚠️");
  console.log("=".repeat(60));
  console.log("This script rolls back a contract to a previous implementation.");
  console.log("USE WITH EXTREME CAUTION!");
  console.log("=".repeat(60));

  const networkName = network.name;
  const chainId = (await ethers.provider.getNetwork()).chainId;
  console.log(`\n📡 Network: ${networkName} (Chain ID: ${chainId})`);

  const [executor] = await ethers.getSigners();
  console.log(`👤 Executor: ${executor.address}`);

  // Parse command line arguments
  const args = process.argv.slice(2);
  let contractArg: string | undefined;
  let targetImplArg: string | undefined;
  let reasonArg: string | undefined;
  let forceArg = false;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--contract" && args[i + 1]) {
      contractArg = args[i + 1];
      i++;
    } else if (args[i] === "--implementation" && args[i + 1]) {
      targetImplArg = args[i + 1];
      i++;
    } else if (args[i] === "--reason" && args[i + 1]) {
      reasonArg = args[i + 1];
      i++;
    } else if (args[i] === "--force") {
      forceArg = true;
    }
  }

  // Load deployment
  const deploymentsDir = path.join(__dirname, "..", "deployments");
  const deploymentFile = path.join(deploymentsDir, `${networkName}-upgradeable-deployment.json`);

  if (!fs.existsSync(deploymentFile)) {
    throw new Error(`No deployment found at ${deploymentFile}`);
  }

  const deployment = JSON.parse(fs.readFileSync(deploymentFile, "utf-8"));

  // Select contract
  console.log("\n📋 Available contracts:");
  CONTRACTS.forEach((c, i) => console.log(`   ${i + 1}. ${c}`));

  let selectedContract: ContractName;
  if (contractArg && CONTRACTS.includes(contractArg as ContractName)) {
    selectedContract = contractArg as ContractName;
  } else {
    const selection = await askQuestion("\nSelect contract number (1-4): ");
    const index = parseInt(selection) - 1;
    if (index < 0 || index >= CONTRACTS.length) {
      throw new Error("Invalid selection");
    }
    selectedContract = CONTRACTS[index];
  }

  console.log(`\n📦 Selected: ${selectedContract}`);

  const contractData = deployment.contracts[selectedContract];
  const proxyAddress = contractData.proxy;
  const currentImpl = await upgrades.erc1967.getImplementationAddress(proxyAddress);

  console.log(`   Proxy: ${proxyAddress}`);
  console.log(`   Current Implementation: ${currentImpl}`);

  // Load upgrade history
  const upgradesDir = path.join(deploymentsDir, "upgrades");
  const previousImpls: string[] = [];

  if (fs.existsSync(upgradesDir)) {
    const files = fs.readdirSync(upgradesDir).filter((f) => f.includes(selectedContract.toLowerCase()));
    for (const file of files) {
      const upgradeInfo = JSON.parse(fs.readFileSync(path.join(upgradesDir, file), "utf-8"));
      if (upgradeInfo.oldImplementation && !previousImpls.includes(upgradeInfo.oldImplementation)) {
        previousImpls.push(upgradeInfo.oldImplementation);
      }
    }
  }

  // Also include the original implementation from deployment
  if (contractData.implementation !== currentImpl && !previousImpls.includes(contractData.implementation)) {
    previousImpls.unshift(contractData.implementation);
  }

  console.log("\n📜 Known previous implementations:");
  if (previousImpls.length === 0) {
    console.log("   No previous implementations found");
  } else {
    previousImpls.forEach((impl, i) => console.log(`   ${i + 1}. ${impl}`));
  }

  // Get target implementation
  let targetImpl: string;
  if (targetImplArg && ethers.isAddress(targetImplArg)) {
    targetImpl = targetImplArg;
  } else if (previousImpls.length > 0) {
    const implSelection = await askQuestion(
      "\nEnter implementation number or paste address: "
    );
    if (ethers.isAddress(implSelection)) {
      targetImpl = implSelection;
    } else {
      const index = parseInt(implSelection) - 1;
      if (index < 0 || index >= previousImpls.length) {
        throw new Error("Invalid selection");
      }
      targetImpl = previousImpls[index];
    }
  } else {
    const implAddress = await askQuestion("\nEnter target implementation address: ");
    if (!ethers.isAddress(implAddress)) {
      throw new Error("Invalid address");
    }
    targetImpl = implAddress;
  }

  console.log(`\n🎯 Target implementation: ${targetImpl}`);

  if (targetImpl === currentImpl) {
    console.log("\n⚠️  Target is the same as current implementation. Nothing to do.");
    return;
  }

  // Verify target implementation exists
  const targetCode = await ethers.provider.getCode(targetImpl);
  if (targetCode === "0x") {
    throw new Error(`Target implementation ${targetImpl} has no code deployed!`);
  }
  console.log("   ✅ Target implementation has code");

  // Verify executor has UPGRADER_ROLE
  const contract = await ethers.getContractAt(selectedContract, proxyAddress);
  const UPGRADER_ROLE = await contract.UPGRADER_ROLE();
  const hasRole = await contract.hasRole(UPGRADER_ROLE, executor.address);

  if (!hasRole) {
    throw new Error(`Executor ${executor.address} does not have UPGRADER_ROLE!`);
  }
  console.log("   ✅ Executor has UPGRADER_ROLE");

  // Get reason
  let reason: string;
  if (reasonArg) {
    reason = reasonArg;
  } else {
    reason = await askQuestion("\nReason for rollback: ");
  }

  // Final confirmation
  console.log("\n" + "⚠️ ".repeat(20));
  console.log("ROLLBACK CONFIRMATION");
  console.log("⚠️ ".repeat(20));
  console.log(`\n   Contract: ${selectedContract}`);
  console.log(`   Proxy: ${proxyAddress}`);
  console.log(`   From: ${currentImpl}`);
  console.log(`   To: ${targetImpl}`);
  console.log(`   Reason: ${reason}`);
  console.log(`   Executor: ${executor.address}`);

  if (!forceArg) {
    const confirm = await askQuestion("\n⚠️  Type 'ROLLBACK' to confirm: ");
    if (confirm !== "ROLLBACK") {
      console.log("\n❌ Rollback cancelled.");
      return;
    }
  }

  // Perform rollback using upgradeProxy with force
  console.log("\n🔄 Performing rollback...");

  try {
    // Create a minimal contract factory pointing to the target implementation
    // This is a workaround - in production you'd keep the V1 contract available
    const ContractFactory = await ethers.getContractFactory(selectedContract);

    // Force upgrade to previous implementation
    // Note: This bypasses some safety checks - use with caution!
    const iface = new ethers.Interface([
      "function upgradeToAndCall(address newImplementation, bytes memory data) external",
    ]);
    const upgradeData = iface.encodeFunctionData("upgradeToAndCall", [targetImpl, "0x"]);

    const tx = await executor.sendTransaction({
      to: proxyAddress,
      data: upgradeData,
    });

    console.log(`   Transaction: ${tx.hash}`);
    await tx.wait();

    // Verify rollback
    const newImpl = await upgrades.erc1967.getImplementationAddress(proxyAddress);
    if (newImpl.toLowerCase() !== targetImpl.toLowerCase()) {
      throw new Error(`Rollback failed! Expected ${targetImpl}, got ${newImpl}`);
    }

    console.log("   ✅ Rollback successful!");

    // Save rollback info
    const rollbackInfo: RollbackInfo = {
      network: networkName,
      chainId: Number(chainId),
      contract: selectedContract,
      proxy: proxyAddress,
      rolledBackFrom: currentImpl,
      rolledBackTo: targetImpl,
      executor: executor.address,
      timestamp: new Date().toISOString(),
      reason,
    };

    const rollbacksDir = path.join(deploymentsDir, "rollbacks");
    if (!fs.existsSync(rollbacksDir)) {
      fs.mkdirSync(rollbacksDir, { recursive: true });
    }

    const rollbackFile = path.join(
      rollbacksDir,
      `${networkName}-${selectedContract.toLowerCase()}-rollback-${Date.now()}.json`
    );
    fs.writeFileSync(rollbackFile, JSON.stringify(rollbackInfo, null, 2));

    // Update main deployment
    deployment.contracts[selectedContract].implementation = targetImpl;
    fs.writeFileSync(deploymentFile, JSON.stringify(deployment, null, 2));

    console.log(`\n💾 Rollback info saved to: ${rollbackFile}`);

    // Post-rollback verification
    console.log("\n🔍 Post-rollback verification...");
    const version = await contract.version();
    console.log(`   Contract version: ${version}`);
    console.log("   ✅ Contract is responding");

  } catch (error) {
    console.error("\n❌ Rollback failed!");
    console.error(error);
    throw error;
  }

  console.log("\n" + "=".repeat(60));
  console.log("🔄 ROLLBACK COMPLETE");
  console.log("=".repeat(60));
  console.log("\n⚠️  IMPORTANT NEXT STEPS:");
  console.log("   1. Verify all contract functionality");
  console.log("   2. Monitor for any issues");
  console.log("   3. Investigate the cause of the rollback");
  console.log("   4. Prepare a proper fix before next upgrade");
  console.log("=".repeat(60) + "\n");
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
