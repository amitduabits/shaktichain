import { expect } from "chai";
import { ethers } from "hardhat";
import { time } from "@nomicfoundation/hardhat-network-helpers";
import { HardhatEthersSigner } from "@nomicfoundation/hardhat-ethers/signers";
import { Treasury, ShaktiToken } from "../typechain-types";

describe("Treasury", function () {
    let treasury: Treasury;
    let token: ShaktiToken;

    let admin: HardhatEthersSigner;
    let escrow: HardhatEthersSigner;
    let stakingPool: HardhatEthersSigner;
    let governance: HardhatEthersSigner;
    let signer1: HardhatEthersSigner;
    let signer2: HardhatEthersSigner;
    let signer3: HardhatEthersSigner;
    let signer4: HardhatEthersSigner;
    let signer5: HardhatEthersSigner;
    let grantRecipient: HardhatEthersSigner;
    let devRecipient: HardhatEthersSigner;
    let donor: HardhatEthersSigner;

    const INITIAL_SUPPLY = ethers.parseEther("100000000"); // 100M tokens
    const FEE_AMOUNT = ethers.parseEther("10000"); // 10,000 SHAKTI
    const LARGE_AMOUNT = ethers.parseEther("200000"); // 200,000 SHAKTI (triggers timelock)
    const SMALL_AMOUNT = ethers.parseEther("50000"); // 50,000 SHAKTI

    const BASIS_POINTS = 10000n;
    const STAKING_SHARE = 5000n;
    const DEVELOPMENT_SHARE = 3000n;
    const GRANTS_SHARE = 2000n;

    const DISTRIBUTION_INTERVAL = 7 * 24 * 60 * 60; // 7 days
    const TIMELOCK_DURATION = 48 * 60 * 60; // 48 hours
    const TIMELOCK_THRESHOLD = ethers.parseEther("100000"); // 100k SHAKTI

    beforeEach(async function () {
        [
            admin,
            escrow,
            stakingPool,
            governance,
            signer1,
            signer2,
            signer3,
            signer4,
            signer5,
            grantRecipient,
            devRecipient,
            donor
        ] = await ethers.getSigners();

        // Deploy ShaktiToken
        const ShaktiToken = await ethers.getContractFactory("ShaktiToken");
        token = await ShaktiToken.deploy(admin.address, admin.address);
        await token.waitForDeployment();

        // Deploy Treasury with 5 signers
        const signers = [
            signer1.address,
            signer2.address,
            signer3.address,
            signer4.address,
            signer5.address
        ];

        const Treasury = await ethers.getContractFactory("Treasury");
        treasury = await Treasury.deploy(
            await token.getAddress(),
            admin.address,
            signers
        );
        await treasury.waitForDeployment();

        // Setup roles
        await treasury.connect(admin).authorizeEscrow(escrow.address);
        await treasury.connect(admin).setStakingPool(stakingPool.address);
        await treasury.connect(admin).grantRole(await treasury.GOVERNANCE_ROLE(), governance.address);

        // Fund accounts for testing
        await token.connect(admin).transfer(escrow.address, ethers.parseEther("1000000"));
        await token.connect(admin).transfer(donor.address, ethers.parseEther("100000"));

        // Approve treasury
        await token.connect(escrow).approve(await treasury.getAddress(), ethers.MaxUint256);
        await token.connect(donor).approve(await treasury.getAddress(), ethers.MaxUint256);
        await token.connect(admin).approve(await treasury.getAddress(), ethers.MaxUint256);
    });

    // ============ Deployment Tests ============

    describe("Deployment", function () {
        it("should deploy with correct parameters", async function () {
            expect(await treasury.shaktiToken()).to.equal(await token.getAddress());
            expect(await treasury.stakingPool()).to.equal(stakingPool.address);
        });

        it("should initialize 5 signers", async function () {
            const signers = await treasury.getSigners();
            expect(signers.length).to.equal(5);
            expect(await treasury.isSigner(signer1.address)).to.be.true;
            expect(await treasury.isSigner(signer5.address)).to.be.true;
        });

        it("should revert if token is zero address", async function () {
            const Treasury = await ethers.getContractFactory("Treasury");
            const signers = [signer1.address, signer2.address, signer3.address, signer4.address, signer5.address];

            await expect(Treasury.deploy(ethers.ZeroAddress, admin.address, signers))
                .to.be.revertedWithCustomError(treasury, "ZeroAddress");
        });

        it("should revert if not 5 signers", async function () {
            const Treasury = await ethers.getContractFactory("Treasury");
            const signers = [signer1.address, signer2.address, signer3.address];

            await expect(Treasury.deploy(await token.getAddress(), admin.address, signers))
                .to.be.revertedWithCustomError(treasury, "InvalidSignerCount");
        });

        it("should revert if duplicate signers", async function () {
            const Treasury = await ethers.getContractFactory("Treasury");
            const signers = [signer1.address, signer1.address, signer3.address, signer4.address, signer5.address];

            await expect(Treasury.deploy(await token.getAddress(), admin.address, signers))
                .to.be.revertedWithCustomError(treasury, "SignerAlreadyExists");
        });
    });

    // ============ Fee Reception Tests ============

    describe("Fee Reception", function () {
        it("should receive fees and allocate correctly", async function () {
            await treasury.connect(escrow).receiveFees(FEE_AMOUNT);

            const allocations = await treasury.getAllocations();
            const expectedStaking = (FEE_AMOUNT * STAKING_SHARE) / BASIS_POINTS;
            const expectedDev = (FEE_AMOUNT * DEVELOPMENT_SHARE) / BASIS_POINTS;
            const expectedGrants = FEE_AMOUNT - expectedStaking - expectedDev;

            expect(allocations.staking).to.equal(expectedStaking);
            expect(allocations.development).to.equal(expectedDev);
            expect(allocations.communityGrants).to.equal(expectedGrants);
        });

        it("should emit FeeReceived event", async function () {
            const expectedStaking = (FEE_AMOUNT * STAKING_SHARE) / BASIS_POINTS;
            const expectedDev = (FEE_AMOUNT * DEVELOPMENT_SHARE) / BASIS_POINTS;
            const expectedGrants = FEE_AMOUNT - expectedStaking - expectedDev;

            await expect(treasury.connect(escrow).receiveFees(FEE_AMOUNT))
                .to.emit(treasury, "FeeReceived")
                .withArgs(FEE_AMOUNT, expectedStaking, expectedDev, expectedGrants);
        });

        it("should track total fees received", async function () {
            await treasury.connect(escrow).receiveFees(FEE_AMOUNT);
            await treasury.connect(escrow).receiveFees(FEE_AMOUNT);

            const inflows = await treasury.getTotalInflows();
            expect(inflows.fees).to.equal(FEE_AMOUNT * 2n);
        });

        it("should record in inflow history", async function () {
            await treasury.connect(escrow).receiveFees(FEE_AMOUNT);

            expect(await treasury.getInflowHistoryLength()).to.equal(1);
            const entry = await treasury.getInflowEntry(0);
            expect(entry.source).to.equal(0); // PlatformFees
            expect(entry.amount).to.equal(FEE_AMOUNT);
        });

        it("should revert if caller is not escrow", async function () {
            await expect(treasury.connect(donor).receiveFees(FEE_AMOUNT))
                .to.be.reverted;
        });

        it("should revert for zero amount", async function () {
            await expect(treasury.connect(escrow).receiveFees(0))
                .to.be.revertedWithCustomError(treasury, "ZeroAmount");
        });
    });

    // ============ Donation Tests ============

    describe("Donations", function () {
        it("should accept donations", async function () {
            const donationAmount = ethers.parseEther("1000");
            await treasury.connect(donor).receiveDonation(donationAmount);

            const allocations = await treasury.getAllocations();
            expect(allocations.communityGrants).to.equal(donationAmount);
        });

        it("should emit DonationReceived event", async function () {
            const donationAmount = ethers.parseEther("1000");

            await expect(treasury.connect(donor).receiveDonation(donationAmount))
                .to.emit(treasury, "DonationReceived")
                .withArgs(donor.address, donationAmount);
        });

        it("should track total donations", async function () {
            const donationAmount = ethers.parseEther("1000");
            await treasury.connect(donor).receiveDonation(donationAmount);

            const inflows = await treasury.getTotalInflows();
            expect(inflows.donations).to.equal(donationAmount);
        });
    });

    // ============ Staking Rewards Distribution Tests ============

    describe("Staking Rewards Distribution", function () {
        beforeEach(async function () {
            // Add fees to create staking allocation
            await treasury.connect(escrow).receiveFees(FEE_AMOUNT);
        });

        it("should distribute rewards to staking pool", async function () {
            const stakingAllocation = (await treasury.getAllocations()).staking;

            // Fast forward 7 days
            await time.increase(DISTRIBUTION_INTERVAL + 1);

            const balanceBefore = await token.balanceOf(stakingPool.address);
            await treasury.distributeRewards();
            const balanceAfter = await token.balanceOf(stakingPool.address);

            expect(balanceAfter - balanceBefore).to.equal(stakingAllocation);
        });

        it("should emit RewardsDistributed event", async function () {
            const stakingAllocation = (await treasury.getAllocations()).staking;
            await time.increase(DISTRIBUTION_INTERVAL + 1);

            await expect(treasury.distributeRewards())
                .to.emit(treasury, "RewardsDistributed")
                .withArgs(stakingAllocation, await time.latest() + 1);
        });

        it("should reset staking allocation after distribution", async function () {
            await time.increase(DISTRIBUTION_INTERVAL + 1);
            await treasury.distributeRewards();

            const allocations = await treasury.getAllocations();
            expect(allocations.staking).to.equal(0);
        });

        it("should track total distributed", async function () {
            const stakingAllocation = (await treasury.getAllocations()).staking;
            await time.increase(DISTRIBUTION_INTERVAL + 1);
            await treasury.distributeRewards();

            expect(await treasury.totalDistributed()).to.equal(stakingAllocation);
        });

        it("should revert if distribution too soon", async function () {
            await time.increase(DISTRIBUTION_INTERVAL + 1);
            await treasury.distributeRewards();

            // Try again immediately
            await treasury.connect(escrow).receiveFees(FEE_AMOUNT);

            await expect(treasury.distributeRewards())
                .to.be.revertedWithCustomError(treasury, "DistributionTooSoon");
        });

        it("should revert if no staking allocation", async function () {
            await time.increase(DISTRIBUTION_INTERVAL + 1);
            await treasury.distributeRewards();

            await time.increase(DISTRIBUTION_INTERVAL + 1);

            await expect(treasury.distributeRewards())
                .to.be.revertedWithCustomError(treasury, "ZeroAmount");
        });

        it("should return correct time until next distribution", async function () {
            const timeRemaining = await treasury.timeUntilNextDistribution();
            expect(timeRemaining).to.be.closeTo(BigInt(DISTRIBUTION_INTERVAL), 10n);

            await time.increase(DISTRIBUTION_INTERVAL + 1);
            expect(await treasury.timeUntilNextDistribution()).to.equal(0);
        });
    });

    // ============ Community Grants Tests ============

    describe("Community Grants", function () {
        beforeEach(async function () {
            // Add fees to create grants allocation
            await treasury.connect(escrow).receiveFees(FEE_AMOUNT);
        });

        it("should allocate a grant", async function () {
            const grantAmount = ethers.parseEther("1000");
            const grantsAllocationBefore = (await treasury.getAllocations()).communityGrants;

            await treasury.connect(governance).allocateGrant(
                grantRecipient.address,
                grantAmount,
                "Community development"
            );

            const grant = await treasury.getGrant(0);
            expect(grant.recipient).to.equal(grantRecipient.address);
            expect(grant.amount).to.equal(grantAmount);
            expect(grant.purpose).to.equal("Community development");
            expect(grant.executed).to.be.false;

            const grantsAllocationAfter = (await treasury.getAllocations()).communityGrants;
            expect(grantsAllocationBefore - grantsAllocationAfter).to.equal(grantAmount);
        });

        it("should emit GrantAllocated event", async function () {
            const grantAmount = ethers.parseEther("1000");

            await expect(treasury.connect(governance).allocateGrant(
                grantRecipient.address,
                grantAmount,
                "Test grant"
            ))
                .to.emit(treasury, "GrantAllocated")
                .withArgs(0, grantRecipient.address, grantAmount, "Test grant");
        });

        it("should execute a grant", async function () {
            const grantAmount = ethers.parseEther("1000");
            await treasury.connect(governance).allocateGrant(
                grantRecipient.address,
                grantAmount,
                "Test grant"
            );

            const balanceBefore = await token.balanceOf(grantRecipient.address);
            await treasury.executeGrant(0);
            const balanceAfter = await token.balanceOf(grantRecipient.address);

            expect(balanceAfter - balanceBefore).to.equal(grantAmount);

            const grant = await treasury.getGrant(0);
            expect(grant.executed).to.be.true;
        });

        it("should emit GrantExecuted event", async function () {
            const grantAmount = ethers.parseEther("1000");
            await treasury.connect(governance).allocateGrant(
                grantRecipient.address,
                grantAmount,
                "Test grant"
            );

            await expect(treasury.executeGrant(0))
                .to.emit(treasury, "GrantExecuted")
                .withArgs(0, grantRecipient.address, grantAmount);
        });

        it("should revert if grant exceeds allocation", async function () {
            const excessiveAmount = ethers.parseEther("1000000");

            await expect(treasury.connect(governance).allocateGrant(
                grantRecipient.address,
                excessiveAmount,
                "Too much"
            ))
                .to.be.revertedWithCustomError(treasury, "GrantExceedsAllocation");
        });

        it("should revert if non-governance allocates grant", async function () {
            await expect(treasury.connect(donor).allocateGrant(
                grantRecipient.address,
                1000,
                "Unauthorized"
            ))
                .to.be.reverted;
        });

        it("should revert if executing already executed grant", async function () {
            const grantAmount = ethers.parseEther("1000");
            await treasury.connect(governance).allocateGrant(
                grantRecipient.address,
                grantAmount,
                "Test grant"
            );
            await treasury.executeGrant(0);

            await expect(treasury.executeGrant(0))
                .to.be.revertedWithCustomError(treasury, "WithdrawalAlreadyExecuted");
        });

        it("should track all grant IDs", async function () {
            await treasury.connect(governance).allocateGrant(grantRecipient.address, 1000, "Grant 1");
            await treasury.connect(governance).allocateGrant(grantRecipient.address, 2000, "Grant 2");

            const grantIds = await treasury.getAllGrantIds();
            expect(grantIds.length).to.equal(2);
            expect(grantIds[0]).to.equal(0);
            expect(grantIds[1]).to.equal(1);
        });
    });

    // ============ Multisig Withdrawal Tests ============

    describe("Multisig Withdrawals", function () {
        beforeEach(async function () {
            // Add fees to create sufficient development allocation
            // Development gets 30%, so we need at least 50000/0.3 = ~167,000 for SMALL_AMOUNT
            await treasury.connect(escrow).receiveFees(ethers.parseEther("200000"));
        });

        describe("Small Withdrawals (No Timelock)", function () {
            it("should propose a withdrawal", async function () {
                await treasury.connect(signer1).proposeWithdrawal(
                    devRecipient.address,
                    SMALL_AMOUNT,
                    "Development expense"
                );

                const info = await treasury.getWithdrawalInfo(0);
                expect(info.to).to.equal(devRecipient.address);
                expect(info.amount).to.equal(SMALL_AMOUNT);
                expect(info.signatureCount).to.equal(1); // Proposer signs automatically
                expect(info.status).to.equal(0); // Pending
            });

            it("should allow signers to sign", async function () {
                await treasury.connect(signer1).proposeWithdrawal(
                    devRecipient.address,
                    SMALL_AMOUNT,
                    "Development expense"
                );

                await treasury.connect(signer2).signWithdrawal(0);
                await treasury.connect(signer3).signWithdrawal(0);

                const info = await treasury.getWithdrawalInfo(0);
                expect(info.signatureCount).to.equal(3);
            });

            it("should emit WithdrawalSigned event", async function () {
                await treasury.connect(signer1).proposeWithdrawal(
                    devRecipient.address,
                    SMALL_AMOUNT,
                    "Test"
                );

                await expect(treasury.connect(signer2).signWithdrawal(0))
                    .to.emit(treasury, "WithdrawalSigned")
                    .withArgs(0, signer2.address, 2);
            });

            it("should execute with 3 signatures", async function () {
                await treasury.connect(signer1).proposeWithdrawal(
                    devRecipient.address,
                    SMALL_AMOUNT,
                    "Development expense"
                );

                await treasury.connect(signer2).signWithdrawal(0);
                await treasury.connect(signer3).signWithdrawal(0);

                const balanceBefore = await token.balanceOf(devRecipient.address);
                await treasury.executeWithdrawal(0);
                const balanceAfter = await token.balanceOf(devRecipient.address);

                expect(balanceAfter - balanceBefore).to.equal(SMALL_AMOUNT);
            });

            it("should revert with insufficient signatures", async function () {
                await treasury.connect(signer1).proposeWithdrawal(
                    devRecipient.address,
                    SMALL_AMOUNT,
                    "Test"
                );

                await treasury.connect(signer2).signWithdrawal(0);
                // Only 2 signatures

                await expect(treasury.executeWithdrawal(0))
                    .to.be.revertedWithCustomError(treasury, "InsufficientSignatures");
            });

            it("should revert if signer signs twice", async function () {
                await treasury.connect(signer1).proposeWithdrawal(
                    devRecipient.address,
                    SMALL_AMOUNT,
                    "Test"
                );

                await expect(treasury.connect(signer1).signWithdrawal(0))
                    .to.be.revertedWithCustomError(treasury, "AlreadySigned");
            });

            it("should revert if non-signer proposes", async function () {
                await expect(treasury.connect(donor).proposeWithdrawal(
                    devRecipient.address,
                    SMALL_AMOUNT,
                    "Unauthorized"
                ))
                    .to.be.revertedWithCustomError(treasury, "NotSigner");
            });
        });

        describe("Large Withdrawals (With Timelock)", function () {
            beforeEach(async function () {
                // Need more development allocation for large withdrawal (200k)
                // Development gets 30%, so need at least 200000/0.3 = ~667,000 more
                await treasury.connect(escrow).receiveFees(ethers.parseEther("700000"));
            });

            it("should set unlock time for large withdrawals", async function () {
                await treasury.connect(signer1).proposeWithdrawal(
                    devRecipient.address,
                    LARGE_AMOUNT,
                    "Large development expense"
                );

                const info = await treasury.getWithdrawalInfo(0);
                const now = await time.latest();

                expect(info.unlockTime).to.be.closeTo(BigInt(now + TIMELOCK_DURATION), 10n);
            });

            it("should revert if timelock not expired", async function () {
                await treasury.connect(signer1).proposeWithdrawal(
                    devRecipient.address,
                    LARGE_AMOUNT,
                    "Large expense"
                );

                await treasury.connect(signer2).signWithdrawal(0);
                await treasury.connect(signer3).signWithdrawal(0);

                await expect(treasury.executeWithdrawal(0))
                    .to.be.revertedWithCustomError(treasury, "TimelockNotExpired");
            });

            it("should execute after timelock expires", async function () {
                await treasury.connect(signer1).proposeWithdrawal(
                    devRecipient.address,
                    LARGE_AMOUNT,
                    "Large expense"
                );

                await treasury.connect(signer2).signWithdrawal(0);
                await treasury.connect(signer3).signWithdrawal(0);

                // Fast forward 48 hours
                await time.increase(TIMELOCK_DURATION + 1);

                const balanceBefore = await token.balanceOf(devRecipient.address);
                await treasury.executeWithdrawal(0);
                const balanceAfter = await token.balanceOf(devRecipient.address);

                expect(balanceAfter - balanceBefore).to.equal(LARGE_AMOUNT);
            });
        });

        describe("Withdrawal Cancellation", function () {
            it("should cancel a pending withdrawal", async function () {
                await treasury.connect(signer1).proposeWithdrawal(
                    devRecipient.address,
                    SMALL_AMOUNT,
                    "Test"
                );

                await treasury.connect(signer2).cancelWithdrawal(0);

                const info = await treasury.getWithdrawalInfo(0);
                expect(info.status).to.equal(2); // Cancelled
            });

            it("should emit WithdrawalCancelled event", async function () {
                await treasury.connect(signer1).proposeWithdrawal(
                    devRecipient.address,
                    SMALL_AMOUNT,
                    "Test"
                );

                await expect(treasury.connect(signer2).cancelWithdrawal(0))
                    .to.emit(treasury, "WithdrawalCancelled")
                    .withArgs(0);
            });

            it("should revert executing cancelled withdrawal", async function () {
                await treasury.connect(signer1).proposeWithdrawal(
                    devRecipient.address,
                    SMALL_AMOUNT,
                    "Test"
                );

                await treasury.connect(signer2).cancelWithdrawal(0);

                await expect(treasury.executeWithdrawal(0))
                    .to.be.revertedWithCustomError(treasury, "WithdrawalWasCancelled");
            });

            it("should revert if non-signer cancels", async function () {
                await treasury.connect(signer1).proposeWithdrawal(
                    devRecipient.address,
                    SMALL_AMOUNT,
                    "Test"
                );

                await expect(treasury.connect(donor).cancelWithdrawal(0))
                    .to.be.revertedWithCustomError(treasury, "NotSigner");
            });
        });
    });

    // ============ Signer Management Tests ============

    describe("Signer Management", function () {
        it("should replace a signer", async function () {
            const newSigner = donor.address;

            await treasury.connect(governance).replaceSigner(signer5.address, newSigner);

            expect(await treasury.isSigner(signer5.address)).to.be.false;
            expect(await treasury.isSigner(newSigner)).to.be.true;
        });

        it("should emit SignerRemoved and SignerAdded events", async function () {
            const newSigner = donor.address;

            await expect(treasury.connect(governance).replaceSigner(signer5.address, newSigner))
                .to.emit(treasury, "SignerRemoved")
                .withArgs(signer5.address)
                .and.to.emit(treasury, "SignerAdded")
                .withArgs(newSigner);
        });

        it("should revert if old signer doesn't exist", async function () {
            await expect(treasury.connect(governance).replaceSigner(donor.address, admin.address))
                .to.be.revertedWithCustomError(treasury, "SignerDoesNotExist");
        });

        it("should revert if new signer already exists", async function () {
            await expect(treasury.connect(governance).replaceSigner(signer5.address, signer1.address))
                .to.be.revertedWithCustomError(treasury, "SignerAlreadyExists");
        });

        it("should revert if non-governance replaces signer", async function () {
            await expect(treasury.connect(signer1).replaceSigner(signer5.address, donor.address))
                .to.be.reverted;
        });
    });

    // ============ Monthly Snapshots Tests ============

    describe("Monthly Snapshots", function () {
        beforeEach(async function () {
            await treasury.connect(escrow).receiveFees(FEE_AMOUNT);
        });

        it("should record monthly snapshot", async function () {
            await treasury.connect(admin).recordMonthlySnapshot(202412);

            const snapshot = await treasury.getMonthlySnapshot(202412);
            expect(snapshot.month).to.equal(202412);
            expect(snapshot.totalInflows).to.equal(FEE_AMOUNT);
        });

        it("should emit MonthlySnapshotRecorded event", async function () {
            await expect(treasury.connect(admin).recordMonthlySnapshot(202412))
                .to.emit(treasury, "MonthlySnapshotRecorded")
                .withArgs(202412, FEE_AMOUNT, 0);
        });

        it("should track snapshot months", async function () {
            await treasury.connect(admin).recordMonthlySnapshot(202411);
            await treasury.connect(admin).recordMonthlySnapshot(202412);

            const months = await treasury.getSnapshotMonths();
            expect(months.length).to.equal(2);
            expect(months[0]).to.equal(202411);
            expect(months[1]).to.equal(202412);
        });

        it("should revert for invalid month", async function () {
            await expect(treasury.connect(admin).recordMonthlySnapshot(202300))
                .to.be.revertedWithCustomError(treasury, "InvalidMonth");
        });
    });

    // ============ Accounting Tests ============

    describe("Accounting", function () {
        it("should track inflows by source", async function () {
            await treasury.connect(escrow).receiveFees(FEE_AMOUNT);
            await treasury.connect(donor).receiveDonation(ethers.parseEther("500"));

            const inflows = await treasury.getTotalInflows();
            expect(inflows.fees).to.equal(FEE_AMOUNT);
            expect(inflows.donations).to.equal(ethers.parseEther("500"));
        });

        it("should track outflows by category", async function () {
            await treasury.connect(escrow).receiveFees(FEE_AMOUNT);

            // Distribute staking rewards
            await time.increase(DISTRIBUTION_INTERVAL + 1);
            const stakingAmount = (await treasury.getAllocations()).staking;
            await treasury.distributeRewards();

            // Execute a grant
            const grantAmount = ethers.parseEther("100");
            await treasury.connect(governance).allocateGrant(grantRecipient.address, grantAmount, "Test");
            await treasury.executeGrant(0);

            const outflows = await treasury.getTotalOutflows();
            expect(outflows.staking).to.equal(stakingAmount);
            expect(outflows.communityGrants).to.equal(grantAmount);
        });

        it("should record outflow history", async function () {
            await treasury.connect(escrow).receiveFees(FEE_AMOUNT);
            await time.increase(DISTRIBUTION_INTERVAL + 1);
            await treasury.distributeRewards();

            expect(await treasury.getOutflowHistoryLength()).to.equal(1);
            const entry = await treasury.getOutflowEntry(0);
            expect(entry.category).to.equal(0); // StakingRewards
            expect(entry.recipient).to.equal(stakingPool.address);
        });
    });

    // ============ View Functions Tests ============

    describe("View Functions", function () {
        beforeEach(async function () {
            await treasury.connect(escrow).receiveFees(FEE_AMOUNT);
        });

        it("should return treasury stats", async function () {
            const stats = await treasury.getTreasuryStats();
            expect(stats.balance).to.equal(FEE_AMOUNT);
            expect(stats.signerCount).to.equal(5);
        });

        it("should check if signer has signed", async function () {
            await treasury.connect(signer1).proposeWithdrawal(devRecipient.address, 1000, "Test");

            expect(await treasury.hasSignedWithdrawal(0, signer1.address)).to.be.true;
            expect(await treasury.hasSignedWithdrawal(0, signer2.address)).to.be.false;
        });
    });

    // ============ Admin Functions Tests ============

    describe("Admin Functions", function () {
        it("should update staking pool", async function () {
            const newPool = donor.address;

            await expect(treasury.connect(admin).setStakingPool(newPool))
                .to.emit(treasury, "StakingPoolUpdated")
                .withArgs(stakingPool.address, newPool);

            expect(await treasury.stakingPool()).to.equal(newPool);
        });

        it("should authorize and revoke escrow", async function () {
            const newEscrow = donor.address;

            await treasury.connect(admin).authorizeEscrow(newEscrow);
            expect(await treasury.hasRole(await treasury.ESCROW_ROLE(), newEscrow)).to.be.true;

            await treasury.connect(admin).revokeEscrow(newEscrow);
            expect(await treasury.hasRole(await treasury.ESCROW_ROLE(), newEscrow)).to.be.false;
        });

        it("should pause and unpause", async function () {
            await treasury.connect(admin).pause();
            expect(await treasury.paused()).to.be.true;

            await expect(treasury.connect(escrow).receiveFees(FEE_AMOUNT))
                .to.be.revertedWithCustomError(treasury, "EnforcedPause");

            await treasury.connect(admin).unpause();
            expect(await treasury.paused()).to.be.false;
        });
    });

    // ============ Emergency Withdrawal Tests ============

    describe("Emergency Withdrawal", function () {
        beforeEach(async function () {
            await treasury.connect(escrow).receiveFees(FEE_AMOUNT);
        });

        it("should allow emergency withdrawal by admin", async function () {
            const withdrawAmount = ethers.parseEther("5000");

            const balanceBefore = await token.balanceOf(admin.address);
            await treasury.connect(admin).emergencyWithdraw(admin.address, withdrawAmount);
            const balanceAfter = await token.balanceOf(admin.address);

            expect(balanceAfter - balanceBefore).to.equal(withdrawAmount);
        });

        it("should record emergency outflow", async function () {
            await treasury.connect(admin).emergencyWithdraw(admin.address, 1000);

            const length = await treasury.getOutflowHistoryLength();
            const entry = await treasury.getOutflowEntry(length - 1n);
            expect(entry.category).to.equal(3); // Emergency
        });

        it("should revert if insufficient balance", async function () {
            const excessiveAmount = ethers.parseEther("1000000");

            await expect(treasury.connect(admin).emergencyWithdraw(admin.address, excessiveAmount))
                .to.be.revertedWithCustomError(treasury, "InsufficientBalance");
        });

        it("should revert if non-admin calls", async function () {
            await expect(treasury.connect(signer1).emergencyWithdraw(signer1.address, 1000))
                .to.be.reverted;
        });
    });

    // ============ Integration Tests ============

    describe("Integration", function () {
        it("should handle complete fee flow", async function () {
            // 1. Receive fees
            await treasury.connect(escrow).receiveFees(FEE_AMOUNT);

            // 2. Wait for distribution
            await time.increase(DISTRIBUTION_INTERVAL + 1);

            // 3. Distribute to staking
            await treasury.distributeRewards();

            // 4. Allocate and execute grant
            const grantAmount = ethers.parseEther("500");
            await treasury.connect(governance).allocateGrant(grantRecipient.address, grantAmount, "Test");
            await treasury.executeGrant(0);

            // 5. Propose and execute dev withdrawal
            await treasury.connect(escrow).receiveFees(FEE_AMOUNT); // Add more for dev allocation
            const devAllocation = (await treasury.getAllocations()).development;

            await treasury.connect(signer1).proposeWithdrawal(devRecipient.address, devAllocation / 2n, "Dev work");
            await treasury.connect(signer2).signWithdrawal(0);
            await treasury.connect(signer3).signWithdrawal(0);
            await treasury.executeWithdrawal(0);

            // Verify all outflows recorded
            expect(await treasury.getOutflowHistoryLength()).to.equal(3);
        });

        it("should handle multiple concurrent withdrawals", async function () {
            await treasury.connect(escrow).receiveFees(ethers.parseEther("100000"));

            // Propose multiple withdrawals
            await treasury.connect(signer1).proposeWithdrawal(devRecipient.address, 1000, "Withdrawal 1");
            await treasury.connect(signer2).proposeWithdrawal(admin.address, 2000, "Withdrawal 2");

            const info1 = await treasury.getWithdrawalInfo(0);
            const info2 = await treasury.getWithdrawalInfo(1);

            expect(info1.to).to.equal(devRecipient.address);
            expect(info2.to).to.equal(admin.address);
        });
    });
});
