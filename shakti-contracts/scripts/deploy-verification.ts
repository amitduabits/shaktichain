import { ethers } from "hardhat";

async function main() {
    console.log("🚀 Deploying SHAKTI-CHAIN EnergyVerification...\n");

    const [deployer] = await ethers.getSigners();
    console.log("📍 Deployer:", deployer.address);
    console.log("💰 Balance:", ethers.formatEther(await ethers.provider.getBalance(deployer.address)), "ETH\n");

    // ============ Configuration ============
    // IMPORTANT: Replace these with actual addresses in production
    const config = {
        // Escrow address (should be deployed EnergyEscrow)
        escrowAddress: process.env.ENERGY_ESCROW_ADDRESS || "",

        // DISCOM addresses to trust (comma-separated)
        discomAddresses: process.env.DISCOM_ADDRESSES?.split(",") || [],

        // Oracle address (Chainlink Functions or custom oracle)
        oracleAddress: process.env.ORACLE_ADDRESS || "",

        // Staking contract address (for slash integration)
        stakingAddress: process.env.STAKING_POOL_ADDRESS || "",

        admin: deployer.address,
    };

    console.log("📋 Configuration:");
    console.log("   Admin:", config.admin);
    console.log("   Escrow Address:", config.escrowAddress || "Not provided");
    console.log("   Oracle Address:", config.oracleAddress || "Not provided");
    console.log("   Staking Address:", config.stakingAddress || "Not provided");
    console.log("   DISCOM Addresses:", config.discomAddresses.length > 0 ? config.discomAddresses.join(", ") : "None provided");
    console.log();

    // ============ Deploy EnergyVerification ============
    console.log("1️⃣  Deploying EnergyVerification...");
    const EnergyVerification = await ethers.getContractFactory("EnergyVerification");
    const verification = await EnergyVerification.deploy(config.admin);
    await verification.waitForDeployment();
    const verificationAddress = await verification.getAddress();
    console.log("   ✅ EnergyVerification deployed at:", verificationAddress);

    // ============ Setup Roles ============
    console.log("\n2️⃣  Setting up roles...");

    // Grant ESCROW_ROLE if escrow address provided
    if (config.escrowAddress) {
        console.log("   • Granting ESCROW_ROLE...");
        const escrowRole = await verification.ESCROW_ROLE();
        const tx = await verification.grantRole(escrowRole, config.escrowAddress);
        await tx.wait();
        console.log("   ✅ ESCROW_ROLE granted to:", config.escrowAddress);

        // Also set escrow contract
        const setTx = await verification.setEscrowContract(config.escrowAddress);
        await setTx.wait();
        console.log("   ✅ Escrow contract set:", config.escrowAddress);
    } else {
        console.log("   ⚠️  No escrow address provided, skipping ESCROW_ROLE setup...");
    }

    // Grant ORACLE_ROLE if oracle address provided
    if (config.oracleAddress) {
        console.log("   • Granting ORACLE_ROLE...");
        const oracleRole = await verification.ORACLE_ROLE();
        const tx = await verification.grantRole(oracleRole, config.oracleAddress);
        await tx.wait();
        console.log("   ✅ ORACLE_ROLE granted to:", config.oracleAddress);
    } else {
        console.log("   ⚠️  No oracle address provided, skipping ORACLE_ROLE setup...");
    }

    // Set staking contract if provided
    if (config.stakingAddress) {
        console.log("   • Setting staking contract...");
        const tx = await verification.setStakingContract(config.stakingAddress);
        await tx.wait();
        console.log("   ✅ Staking contract set:", config.stakingAddress);
    } else {
        console.log("   ⚠️  No staking address provided, skipping...");
    }

    // Trust DISCOMs if provided
    if (config.discomAddresses.length > 0) {
        console.log("   • Trusting DISCOM addresses...");
        for (const discom of config.discomAddresses) {
            if (discom && discom.trim()) {
                const tx = await verification.setDISCOMTrust(discom.trim(), true);
                await tx.wait();
                console.log("   ✅ DISCOM trusted:", discom.trim());
            }
        }
    } else {
        console.log("   ⚠️  No DISCOM addresses provided, skipping...");
    }

    // ============ Verify Deployment ============
    console.log("\n3️⃣  Verifying deployment...");

    // Check roles
    const escrowRole = await verification.ESCROW_ROLE();
    const oracleRole = await verification.ORACLE_ROLE();
    const arbiterRole = await verification.ARBITER_ROLE();
    const pauserRole = await verification.PAUSER_ROLE();

    console.log("   Roles configured:");
    console.log(`     • Admin has DEFAULT_ADMIN_ROLE: ${await verification.hasRole(await verification.DEFAULT_ADMIN_ROLE(), config.admin)}`);
    console.log(`     • Admin has ARBITER_ROLE: ${await verification.hasRole(arbiterRole, config.admin)}`);
    console.log(`     • Admin has PAUSER_ROLE: ${await verification.hasRole(pauserRole, config.admin)}`);

    if (config.escrowAddress) {
        console.log(`     • Escrow has ESCROW_ROLE: ${await verification.hasRole(escrowRole, config.escrowAddress)}`);
    }

    if (config.oracleAddress) {
        console.log(`     • Oracle has ORACLE_ROLE: ${await verification.hasRole(oracleRole, config.oracleAddress)}`);
    }

    // Check constants
    const deliveryWindow = await verification.DELIVERY_WINDOW();
    const quantityTolerance = await verification.QUANTITY_TOLERANCE();
    const peerThreshold = await verification.PEER_ATTESTATION_THRESHOLD();
    const nonDeliverySlash = await verification.NON_DELIVERY_SLASH();
    const falseDisputeSlash = await verification.FALSE_DISPUTE_SLASH();
    const tempBanThreshold = await verification.TEMP_BAN_THRESHOLD();
    const permBanThreshold = await verification.PERM_BAN_THRESHOLD();
    const tempBanDuration = await verification.TEMP_BAN_DURATION();

    console.log("\n   Verification Settings:");
    console.log(`     • Delivery Window: ${Number(deliveryWindow) / 3600} hours`);
    console.log(`     • Quantity Tolerance: ${Number(quantityTolerance) / 100}%`);
    console.log(`     • Peer Attestation Threshold: ${ethers.formatEther(peerThreshold)} kWh`);

    console.log("\n   Slashing Settings:");
    console.log(`     • Non-Delivery Slash: ${Number(nonDeliverySlash) / 100}%`);
    console.log(`     • False Dispute Slash: ${Number(falseDisputeSlash) / 100}%`);

    console.log("\n   Banning Settings:");
    console.log(`     • Temp Ban Threshold: ${tempBanThreshold} offenses`);
    console.log(`     • Perm Ban Threshold: ${permBanThreshold} offenses`);
    console.log(`     • Temp Ban Duration: ${Number(tempBanDuration) / 86400} days`);

    // Get verification stats
    const stats = await verification.getVerificationStats();
    console.log("\n   Current Statistics:");
    console.log(`     • Total Trades: ${stats.total}`);
    console.log(`     • Successful Deliveries: ${stats.successful}`);
    console.log(`     • Failed Deliveries: ${stats.failed}`);
    console.log(`     • Total Slashed: ${ethers.formatEther(stats.slashed)} SHAKTI`);

    // ============ Summary ============
    console.log("\n" + "=".repeat(60));
    console.log("📋 DEPLOYMENT SUMMARY");
    console.log("=".repeat(60));
    console.log("\nContract Address:");
    console.log("   EnergyVerification:", verificationAddress);

    console.log("\nVerification Methods:");
    console.log("   1. DISCOM Attestation (Primary)");
    console.log("      - Signed attestation from trusted DISCOM");
    console.log("      - Auto-confirms if within 5% tolerance");
    console.log("   2. Smart Meter Oracle (Secondary)");
    console.log("      - Chainlink Functions reads meter API");
    console.log("      - Requires ORACLE_ROLE");
    console.log("   3. Peer Attestation (Backup)");
    console.log("      - Buyer confirms for small trades < 10 kWh");
    console.log("      - Requires 70% reputation");

    console.log("\nVerification Flow:");
    console.log("   1. Trade registered by EnergyEscrow");
    console.log("   2. Seller has 4 hours to deliver energy");
    console.log("   3. Verification method reports delivery");
    console.log("   4. Settlement releases funds");

    console.log("\nRequired Actions:");
    console.log("   1. Update EnergyEscrow to call verification:");
    console.log(`      verification.registerTrade(tradeId, seller, buyer, qty, value, discom);`);
    console.log("   2. Trust DISCOM addresses:");
    console.log(`      await verification.setDISCOMTrust(discomAddress, true);`);
    console.log("   3. Grant ORACLE_ROLE to oracle:");
    console.log(`      await verification.grantRole(ORACLE_ROLE, oracleAddress);`);

    console.log("\n" + "=".repeat(60));
    console.log("✅ EnergyVerification deployment completed successfully!");
    console.log("=".repeat(60));

    return {
        verification: verificationAddress,
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
