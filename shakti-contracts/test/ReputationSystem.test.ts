import { expect } from "chai";
import { ethers } from "hardhat";
import { time } from "@nomicfoundation/hardhat-network-helpers";
import { HardhatEthersSigner } from "@nomicfoundation/hardhat-ethers/signers";
import { ReputationSystem } from "../typechain-types";

describe("ReputationSystem", function () {
    let reputation: ReputationSystem;

    let admin: HardhatEthersSigner;
    let reporter: HardhatEthersSigner;
    let verifier: HardhatEthersSigner;
    let user1: HardhatEthersSigner;
    let user2: HardhatEthersSigner;
    let user3: HardhatEthersSigner;
    let other: HardhatEthersSigner;

    const STARTING_REPUTATION = 500n;
    const MAX_REPUTATION = 1000n;
    const MIN_STAKE = ethers.parseEther("100");
    const LARGE_TRADE = ethers.parseEther("100");
    const SMALL_TRADE = ethers.parseEther("50");
    const WEEK = 7 * 24 * 60 * 60;

    // Tier thresholds
    const BRONZE_MAX = 300n;
    const SILVER_MAX = 500n;
    const GOLD_MAX = 700n;
    const PLATINUM_MAX = 850n;

    // Reputation changes
    const SUCCESSFUL_TRADE_BASE = 5n;
    const SUCCESSFUL_TRADE_LARGE = 10n;
    const FAILED_DELIVERY = -50n;
    const DISPUTE_LOST = -30n;
    const DISPUTE_WON = 10n;

    // Tiers enum
    enum Tier {
        Bronze = 0,
        Silver = 1,
        Gold = 2,
        Platinum = 3,
        Diamond = 4
    }

    // ReputationType enum
    enum ReputationType {
        SuccessfulTrade = 0,
        SuccessfulTradeLarge = 1,
        FailedDelivery = 2,
        DisputeLost = 3,
        DisputeWon = 4,
        WeeklyDecay = 5,
        AdminAdjustment = 6,
        FlagPenalty = 7
    }

    beforeEach(async function () {
        [admin, reporter, verifier, user1, user2, user3, other] = await ethers.getSigners();

        // Deploy ReputationSystem
        const ReputationSystem = await ethers.getContractFactory("ReputationSystem");
        reputation = await ReputationSystem.deploy(admin.address);
        await reputation.waitForDeployment();

        // Setup roles
        await reputation.connect(admin).grantReporterRole(reporter.address);
        await reputation.connect(admin).grantRole(await reputation.VERIFIER_ROLE(), verifier.address);
    });

    // ============ Deployment Tests ============

    describe("Deployment", function () {
        it("should deploy with correct admin", async function () {
            expect(await reputation.hasRole(await reputation.DEFAULT_ADMIN_ROLE(), admin.address)).to.be.true;
        });

        it("should revert if admin is zero address", async function () {
            const ReputationSystem = await ethers.getContractFactory("ReputationSystem");
            await expect(ReputationSystem.deploy(ethers.ZeroAddress))
                .to.be.revertedWithCustomError(reputation, "ZeroAddress");
        });

        it("should set correct constants", async function () {
            expect(await reputation.MAX_REPUTATION()).to.equal(MAX_REPUTATION);
            expect(await reputation.STARTING_REPUTATION()).to.equal(STARTING_REPUTATION);
            expect(await reputation.MIN_STAKE_FOR_REPUTATION()).to.equal(MIN_STAKE);
        });

        it("should initialize tier benefits", async function () {
            const bronzeBenefits = await reputation.getTierBenefits(Tier.Bronze);
            expect(bronzeBenefits.feeRate).to.equal(250); // 2.5%

            const diamondBenefits = await reputation.getTierBenefits(Tier.Diamond);
            expect(diamondBenefits.feeRate).to.equal(50); // 0.5%
            expect(diamondBenefits.feeRebates).to.be.true;
        });
    });

    // ============ Registration Tests ============

    describe("Registration", function () {
        it("should register a new user", async function () {
            await reputation.registerUser(user1.address);

            expect(await reputation.isRegistered(user1.address)).to.be.true;
            const [score, tier] = await reputation.getReputation(user1.address);
            expect(score).to.equal(STARTING_REPUTATION);
            expect(tier).to.equal(Tier.Silver); // 500 is Silver
        });

        it("should emit UserRegistered event", async function () {
            await expect(reputation.registerUser(user1.address))
                .to.emit(reputation, "UserRegistered")
                .withArgs(user1.address, STARTING_REPUTATION);
        });

        it("should increment total users", async function () {
            await reputation.registerUser(user1.address);
            await reputation.registerUser(user2.address);

            expect(await reputation.totalUsers()).to.equal(2);
        });

        it("should revert if user already registered", async function () {
            await reputation.registerUser(user1.address);

            await expect(reputation.registerUser(user1.address))
                .to.be.revertedWithCustomError(reputation, "UserAlreadyRegistered");
        });

        it("should revert for zero address", async function () {
            await expect(reputation.registerUser(ethers.ZeroAddress))
                .to.be.revertedWithCustomError(reputation, "ZeroAddress");
        });

        it("should record initial reputation in history", async function () {
            await reputation.registerUser(user1.address);

            const historyLength = await reputation.getReputationHistoryLength(user1.address);
            expect(historyLength).to.equal(1);

            const entry = await reputation.getReputationHistoryAt(user1.address, 0);
            expect(entry.newScore).to.equal(STARTING_REPUTATION);
        });
    });

    // ============ Reputation Updates Tests ============

    describe("Reputation Updates", function () {
        beforeEach(async function () {
            await reputation.registerUser(user1.address);
            // Set stake for user1
            await reputation.connect(reporter).updateStake(user1.address, MIN_STAKE);
        });

        it("should record successful small trade", async function () {
            await reputation.connect(reporter).recordSuccessfulTrade(user1.address, SMALL_TRADE);

            const [score] = await reputation.getReputation(user1.address);
            expect(score).to.equal(STARTING_REPUTATION + SUCCESSFUL_TRADE_BASE);
        });

        it("should record successful large trade", async function () {
            await reputation.connect(reporter).recordSuccessfulTrade(user1.address, LARGE_TRADE);

            const [score] = await reputation.getReputation(user1.address);
            expect(score).to.equal(STARTING_REPUTATION + SUCCESSFUL_TRADE_LARGE);
        });

        it("should apply KYC multiplier to gains", async function () {
            // Verify KYC
            await reputation.connect(verifier).updateKYCStatus(user1.address, true);

            await reputation.connect(reporter).recordSuccessfulTrade(user1.address, SMALL_TRADE);

            // 5 * 1.5 = 7 (rounded down)
            const [score] = await reputation.getReputation(user1.address);
            expect(score).to.equal(STARTING_REPUTATION + 7n);
        });

        it("should record failed delivery", async function () {
            await reputation.connect(reporter).recordFailedDelivery(user1.address);

            const [score] = await reputation.getReputation(user1.address);
            expect(score).to.equal(STARTING_REPUTATION + FAILED_DELIVERY);
        });

        it("should record dispute won", async function () {
            await reputation.connect(reporter).recordDisputeOutcome(user1.address, true);

            const [score] = await reputation.getReputation(user1.address);
            expect(score).to.equal(STARTING_REPUTATION + DISPUTE_WON);
        });

        it("should record dispute lost", async function () {
            await reputation.connect(reporter).recordDisputeOutcome(user1.address, false);

            const [score] = await reputation.getReputation(user1.address);
            expect(score).to.equal(STARTING_REPUTATION + DISPUTE_LOST);
        });

        it("should emit ReputationUpdated event", async function () {
            await expect(reputation.connect(reporter).recordSuccessfulTrade(user1.address, SMALL_TRADE))
                .to.emit(reputation, "ReputationUpdated");
        });

        it("should cap reputation at MAX", async function () {
            // Admin boost to near max
            await reputation.connect(admin).adminAdjustReputation(user1.address, 450, "Boost");

            // Another boost that would exceed max
            await reputation.connect(admin).adminAdjustReputation(user1.address, 100, "Boost");

            const [score] = await reputation.getReputation(user1.address);
            expect(score).to.equal(MAX_REPUTATION);
        });

        it("should not go below 0", async function () {
            // Many failed deliveries
            for (let i = 0; i < 15; i++) {
                await reputation.connect(reporter).recordFailedDelivery(user1.address);
            }

            const [score] = await reputation.getReputation(user1.address);
            expect(score).to.equal(0n);
        });

        it("should revert if not registered", async function () {
            await expect(reputation.connect(reporter).recordSuccessfulTrade(user2.address, SMALL_TRADE))
                .to.be.revertedWithCustomError(reputation, "UserNotRegistered");
        });

        it("should revert if insufficient stake", async function () {
            await reputation.registerUser(user2.address);
            // No stake set

            await expect(reputation.connect(reporter).recordSuccessfulTrade(user2.address, SMALL_TRADE))
                .to.be.revertedWithCustomError(reputation, "InsufficientStake");
        });

        it("should update trade statistics", async function () {
            await reputation.connect(reporter).recordSuccessfulTrade(user1.address, SMALL_TRADE);
            await reputation.connect(reporter).recordFailedDelivery(user1.address);

            const userData = await reputation.getUserReputation(user1.address);
            expect(userData.totalTrades).to.equal(2);
            expect(userData.successfulTrades).to.equal(1);
            expect(userData.failedTrades).to.equal(1);
        });
    });

    // ============ Decay Tests ============

    describe("Decay", function () {
        beforeEach(async function () {
            await reputation.registerUser(user1.address);
        });

        it("should apply decay after 1 week of inactivity", async function () {
            await time.increase(WEEK + 1);

            await reputation.applyDecay(user1.address);

            const [score] = await reputation.getReputation(user1.address);
            expect(score).to.equal(STARTING_REPUTATION - 1n);
        });

        it("should apply decay for multiple weeks (capped at 10)", async function () {
            await time.increase(WEEK * 20);

            await reputation.applyDecay(user1.address);

            const [score] = await reputation.getReputation(user1.address);
            expect(score).to.equal(STARTING_REPUTATION - 10n); // Capped at 10
        });

        it("should emit DecayApplied event", async function () {
            await time.increase(WEEK + 1);

            await expect(reputation.applyDecay(user1.address))
                .to.emit(reputation, "ReputationUpdated");
        });

        it("should revert if cooldown not expired", async function () {
            await expect(reputation.applyDecay(user1.address))
                .to.be.revertedWithCustomError(reputation, "CooldownNotExpired");
        });

        it("should batch apply decay", async function () {
            await reputation.registerUser(user2.address);
            await time.increase(WEEK + 1);

            await reputation.batchApplyDecay([user1.address, user2.address]);

            const [score1] = await reputation.getReputation(user1.address);
            const [score2] = await reputation.getReputation(user2.address);
            expect(score1).to.equal(STARTING_REPUTATION - 1n);
            expect(score2).to.equal(STARTING_REPUTATION - 1n);
        });

        it("should return pending decay amount", async function () {
            await time.increase(WEEK * 3);

            const pendingDecay = await reputation.getPendingDecay(user1.address);
            expect(pendingDecay).to.equal(3);
        });
    });

    // ============ Tier Tests ============

    describe("Tiers", function () {
        beforeEach(async function () {
            await reputation.registerUser(user1.address);
        });

        it("should start at Silver tier", async function () {
            const [, tier] = await reputation.getReputation(user1.address);
            expect(tier).to.equal(Tier.Silver);
        });

        it("should downgrade to Bronze on reputation loss", async function () {
            // Drop below 300
            await reputation.connect(admin).adminAdjustReputation(user1.address, -250, "Test");

            const [score, tier] = await reputation.getReputation(user1.address);
            expect(score).to.equal(250n);
            expect(tier).to.equal(Tier.Bronze);
        });

        it("should upgrade to Gold on reputation gain", async function () {
            // Boost above 500
            await reputation.connect(admin).adminAdjustReputation(user1.address, 150, "Test");

            const [score, tier] = await reputation.getReputation(user1.address);
            expect(score).to.equal(650n);
            expect(tier).to.equal(Tier.Gold);
        });

        it("should upgrade to Platinum", async function () {
            await reputation.connect(admin).adminAdjustReputation(user1.address, 300, "Test");

            const [score, tier] = await reputation.getReputation(user1.address);
            expect(score).to.equal(800n);
            expect(tier).to.equal(Tier.Platinum);
        });

        it("should upgrade to Diamond", async function () {
            await reputation.connect(admin).adminAdjustReputation(user1.address, 400, "Test");

            const [score, tier] = await reputation.getReputation(user1.address);
            expect(score).to.equal(900n);
            expect(tier).to.equal(Tier.Diamond);
        });

        it("should emit TierChanged event", async function () {
            await expect(reputation.connect(admin).adminAdjustReputation(user1.address, 150, "Test"))
                .to.emit(reputation, "TierChanged")
                .withArgs(user1.address, Tier.Silver, Tier.Gold);
        });
    });

    // ============ Tier Benefits Tests ============

    describe("Tier Benefits", function () {
        beforeEach(async function () {
            await reputation.registerUser(user1.address);
        });

        it("should return correct fee rates by tier", async function () {
            // Bronze
            await reputation.connect(admin).adminAdjustReputation(user1.address, -300, "Test");
            expect(await reputation.getEffectiveFeeRate(user1.address)).to.equal(250);

            // Silver
            await reputation.connect(admin).adminAdjustReputation(user1.address, 200, "Test");
            expect(await reputation.getEffectiveFeeRate(user1.address)).to.equal(200);

            // Gold
            await reputation.connect(admin).adminAdjustReputation(user1.address, 200, "Test");
            expect(await reputation.getEffectiveFeeRate(user1.address)).to.equal(150);

            // Platinum
            await reputation.connect(admin).adminAdjustReputation(user1.address, 200, "Test");
            expect(await reputation.getEffectiveFeeRate(user1.address)).to.equal(100);

            // Diamond
            await reputation.connect(admin).adminAdjustReputation(user1.address, 200, "Test");
            expect(await reputation.getEffectiveFeeRate(user1.address)).to.equal(50);
        });

        it("should return correct fee discounts", async function () {
            // Silver (starting) - 0.5% discount
            expect(await reputation.calculateFeeDiscount(user1.address)).to.equal(50);

            // Gold - 1% discount
            await reputation.connect(admin).adminAdjustReputation(user1.address, 150, "Test");
            expect(await reputation.calculateFeeDiscount(user1.address)).to.equal(100);
        });

        it("should return correct transaction limits", async function () {
            // Silver
            expect(await reputation.getTransactionLimit(user1.address)).to.equal(ethers.parseEther("100"));

            // Gold
            await reputation.connect(admin).adminAdjustReputation(user1.address, 150, "Test");
            expect(await reputation.getTransactionLimit(user1.address)).to.equal(ethers.parseEther("250"));

            // Diamond
            await reputation.connect(admin).adminAdjustReputation(user1.address, 350, "Test");
            expect(await reputation.getTransactionLimit(user1.address)).to.equal(ethers.parseEther("1000"));
        });

        it("should return correct governance multiplier", async function () {
            // Silver - 1x
            expect(await reputation.getGovernanceMultiplier(user1.address)).to.equal(100);

            // Gold - 1.2x
            await reputation.connect(admin).adminAdjustReputation(user1.address, 150, "Test");
            expect(await reputation.getGovernanceMultiplier(user1.address)).to.equal(120);

            // Diamond - 2x
            await reputation.connect(admin).adminAdjustReputation(user1.address, 350, "Test");
            expect(await reputation.getGovernanceMultiplier(user1.address)).to.equal(200);
        });

        it("should return priority matching status", async function () {
            // Silver - no priority
            expect(await reputation.hasPriorityMatching(user1.address)).to.be.false;

            // Gold - has priority
            await reputation.connect(admin).adminAdjustReputation(user1.address, 150, "Test");
            expect(await reputation.hasPriorityMatching(user1.address)).to.be.true;
        });
    });

    // ============ Sybil Resistance Tests ============

    describe("Sybil Resistance", function () {
        beforeEach(async function () {
            await reputation.registerUser(user1.address);
        });

        it("should require minimum stake for reputation gains", async function () {
            // No stake - should fail
            await expect(reputation.connect(reporter).recordSuccessfulTrade(user1.address, SMALL_TRADE))
                .to.be.revertedWithCustomError(reputation, "InsufficientStake");

            // Add stake
            await reputation.connect(reporter).updateStake(user1.address, MIN_STAKE);

            // Now should work
            await reputation.connect(reporter).recordSuccessfulTrade(user1.address, SMALL_TRADE);
            const [score] = await reputation.getReputation(user1.address);
            expect(score).to.be.gt(STARTING_REPUTATION);
        });

        it("should emit StakeUpdated event", async function () {
            await expect(reputation.connect(reporter).updateStake(user1.address, MIN_STAKE))
                .to.emit(reputation, "StakeUpdated")
                .withArgs(user1.address, MIN_STAKE);
        });

        it("should apply KYC multiplier (1.5x)", async function () {
            await reputation.connect(reporter).updateStake(user1.address, MIN_STAKE);
            await reputation.connect(verifier).updateKYCStatus(user1.address, true);

            await reputation.connect(reporter).recordSuccessfulTrade(user1.address, SMALL_TRADE);

            // 5 * 1.5 = 7.5 -> 7
            const [score] = await reputation.getReputation(user1.address);
            expect(score).to.equal(STARTING_REPUTATION + 7n);
        });

        it("should emit KYCStatusUpdated event", async function () {
            await expect(reputation.connect(verifier).updateKYCStatus(user1.address, true))
                .to.emit(reputation, "KYCStatusUpdated")
                .withArgs(user1.address, true);
        });

        it("should return canBuildReputation status", async function () {
            expect(await reputation.canBuildReputation(user1.address)).to.be.false;

            await reputation.connect(reporter).updateStake(user1.address, MIN_STAKE);
            expect(await reputation.canBuildReputation(user1.address)).to.be.true;
        });
    });

    // ============ Flagging Tests ============

    describe("Flagging", function () {
        beforeEach(async function () {
            await reputation.registerUser(user1.address);
            await reputation.connect(reporter).updateStake(user1.address, MIN_STAKE);
        });

        it("should flag user for suspicious activity", async function () {
            await reputation.connect(verifier).flagUser(user1.address, "Suspicious pattern");

            const userData = await reputation.getUserReputation(user1.address);
            expect(userData.isFlagged).to.be.true;
            expect(userData.flagReason).to.equal("Suspicious pattern");
        });

        it("should apply penalty when flagging", async function () {
            await reputation.connect(verifier).flagUser(user1.address, "Test");

            const [score] = await reputation.getReputation(user1.address);
            expect(score).to.equal(STARTING_REPUTATION - 100n);
        });

        it("should emit UserFlaggedEvent", async function () {
            await expect(reputation.connect(verifier).flagUser(user1.address, "Test"))
                .to.emit(reputation, "UserFlaggedEvent")
                .withArgs(user1.address, "Test");
        });

        it("should prevent reputation gains when flagged", async function () {
            await reputation.connect(verifier).flagUser(user1.address, "Test");

            await expect(reputation.connect(reporter).recordSuccessfulTrade(user1.address, SMALL_TRADE))
                .to.be.revertedWithCustomError(reputation, "UserFlagged");
        });

        it("should allow unflagging", async function () {
            await reputation.connect(verifier).flagUser(user1.address, "Test");
            await reputation.connect(verifier).unflagUser(user1.address);

            const userData = await reputation.getUserReputation(user1.address);
            expect(userData.isFlagged).to.be.false;
        });

        it("should emit UserUnflagged event", async function () {
            await reputation.connect(verifier).flagUser(user1.address, "Test");

            await expect(reputation.connect(verifier).unflagUser(user1.address))
                .to.emit(reputation, "UserUnflagged")
                .withArgs(user1.address);
        });
    });

    // ============ Priority Comparison Tests ============

    describe("Priority Comparison", function () {
        beforeEach(async function () {
            await reputation.registerUser(user1.address);
            await reputation.registerUser(user2.address);
        });

        it("should compare users for priority", async function () {
            // Equal scores - user1 wins (first in)
            let winner = await reputation.compareForPriority(user1.address, user2.address);
            expect(winner).to.equal(user1.address);

            // Boost user2
            await reputation.connect(admin).adminAdjustReputation(user2.address, 100, "Test");

            winner = await reputation.compareForPriority(user1.address, user2.address);
            expect(winner).to.equal(user2.address);
        });

        it("should handle unregistered users", async function () {
            const winner = await reputation.compareForPriority(user1.address, user3.address);
            expect(winner).to.equal(user1.address); // Registered user wins
        });
    });

    // ============ Leaderboard Tests ============

    describe("Leaderboard", function () {
        beforeEach(async function () {
            await reputation.registerUser(user1.address);
            await reputation.registerUser(user2.address);
            await reputation.registerUser(user3.address);

            // Give different scores
            await reputation.connect(admin).adminAdjustReputation(user1.address, 100, "Test");
            await reputation.connect(admin).adminAdjustReputation(user2.address, 200, "Test");
            await reputation.connect(admin).adminAdjustReputation(user3.address, -100, "Test");
        });

        it("should return top users sorted by score", async function () {
            const leaderboard = await reputation.getLeaderboard(3);

            expect(leaderboard[0].user).to.equal(user2.address); // 700
            expect(leaderboard[1].user).to.equal(user1.address); // 600
            expect(leaderboard[2].user).to.equal(user3.address); // 400
        });

        it("should limit results to count parameter", async function () {
            const leaderboard = await reputation.getLeaderboard(2);
            expect(leaderboard.length).to.equal(2);
        });

        it("should include tier information", async function () {
            const leaderboard = await reputation.getLeaderboard(3);

            expect(leaderboard[0].tier).to.equal(Tier.Gold);   // 700
            expect(leaderboard[1].tier).to.equal(Tier.Gold);   // 600
            expect(leaderboard[2].tier).to.equal(Tier.Silver); // 400
        });
    });

    // ============ View Functions Tests ============

    describe("View Functions", function () {
        beforeEach(async function () {
            await reputation.registerUser(user1.address);
        });

        it("should return reputation history", async function () {
            await reputation.connect(admin).adminAdjustReputation(user1.address, 50, "Boost");

            const history = await reputation.getReputationHistory(user1.address);
            expect(history.length).to.equal(2); // Initial + boost
        });

        it("should return registered users count", async function () {
            expect(await reputation.getRegisteredUsersCount()).to.equal(1);

            await reputation.registerUser(user2.address);
            expect(await reputation.getRegisteredUsersCount()).to.equal(2);
        });

        it("should return user by index", async function () {
            expect(await reputation.getRegisteredUser(0)).to.equal(user1.address);
        });

        it("should return system stats", async function () {
            await reputation.connect(admin).adminAdjustReputation(user1.address, 50, "Boost");

            const [users, distributed, deducted] = await reputation.getSystemStats();
            expect(users).to.equal(1);
            expect(distributed).to.be.gt(0);
        });

        it("should return tier distribution", async function () {
            await reputation.registerUser(user2.address);

            // Move user1 to Gold
            await reputation.connect(admin).adminAdjustReputation(user1.address, 150, "Test");

            const [bronze, silver, gold, platinum, diamond] = await reputation.getTierDistribution();
            expect(silver).to.equal(1); // user2
            expect(gold).to.equal(1);   // user1
        });

        it("should return time since last activity", async function () {
            await time.increase(100);
            const timeSince = await reputation.getTimeSinceLastActivity(user1.address);
            expect(timeSince).to.be.gte(100);
        });

        it("should return defaults for unregistered users", async function () {
            const [score, tier] = await reputation.getReputation(other.address);
            expect(score).to.equal(0);
            expect(tier).to.equal(Tier.Bronze);

            expect(await reputation.getEffectiveFeeRate(other.address)).to.equal(250);
            expect(await reputation.getGovernanceMultiplier(other.address)).to.equal(100);
        });
    });

    // ============ Admin Functions Tests ============

    describe("Admin Functions", function () {
        beforeEach(async function () {
            await reputation.registerUser(user1.address);
        });

        it("should allow admin adjustment", async function () {
            await reputation.connect(admin).adminAdjustReputation(user1.address, 100, "Manual boost");

            const [score] = await reputation.getReputation(user1.address);
            expect(score).to.equal(STARTING_REPUTATION + 100n);
        });

        it("should update tier benefits", async function () {
            await reputation.connect(admin).updateTierBenefits(
                Tier.Gold,
                120, // 1.2% fee
                ethers.parseEther("300"),
                130  // 1.3x governance
            );

            const benefits = await reputation.getTierBenefits(Tier.Gold);
            expect(benefits.feeRate).to.equal(120);
            expect(benefits.transactionLimit).to.equal(ethers.parseEther("300"));
            expect(benefits.governanceMultiplier).to.equal(130);
        });

        it("should emit TierBenefitsUpdated event", async function () {
            await expect(reputation.connect(admin).updateTierBenefits(
                Tier.Gold,
                120,
                ethers.parseEther("300"),
                130
            ))
                .to.emit(reputation, "TierBenefitsUpdated");
        });

        it("should revert invalid fee rate (>5%)", async function () {
            await expect(reputation.connect(admin).updateTierBenefits(
                Tier.Gold,
                600, // 6%
                ethers.parseEther("300"),
                100
            )).to.be.revertedWithCustomError(reputation, "InvalidMultiplier");
        });

        it("should revert invalid governance multiplier (>3x)", async function () {
            await expect(reputation.connect(admin).updateTierBenefits(
                Tier.Gold,
                100,
                ethers.parseEther("300"),
                400 // 4x
            )).to.be.revertedWithCustomError(reputation, "InvalidMultiplier");
        });

        it("should set staking contract", async function () {
            await reputation.connect(admin).setStakingContract(other.address);
            expect(await reputation.stakingContract()).to.equal(other.address);
        });

        it("should set KYC registry", async function () {
            await reputation.connect(admin).setKYCRegistry(other.address);
            expect(await reputation.kycRegistry()).to.equal(other.address);
        });

        it("should grant and revoke reporter role", async function () {
            await reputation.connect(admin).grantReporterRole(other.address);
            expect(await reputation.hasRole(await reputation.REPORTER_ROLE(), other.address)).to.be.true;

            await reputation.connect(admin).revokeReporterRole(other.address);
            expect(await reputation.hasRole(await reputation.REPORTER_ROLE(), other.address)).to.be.false;
        });

        it("should pause and unpause", async function () {
            await reputation.connect(admin).pause();
            expect(await reputation.paused()).to.be.true;

            await expect(reputation.registerUser(user2.address))
                .to.be.reverted;

            await reputation.connect(admin).unpause();
            expect(await reputation.paused()).to.be.false;
        });
    });

    // ============ Integration Tests ============

    describe("Integration", function () {
        it("should handle complete reputation lifecycle", async function () {
            // 1. Register user
            await reputation.registerUser(user1.address);
            let [score, tier] = await reputation.getReputation(user1.address);
            expect(score).to.equal(STARTING_REPUTATION);
            expect(tier).to.equal(Tier.Silver);

            // 2. KYC verify
            await reputation.connect(verifier).updateKYCStatus(user1.address, true);

            // 3. Stake tokens
            await reputation.connect(reporter).updateStake(user1.address, MIN_STAKE);

            // 4. Successful trades (with KYC bonus)
            for (let i = 0; i < 20; i++) {
                await reputation.connect(reporter).recordSuccessfulTrade(user1.address, LARGE_TRADE);
            }

            // Should be at Gold or Platinum now
            [score, tier] = await reputation.getReputation(user1.address);
            expect(score).to.be.gt(GOLD_MAX);

            // 5. Check benefits
            expect(await reputation.hasPriorityMatching(user1.address)).to.be.true;
            expect(await reputation.getEffectiveFeeRate(user1.address)).to.be.lt(150); // Less than Gold fee
        });

        it("should handle reputation crash and recovery", async function () {
            await reputation.registerUser(user1.address);
            await reputation.connect(reporter).updateStake(user1.address, MIN_STAKE);

            // Build up reputation
            await reputation.connect(admin).adminAdjustReputation(user1.address, 300, "Initial boost");

            let [score, tier] = await reputation.getReputation(user1.address);
            expect(tier).to.equal(Tier.Platinum);

            // Multiple failures
            for (let i = 0; i < 10; i++) {
                await reputation.connect(reporter).recordFailedDelivery(user1.address);
            }

            [score, tier] = await reputation.getReputation(user1.address);
            expect(score).to.equal(300n); // 800 - 500 = 300
            expect(tier).to.equal(Tier.Bronze);

            // Recovery through successful trades
            for (let i = 0; i < 50; i++) {
                await reputation.connect(reporter).recordSuccessfulTrade(user1.address, SMALL_TRADE);
            }

            [score] = await reputation.getReputation(user1.address);
            expect(score).to.be.gt(500n);
        });

        it("should integrate with auction priority", async function () {
            await reputation.registerUser(user1.address);
            await reputation.registerUser(user2.address);

            // Same starting reputation - first user wins ties
            let winner = await reputation.compareForPriority(user1.address, user2.address);
            expect(winner).to.equal(user1.address);

            // Boost user2's reputation
            await reputation.connect(admin).adminAdjustReputation(user2.address, 100, "Boost");

            // Now user2 should win
            winner = await reputation.compareForPriority(user1.address, user2.address);
            expect(winner).to.equal(user2.address);
        });
    });
});
