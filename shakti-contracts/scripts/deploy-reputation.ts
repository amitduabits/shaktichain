import { ethers } from "hardhat";

async function main() {
    console.log("🚀 Deploying SHAKTI-CHAIN ReputationSystem...\n");

    const [deployer] = await ethers.getSigners();
    console.log("📍 Deployer:", deployer.address);
    console.log("💰 Balance:", ethers.formatEther(await ethers.provider.getBalance(deployer.address)), "ETH\n");

    // ============ Configuration ============
    const config = {
        // Staking contract address (for stake verification)
        stakingAddress: process.env.STAKING_POOL_ADDRESS || "",

        // KYC Registry address (for verification status)
        kycRegistryAddress: process.env.KYC_REGISTRY_ADDRESS || "",

        // EnergyEscrow address (to grant reporter role)
        escrowAddress: process.env.ENERGY_ESCROW_ADDRESS || "",

        // EnergyAuction address (to grant reporter role)
        auctionAddress: process.env.ENERGY_AUCTION_ADDRESS || "",

        // EnergyVerification address (to grant reporter role)
        verificationAddress: process.env.ENERGY_VERIFICATION_ADDRESS || "",

        admin: deployer.address,
    };

    console.log("📋 Configuration:");
    console.log("   Admin:", config.admin);
    console.log("   Staking Address:", config.stakingAddress || "Not provided");
    console.log("   KYC Registry:", config.kycRegistryAddress || "Not provided");
    console.log("   Escrow Address:", config.escrowAddress || "Not provided");
    console.log("   Auction Address:", config.auctionAddress || "Not provided");
    console.log("   Verification Address:", config.verificationAddress || "Not provided");
    console.log();

    // ============ Deploy ReputationSystem ============
    console.log("1️⃣  Deploying ReputationSystem...");
    const ReputationSystem = await ethers.getContractFactory("ReputationSystem");
    const reputation = await ReputationSystem.deploy(config.admin);
    await reputation.waitForDeployment();
    const reputationAddress = await reputation.getAddress();
    console.log("   ✅ ReputationSystem deployed at:", reputationAddress);

    // ============ Setup Integrations ============
    console.log("\n2️⃣  Setting up integrations...");

    // Set staking contract if provided
    if (config.stakingAddress) {
        console.log("   • Setting staking contract...");
        const tx = await reputation.setStakingContract(config.stakingAddress);
        await tx.wait();
        console.log("   ✅ Staking contract set:", config.stakingAddress);
    } else {
        console.log("   ⚠️  No staking address provided, skipping...");
    }

    // Set KYC registry if provided
    if (config.kycRegistryAddress) {
        console.log("   • Setting KYC registry...");
        const tx = await reputation.setKYCRegistry(config.kycRegistryAddress);
        await tx.wait();
        console.log("   ✅ KYC registry set:", config.kycRegistryAddress);
    } else {
        console.log("   ⚠️  No KYC registry provided, skipping...");
    }

    // Grant reporter role to escrow
    if (config.escrowAddress) {
        console.log("   • Granting reporter role to escrow...");
        const tx = await reputation.grantReporterRole(config.escrowAddress);
        await tx.wait();
        console.log("   ✅ Reporter role granted to escrow:", config.escrowAddress);
    }

    // Grant reporter role to auction
    if (config.auctionAddress) {
        console.log("   • Granting reporter role to auction...");
        const tx = await reputation.grantReporterRole(config.auctionAddress);
        await tx.wait();
        console.log("   ✅ Reporter role granted to auction:", config.auctionAddress);
    }

    // Grant reporter role to verification
    if (config.verificationAddress) {
        console.log("   • Granting reporter role to verification...");
        const tx = await reputation.grantReporterRole(config.verificationAddress);
        await tx.wait();
        console.log("   ✅ Reporter role granted to verification:", config.verificationAddress);
    }

    // ============ Verify Deployment ============
    console.log("\n3️⃣  Verifying deployment...");

    // Check constants
    const maxReputation = await reputation.MAX_REPUTATION();
    const startingReputation = await reputation.STARTING_REPUTATION();
    const minStake = await reputation.MIN_STAKE_FOR_REPUTATION();
    const kycMultiplier = await reputation.KYC_MULTIPLIER();
    const decayInterval = await reputation.DECAY_INTERVAL();

    console.log("   Reputation Settings:");
    console.log(`     • Max Score: ${maxReputation}`);
    console.log(`     • Starting Score: ${startingReputation}`);
    console.log(`     • Min Stake Requirement: ${ethers.formatEther(minStake)} SHAKTI`);
    console.log(`     • KYC Multiplier: ${Number(kycMultiplier) / 100}x`);
    console.log(`     • Decay Interval: ${Number(decayInterval) / 86400} days`);

    // Display tier thresholds
    console.log("\n   Tier Thresholds:");
    console.log(`     • Bronze: 0-${await reputation.BRONZE_MAX()}`);
    console.log(`     • Silver: ${Number(await reputation.BRONZE_MAX()) + 1}-${await reputation.SILVER_MAX()}`);
    console.log(`     • Gold: ${Number(await reputation.SILVER_MAX()) + 1}-${await reputation.GOLD_MAX()}`);
    console.log(`     • Platinum: ${Number(await reputation.GOLD_MAX()) + 1}-${await reputation.PLATINUM_MAX()}`);
    console.log(`     • Diamond: ${Number(await reputation.PLATINUM_MAX()) + 1}-${maxReputation}`);

    // Display tier benefits
    console.log("\n   Tier Benefits:");
    const tiers = ["Bronze", "Silver", "Gold", "Platinum", "Diamond"];
    for (let i = 0; i < 5; i++) {
        const benefits = await reputation.getTierBenefits(i);
        console.log(`     ${tiers[i]}:`);
        console.log(`       - Fee Rate: ${Number(benefits.feeRate) / 100}%`);
        console.log(`       - Transaction Limit: ${ethers.formatEther(benefits.transactionLimit)} kWh`);
        console.log(`       - Governance Multiplier: ${Number(benefits.governanceMultiplier) / 100}x`);
        console.log(`       - Priority Matching: ${benefits.priorityMatching}`);
    }

    // Get system stats
    const [users, distributed, deducted] = await reputation.getSystemStats();
    console.log("\n   Current Statistics:");
    console.log(`     • Total Users: ${users}`);
    console.log(`     • Reputation Distributed: ${distributed}`);
    console.log(`     • Reputation Deducted: ${deducted}`);

    // ============ Summary ============
    console.log("\n" + "=".repeat(60));
    console.log("📋 DEPLOYMENT SUMMARY");
    console.log("=".repeat(60));
    console.log("\nContract Address:");
    console.log("   ReputationSystem:", reputationAddress);

    console.log("\nReputation Score (0-1000):");
    console.log("   • Starting score: 500");
    console.log("   • Successful trade: +5 (max +10 for large trades)");
    console.log("   • Failed delivery: -50");
    console.log("   • Dispute lost: -30");
    console.log("   • Dispute won: +10");
    console.log("   • Weekly decay: -1 per week of inactivity");

    console.log("\nSybil Resistance:");
    console.log(`   • Min stake required: ${ethers.formatEther(minStake)} SHAKTI`);
    console.log("   • KYC verified: 1.5x reputation gains");

    console.log("\nRequired Actions:");
    console.log("   1. Grant REPORTER_ROLE to contracts that update reputation:");
    console.log(`      await reputation.grantReporterRole(contractAddress);`);
    console.log("   2. Update EnergyEscrow to report trades:");
    console.log(`      reputation.recordSuccessfulTrade(user, tradeValue);`);
    console.log("   3. Update EnergyVerification to report outcomes:");
    console.log(`      reputation.recordFailedDelivery(seller);`);
    console.log(`      reputation.recordDisputeOutcome(user, won);`);

    console.log("\nIntegration Points:");
    console.log("   EnergyAuction: compareForPriority(user1, user2) for tie-breaking");
    console.log("   EnergyEscrow: getEffectiveFeeRate(user) for fee calculation");
    console.log("   Governance: getGovernanceMultiplier(user) for voting power");

    console.log("\n" + "=".repeat(60));
    console.log("✅ ReputationSystem deployment completed successfully!");
    console.log("=".repeat(60));

    return {
        reputation: reputationAddress,
    };
}

main()
    .then((addresses) => {
        console.log("\nDeployed addresses:", addresses);
        process.exit(0);
    })
    .catch((error) => {
        console.error("❌ Deployment failed:", error);
        process.exit(1);
    });
