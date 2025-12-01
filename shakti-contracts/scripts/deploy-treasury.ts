import { ethers } from "hardhat";

async function main() {
    console.log("🚀 Deploying SHAKTI-CHAIN Treasury...\n");

    const [deployer] = await ethers.getSigners();
    console.log("📍 Deployer:", deployer.address);
    console.log("💰 Balance:", ethers.formatEther(await ethers.provider.getBalance(deployer.address)), "ETH\n");

    // ============ Configuration ============
    // IMPORTANT: Replace these with actual addresses in production
    const config = {
        // Token address (should be deployed ShaktiToken)
        tokenAddress: process.env.SHAKTI_TOKEN_ADDRESS || "",

        // Staking pool address (should be deployed StakingPool)
        stakingPoolAddress: process.env.STAKING_POOL_ADDRESS || "",

        // Escrow address (should be deployed EnergyEscrow)
        escrowAddress: process.env.ENERGY_ESCROW_ADDRESS || "",

        // Multisig signers (5 addresses required)
        // In production, these should be hardware wallet addresses from core team
        signers: [
            process.env.SIGNER_1 || deployer.address,
            process.env.SIGNER_2 || deployer.address,
            process.env.SIGNER_3 || deployer.address,
            process.env.SIGNER_4 || deployer.address,
            process.env.SIGNER_5 || deployer.address,
        ],

        admin: deployer.address,
    };

    // For localhost testing, deploy a mock token if not provided
    let tokenAddress = config.tokenAddress;

    if (!tokenAddress) {
        console.log("⚠️  No token address provided, deploying ShaktiToken for testing...");
        const ShaktiToken = await ethers.getContractFactory("ShaktiToken");
        const token = await ShaktiToken.deploy(deployer.address, deployer.address);
        await token.waitForDeployment();
        tokenAddress = await token.getAddress();
        console.log("   ✅ ShaktiToken deployed at:", tokenAddress);
    }

    // Ensure unique signers for testing
    const uniqueSigners = new Set(config.signers);
    if (uniqueSigners.size !== 5) {
        // Generate unique signers from deployer for testing
        console.log("⚠️  Generating test signers (deployer is all signers for testing)...");
        const accounts = await ethers.getSigners();
        config.signers = accounts.slice(0, 5).map(a => a.address);
        if (config.signers.length < 5) {
            // If not enough accounts, pad with deployer
            while (config.signers.length < 5) {
                const wallet = ethers.Wallet.createRandom();
                config.signers.push(wallet.address);
            }
        }
    }

    console.log("📋 Configuration:");
    console.log("   Token Address:", tokenAddress);
    console.log("   Admin:", config.admin);
    console.log("   Signers:");
    config.signers.forEach((s, i) => console.log(`     ${i + 1}. ${s}`));
    console.log();

    // ============ Deploy Treasury ============
    console.log("1️⃣  Deploying Treasury...");
    const Treasury = await ethers.getContractFactory("Treasury");
    const treasury = await Treasury.deploy(
        tokenAddress,
        config.admin,
        config.signers
    );
    await treasury.waitForDeployment();
    const treasuryAddress = await treasury.getAddress();
    console.log("   ✅ Treasury deployed at:", treasuryAddress);

    // ============ Setup Integrations ============
    console.log("\n2️⃣  Setting up integrations...");

    // Set staking pool if provided
    if (config.stakingPoolAddress) {
        console.log("   • Setting staking pool...");
        const tx = await treasury.setStakingPool(config.stakingPoolAddress);
        await tx.wait();
        console.log("   ✅ Staking pool set to:", config.stakingPoolAddress);
    } else {
        console.log("   ⚠️  No staking pool address provided, skipping...");
    }

    // Authorize escrow if provided
    if (config.escrowAddress) {
        console.log("   • Authorizing escrow...");
        const tx = await treasury.authorizeEscrow(config.escrowAddress);
        await tx.wait();
        console.log("   ✅ Escrow authorized:", config.escrowAddress);
    } else {
        console.log("   ⚠️  No escrow address provided, skipping...");
    }

    // ============ Verify Deployment ============
    console.log("\n3️⃣  Verifying deployment...");

    // Check signers
    const signers = await treasury.getSigners();
    console.log("   Signers configured:", signers.length);

    // Check constants
    const stakingShare = await treasury.STAKING_SHARE();
    const devShare = await treasury.DEVELOPMENT_SHARE();
    const grantsShare = await treasury.GRANTS_SHARE();
    const requiredSigs = await treasury.REQUIRED_SIGNATURES();
    const timelockThreshold = await treasury.TIMELOCK_THRESHOLD();
    const timelockDuration = await treasury.TIMELOCK_DURATION();
    const distributionInterval = await treasury.DISTRIBUTION_INTERVAL();

    console.log("\n   Distribution Shares:");
    console.log(`     • Staking: ${Number(stakingShare) / 100}%`);
    console.log(`     • Development: ${Number(devShare) / 100}%`);
    console.log(`     • Grants: ${Number(grantsShare) / 100}%`);

    console.log("\n   Multisig Settings:");
    console.log(`     • Required Signatures: ${requiredSigs}/5`);
    console.log(`     • Timelock Threshold: ${ethers.formatEther(timelockThreshold)} SHAKTI`);
    console.log(`     • Timelock Duration: ${Number(timelockDuration) / 3600} hours`);

    console.log("\n   Distribution Settings:");
    console.log(`     • Distribution Interval: ${Number(distributionInterval) / 86400} days`);

    // Get allocations
    const allocations = await treasury.getAllocations();
    console.log("\n   Current Allocations:");
    console.log(`     • Staking: ${ethers.formatEther(allocations.staking)} SHAKTI`);
    console.log(`     • Development: ${ethers.formatEther(allocations.development)} SHAKTI`);
    console.log(`     • Grants: ${ethers.formatEther(allocations.communityGrants)} SHAKTI`);
    console.log(`     • Total Balance: ${ethers.formatEther(allocations.total)} SHAKTI`);

    // ============ Summary ============
    console.log("\n" + "=".repeat(60));
    console.log("📋 DEPLOYMENT SUMMARY");
    console.log("=".repeat(60));
    console.log("\nContract Address:");
    console.log("   Treasury:", treasuryAddress);

    console.log("\nMultisig Signers:");
    signers.forEach((s, i) => console.log(`   ${i + 1}. ${s}`));

    console.log("\nRequired Actions:");
    console.log("   1. Set staking pool address if not done:");
    console.log(`      await treasury.setStakingPool(stakingPoolAddress);`);
    console.log("   2. Authorize escrow contract:");
    console.log(`      await treasury.authorizeEscrow(escrowAddress);`);
    console.log("   3. Update EnergyEscrow to send fees to Treasury:");
    console.log(`      // In EnergyEscrow: treasury.receiveFees(feeAmount);`);

    console.log("\nIntegration Flow:");
    console.log("   EnergyEscrow → (70% of fee) → Treasury");
    console.log("   Treasury → (50%) → StakingPool (weekly)");
    console.log("   Treasury → (30%) → Development (multisig)");
    console.log("   Treasury → (20%) → Community Grants (governance)");

    console.log("\n" + "=".repeat(60));
    console.log("✅ Treasury deployment completed successfully!");
    console.log("=".repeat(60));

    return {
        treasury: treasuryAddress,
        token: tokenAddress,
        signers: config.signers,
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
