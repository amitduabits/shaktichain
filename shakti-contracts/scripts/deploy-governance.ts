import { ethers } from "hardhat";

async function main() {
    console.log("🚀 Deploying SHAKTI-CHAIN Governance System...\n");

    const [deployer] = await ethers.getSigners();
    console.log("📍 Deployer:", deployer.address);
    console.log("💰 Balance:", ethers.formatEther(await ethers.provider.getBalance(deployer.address)), "ETH\n");

    // ============ Configuration ============
    const config = {
        // Voting parameters
        votingDelay: 7200n, // 1 day in blocks (12s/block)
        votingPeriod: 36000n, // 5 days in blocks
        proposalThreshold: ethers.parseEther("100000"), // 100,000 SHAKTI

        // Timelock parameters
        timelockMinDelay: 2n * 24n * 60n * 60n, // 2 days in seconds

        // Role addresses (can be updated post-deployment)
        proposers: [deployer.address], // Will add governor after deployment
        executors: [deployer.address], // Will add governor after deployment
        admin: deployer.address,
    };

    console.log("📋 Configuration:");
    console.log("   Voting Delay:", config.votingDelay.toString(), "blocks (~1 day)");
    console.log("   Voting Period:", config.votingPeriod.toString(), "blocks (~5 days)");
    console.log("   Proposal Threshold:", ethers.formatEther(config.proposalThreshold), "SHAKTI");
    console.log("   Timelock Delay:", (config.timelockMinDelay / (24n * 60n * 60n)).toString(), "days\n");

    // ============ Deploy StakedShaktiVotes ============
    console.log("1️⃣  Deploying StakedShaktiVotes...");
    const StakedShaktiVotes = await ethers.getContractFactory("StakedShaktiVotes");
    const votesToken = await StakedShaktiVotes.deploy(deployer.address);
    await votesToken.waitForDeployment();
    const votesTokenAddress = await votesToken.getAddress();
    console.log("   ✅ StakedShaktiVotes deployed at:", votesTokenAddress);

    // ============ Deploy ShaktiTimelock ============
    console.log("\n2️⃣  Deploying ShaktiTimelock...");
    const ShaktiTimelock = await ethers.getContractFactory("ShaktiTimelock");
    const timelock = await ShaktiTimelock.deploy(
        config.timelockMinDelay,
        config.proposers,
        config.executors,
        config.admin
    );
    await timelock.waitForDeployment();
    const timelockAddress = await timelock.getAddress();
    console.log("   ✅ ShaktiTimelock deployed at:", timelockAddress);

    // ============ Deploy ShaktiGovernor ============
    console.log("\n3️⃣  Deploying ShaktiGovernor...");
    const ShaktiGovernor = await ethers.getContractFactory("ShaktiGovernor");
    const governor = await ShaktiGovernor.deploy(
        votesTokenAddress,
        timelockAddress,
        config.votingDelay,
        config.votingPeriod,
        config.proposalThreshold
    );
    await governor.waitForDeployment();
    const governorAddress = await governor.getAddress();
    console.log("   ✅ ShaktiGovernor deployed at:", governorAddress);

    // ============ Setup Roles ============
    console.log("\n4️⃣  Setting up roles...");

    // Get role identifiers
    const PROPOSER_ROLE = await timelock.PROPOSER_ROLE();
    const CANCELLER_ROLE = await timelock.CANCELLER_ROLE();
    const EXECUTOR_ROLE = await timelock.EXECUTOR_ROLE();
    const DEFAULT_ADMIN_ROLE = await timelock.DEFAULT_ADMIN_ROLE();

    // Grant governor the proposer role
    console.log("   • Granting PROPOSER_ROLE to Governor...");
    let tx = await timelock.grantRole(PROPOSER_ROLE, governorAddress);
    await tx.wait();

    // Grant governor the canceller role
    console.log("   • Granting CANCELLER_ROLE to Governor...");
    tx = await timelock.grantRole(CANCELLER_ROLE, governorAddress);
    await tx.wait();

    // Grant executor role to governor (so it can execute proposals through timelock)
    console.log("   • Granting EXECUTOR_ROLE to Governor...");
    tx = await timelock.grantRole(EXECUTOR_ROLE, governorAddress);
    await tx.wait();

    // Grant executor role to timelock itself (for self-execution)
    console.log("   • Granting EXECUTOR_ROLE to Timelock...");
    tx = await timelock.grantRole(EXECUTOR_ROLE, timelockAddress);
    await tx.wait();

    // IMPORTANT: In production, you should:
    // 1. Renounce deployer's admin role after setup
    // 2. Transfer admin to timelock for full decentralization
    // For now, keeping admin for easier management during development

    console.log("   ✅ Roles configured successfully");

    // ============ Verify Configuration ============
    console.log("\n5️⃣  Verifying deployment...");

    // Verify governor configuration
    const actualVotingDelay = await governor.votingDelay();
    const actualVotingPeriod = await governor.votingPeriod();
    const actualProposalThreshold = await governor.proposalThreshold();
    const actualTimelock = await governor.timelock();
    const actualToken = await governor.token();
    const emergencyThreshold = await governor.emergencyThreshold();

    console.log("   Governor:");
    console.log("   • Voting Delay:", actualVotingDelay.toString(), "blocks");
    console.log("   • Voting Period:", actualVotingPeriod.toString(), "blocks");
    console.log("   • Proposal Threshold:", ethers.formatEther(actualProposalThreshold), "SHAKTI");
    console.log("   • Emergency Threshold:", ethers.formatEther(emergencyThreshold), "SHAKTI");
    console.log("   • Timelock:", actualTimelock);
    console.log("   • Token:", actualToken);

    // Verify timelock configuration
    const standardDelay = await timelock.standardDelay();
    const minDelay = await timelock.MIN_DELAY();
    const maxDelay = await timelock.MAX_DELAY();
    const emergencyDelay = await timelock.EMERGENCY_DELAY();

    console.log("\n   Timelock:");
    console.log("   • Standard Delay:", (standardDelay / (24n * 60n * 60n)).toString(), "days");
    console.log("   • Min Delay:", (minDelay / (24n * 60n * 60n)).toString(), "days");
    console.log("   • Max Delay:", (maxDelay / (24n * 60n * 60n)).toString(), "days");
    console.log("   • Emergency Delay:", (emergencyDelay / (60n * 60n)).toString(), "hours");

    // Verify votes token
    const tokenName = await votesToken.name();
    const tokenSymbol = await votesToken.symbol();
    const autoDelegateEnabled = await votesToken.autoDelegateEnabled();

    console.log("\n   Votes Token:");
    console.log("   • Name:", tokenName);
    console.log("   • Symbol:", tokenSymbol);
    console.log("   • Auto-Delegate:", autoDelegateEnabled);

    // ============ Summary ============
    console.log("\n" + "=".repeat(60));
    console.log("📋 DEPLOYMENT SUMMARY");
    console.log("=".repeat(60));
    console.log("\nContract Addresses:");
    console.log("   StakedShaktiVotes:", votesTokenAddress);
    console.log("   ShaktiTimelock:   ", timelockAddress);
    console.log("   ShaktiGovernor:   ", governorAddress);

    console.log("\nNext Steps:");
    console.log("   1. Authorize StakingPool as minter on StakedShaktiVotes");
    console.log("   2. Integrate StakedShaktiVotes with StakingPool");
    console.log("   3. Test proposal creation and voting");
    console.log("   4. Consider renouncing admin role for full decentralization");

    console.log("\nIntegration Commands:");
    console.log(`   // Authorize staking pool as minter`);
    console.log(`   await votesToken.authorizeMinter(stakingPoolAddress);`);

    console.log("\n" + "=".repeat(60));
    console.log("✅ Governance deployment completed successfully!");
    console.log("=".repeat(60));

    return {
        votesToken: votesTokenAddress,
        timelock: timelockAddress,
        governor: governorAddress,
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
