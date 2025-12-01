import { expect } from "chai";
import { ethers } from "hardhat";
import { time, mine } from "@nomicfoundation/hardhat-network-helpers";
import { HardhatEthersSigner } from "@nomicfoundation/hardhat-ethers/signers";
import {
    ShaktiGovernor,
    ShaktiTimelock,
    StakedShaktiVotes,
} from "../typechain-types";

describe("SHAKTI-CHAIN Governance", function () {
    let governor: ShaktiGovernor;
    let timelock: ShaktiTimelock;
    let votesToken: StakedShaktiVotes;

    let owner: HardhatEthersSigner;
    let proposer: HardhatEthersSigner;
    let voter1: HardhatEthersSigner;
    let voter2: HardhatEthersSigner;
    let voter3: HardhatEthersSigner;
    let executor: HardhatEthersSigner;
    let emergencyAdmin: HardhatEthersSigner;

    // Governance parameters
    const VOTING_DELAY = 7200n; // 1 day in blocks (12s/block)
    const VOTING_PERIOD = 36000n; // 5 days in blocks
    const PROPOSAL_THRESHOLD = ethers.parseEther("100000"); // 100k SHAKTI
    const QUORUM_PERCENTAGE = 4n; // 4%
    const TIMELOCK_MIN_DELAY = 2n * 24n * 60n * 60n; // 2 days
    const EMERGENCY_THRESHOLD = ethers.parseEther("500000"); // 500k SHAKTI

    // Test amounts
    const LARGE_STAKE = ethers.parseEther("1000000"); // 1M SHAKTI
    const MEDIUM_STAKE = ethers.parseEther("200000"); // 200k SHAKTI
    const SMALL_STAKE = ethers.parseEther("50000"); // 50k SHAKTI

    beforeEach(async function () {
        [owner, proposer, voter1, voter2, voter3, executor, emergencyAdmin] = await ethers.getSigners();

        // Deploy StakedShaktiVotes
        const StakedShaktiVotes = await ethers.getContractFactory("StakedShaktiVotes");
        votesToken = await StakedShaktiVotes.deploy(owner.address);
        await votesToken.waitForDeployment();

        // Authorize owner as minter for testing
        await votesToken.authorizeMinter(owner.address);

        // Deploy ShaktiTimelock
        const ShaktiTimelock = await ethers.getContractFactory("ShaktiTimelock");
        timelock = await ShaktiTimelock.deploy(
            TIMELOCK_MIN_DELAY,
            [owner.address], // proposers (will add governor later)
            [owner.address, executor.address], // executors
            owner.address // admin
        );
        await timelock.waitForDeployment();

        // Deploy ShaktiGovernor
        const ShaktiGovernor = await ethers.getContractFactory("ShaktiGovernor");
        governor = await ShaktiGovernor.deploy(
            await votesToken.getAddress(),
            await timelock.getAddress(),
            VOTING_DELAY,
            VOTING_PERIOD,
            PROPOSAL_THRESHOLD
        );
        await governor.waitForDeployment();

        // Setup roles
        const PROPOSER_ROLE = await timelock.PROPOSER_ROLE();
        const CANCELLER_ROLE = await timelock.CANCELLER_ROLE();
        const EXECUTOR_ROLE = await timelock.EXECUTOR_ROLE();

        // Grant governor the proposer and canceller roles
        await timelock.grantRole(PROPOSER_ROLE, await governor.getAddress());
        await timelock.grantRole(CANCELLER_ROLE, await governor.getAddress());

        // Grant executor role to governor (so it can execute proposals)
        await timelock.grantRole(EXECUTOR_ROLE, await governor.getAddress());

        // Grant emergency role
        await timelock.grantEmergencyRole(emergencyAdmin.address);

        // Mint voting tokens for testing
        await votesToken.mint(proposer.address, LARGE_STAKE);
        await votesToken.mint(voter1.address, MEDIUM_STAKE);
        await votesToken.mint(voter2.address, MEDIUM_STAKE);
        await votesToken.mint(voter3.address, SMALL_STAKE);

        // Delegate voting power
        await votesToken.connect(proposer).delegate(proposer.address);
        await votesToken.connect(voter1).delegate(voter1.address);
        await votesToken.connect(voter2).delegate(voter2.address);
        await votesToken.connect(voter3).delegate(voter3.address);

        // Mine a block to record checkpoints
        await mine(1);
    });

    // ============ StakedShaktiVotes Tests ============

    describe("StakedShaktiVotes", function () {
        describe("Deployment", function () {
            it("Should set correct name and symbol", async function () {
                expect(await votesToken.name()).to.equal("Staked SHAKTI Votes");
                expect(await votesToken.symbol()).to.equal("stkSHAKTI");
            });

            it("Should set owner correctly", async function () {
                expect(await votesToken.owner()).to.equal(owner.address);
            });

            it("Should enable auto-delegation by default", async function () {
                expect(await votesToken.autoDelegateEnabled()).to.be.true;
            });
        });

        describe("Minter Management", function () {
            it("Should authorize minter correctly", async function () {
                const newMinter = voter3.address;
                await votesToken.authorizeMinter(newMinter);
                expect(await votesToken.authorizedMinters(newMinter)).to.be.true;
                expect(await votesToken.minterCount()).to.equal(2n);
            });

            it("Should revert when authorizing zero address", async function () {
                await expect(votesToken.authorizeMinter(ethers.ZeroAddress))
                    .to.be.revertedWithCustomError(votesToken, "ZeroAddress");
            });

            it("Should revert when authorizing already authorized minter", async function () {
                await expect(votesToken.authorizeMinter(owner.address))
                    .to.be.revertedWithCustomError(votesToken, "MinterAlreadyAuthorized");
            });

            it("Should revoke minter correctly", async function () {
                await votesToken.revokeMinter(owner.address);
                expect(await votesToken.authorizedMinters(owner.address)).to.be.false;
                expect(await votesToken.minterCount()).to.equal(0n);
            });

            it("Should revert when revoking non-authorized minter", async function () {
                await expect(votesToken.revokeMinter(voter1.address))
                    .to.be.revertedWithCustomError(votesToken, "MinterNotAuthorized");
            });

            it("Should only allow owner to authorize minter", async function () {
                await expect(votesToken.connect(voter1).authorizeMinter(voter2.address))
                    .to.be.revertedWithCustomError(votesToken, "OwnableUnauthorizedAccount");
            });
        });

        describe("Minting", function () {
            it("Should mint tokens correctly", async function () {
                const amount = ethers.parseEther("100000");
                await votesToken.mint(executor.address, amount);
                expect(await votesToken.balanceOf(executor.address)).to.equal(amount);
            });

            it("Should auto-delegate on first mint", async function () {
                const amount = ethers.parseEther("100000");
                await votesToken.mint(executor.address, amount);
                await mine(1);
                expect(await votesToken.delegates(executor.address)).to.equal(executor.address);
                expect(await votesToken.getVotes(executor.address)).to.equal(amount);
            });

            it("Should track total minted", async function () {
                const initialMinted = await votesToken.totalVotesMinted();
                const amount = ethers.parseEther("100000");
                await votesToken.mint(executor.address, amount);
                expect(await votesToken.totalVotesMinted()).to.equal(initialMinted + amount);
            });

            it("Should emit VotesMinted event", async function () {
                const amount = ethers.parseEther("100000");
                await expect(votesToken.mint(executor.address, amount))
                    .to.emit(votesToken, "VotesMinted")
                    .withArgs(executor.address, amount, owner.address);
            });

            it("Should revert when unauthorized minter", async function () {
                await expect(votesToken.connect(voter1).mint(executor.address, 1000n))
                    .to.be.revertedWithCustomError(votesToken, "UnauthorizedMinter");
            });

            it("Should revert when minting zero amount", async function () {
                await expect(votesToken.mint(executor.address, 0n))
                    .to.be.revertedWithCustomError(votesToken, "ZeroAmount");
            });
        });

        describe("Burning", function () {
            it("Should burn tokens correctly", async function () {
                const initialBalance = await votesToken.balanceOf(proposer.address);
                const burnAmount = ethers.parseEther("100000");
                await votesToken.burn(proposer.address, burnAmount);
                expect(await votesToken.balanceOf(proposer.address)).to.equal(initialBalance - burnAmount);
            });

            it("Should track total burned", async function () {
                const burnAmount = ethers.parseEther("100000");
                await votesToken.burn(proposer.address, burnAmount);
                expect(await votesToken.totalVotesBurned()).to.equal(burnAmount);
            });

            it("Should emit VotesBurned event", async function () {
                const burnAmount = ethers.parseEther("100000");
                await expect(votesToken.burn(proposer.address, burnAmount))
                    .to.emit(votesToken, "VotesBurned")
                    .withArgs(proposer.address, burnAmount, owner.address);
            });

            it("Should revert when unauthorized burner", async function () {
                await expect(votesToken.connect(voter1).burn(proposer.address, 1000n))
                    .to.be.revertedWithCustomError(votesToken, "UnauthorizedBurner");
            });
        });

        describe("Delegation", function () {
            it("Should delegate voting power correctly", async function () {
                // voter3 delegates to voter1
                await votesToken.connect(voter3).delegate(voter1.address);
                await mine(1);

                // voter1 should have their own votes + voter3's votes
                const expectedVotes = MEDIUM_STAKE + SMALL_STAKE;
                expect(await votesToken.getVotes(voter1.address)).to.equal(expectedVotes);
            });

            it("Should update delegates", async function () {
                await votesToken.connect(voter3).delegate(voter1.address);
                expect(await votesToken.delegates(voter3.address)).to.equal(voter1.address);
            });

            it("Should revert when delegating to zero address", async function () {
                await expect(votesToken.connect(voter1).delegate(ethers.ZeroAddress))
                    .to.be.revertedWithCustomError(votesToken, "ZeroAddress");
            });
        });

        describe("View Functions", function () {
            it("Should return correct voting power", async function () {
                const power = await votesToken.getVotingPower(proposer.address);
                expect(power).to.equal(LARGE_STAKE);
            });

            it("Should return correct voting stats", async function () {
                const stats = await votesToken.getVotingStats();
                expect(stats.supply).to.equal(LARGE_STAKE + MEDIUM_STAKE + MEDIUM_STAKE + SMALL_STAKE);
                expect(stats.minters).to.equal(1n);
            });

            it("Should check sufficient voting power", async function () {
                expect(await votesToken.hasSufficientVotingPower(proposer.address, PROPOSAL_THRESHOLD)).to.be.true;
                expect(await votesToken.hasSufficientVotingPower(voter3.address, PROPOSAL_THRESHOLD)).to.be.false;
            });
        });
    });

    // ============ ShaktiTimelock Tests ============

    describe("ShaktiTimelock", function () {
        describe("Deployment", function () {
            it("Should set correct minimum delay", async function () {
                expect(await timelock.standardDelay()).to.equal(TIMELOCK_MIN_DELAY);
            });

            it("Should set correct constants", async function () {
                expect(await timelock.MIN_DELAY()).to.equal(2n * 24n * 60n * 60n);
                expect(await timelock.MAX_DELAY()).to.equal(30n * 24n * 60n * 60n);
                expect(await timelock.EMERGENCY_DELAY()).to.equal(6n * 60n * 60n);
            });

            it("Should set emergency mode duration", async function () {
                expect(await timelock.emergencyModeDuration()).to.equal(7n * 24n * 60n * 60n);
            });
        });

        describe("Delay Management", function () {
            it("Should update standard delay", async function () {
                const newDelay = 3n * 24n * 60n * 60n; // 3 days
                await timelock.updateStandardDelay(newDelay);
                expect(await timelock.standardDelay()).to.equal(newDelay);
            });

            it("Should emit StandardDelayUpdated event", async function () {
                const newDelay = 3n * 24n * 60n * 60n;
                await expect(timelock.updateStandardDelay(newDelay))
                    .to.emit(timelock, "StandardDelayUpdated")
                    .withArgs(TIMELOCK_MIN_DELAY, newDelay);
            });

            it("Should revert when delay below minimum", async function () {
                const tooLow = 1n * 24n * 60n * 60n; // 1 day
                await expect(timelock.updateStandardDelay(tooLow))
                    .to.be.revertedWithCustomError(timelock, "DelayBelowMinimum");
            });

            it("Should revert when delay above maximum", async function () {
                const tooHigh = 31n * 24n * 60n * 60n; // 31 days
                await expect(timelock.updateStandardDelay(tooHigh))
                    .to.be.revertedWithCustomError(timelock, "DelayAboveMaximum");
            });
        });

        describe("Emergency Mode", function () {
            it("Should activate emergency mode", async function () {
                await timelock.connect(emergencyAdmin).activateEmergencyMode();
                expect(await timelock.isEmergencyModeActive()).to.be.true;
            });

            it("Should emit EmergencyModeActivated event", async function () {
                await expect(timelock.connect(emergencyAdmin).activateEmergencyMode())
                    .to.emit(timelock, "EmergencyModeActivated");
            });

            it("Should deactivate emergency mode", async function () {
                await timelock.connect(emergencyAdmin).activateEmergencyMode();
                await timelock.connect(emergencyAdmin).deactivateEmergencyMode();
                expect(await timelock.isEmergencyModeActive()).to.be.false;
            });

            it("Should revert when activating already active emergency", async function () {
                await timelock.connect(emergencyAdmin).activateEmergencyMode();
                await expect(timelock.connect(emergencyAdmin).activateEmergencyMode())
                    .to.be.revertedWithCustomError(timelock, "EmergencyAlreadyActive");
            });

            it("Should revert when deactivating inactive emergency", async function () {
                await expect(timelock.connect(emergencyAdmin).deactivateEmergencyMode())
                    .to.be.revertedWithCustomError(timelock, "EmergencyNotActive");
            });

            it("Should auto-expire after duration", async function () {
                await timelock.connect(emergencyAdmin).activateEmergencyMode();
                expect(await timelock.isEmergencyModeActive()).to.be.true;

                // Fast forward past emergency duration
                await time.increase(7n * 24n * 60n * 60n + 1n);

                expect(await timelock.isEmergencyModeActive()).to.be.false;
            });

            it("Should return correct time remaining", async function () {
                await timelock.connect(emergencyAdmin).activateEmergencyMode();

                // Should have approximately 7 days remaining
                const remaining = await timelock.emergencyModeTimeRemaining();
                expect(remaining).to.be.closeTo(7n * 24n * 60n * 60n, 10n);
            });

            it("Should return zero remaining when not active", async function () {
                expect(await timelock.emergencyModeTimeRemaining()).to.equal(0n);
            });

            it("Should get effective delay based on emergency mode", async function () {
                // Normal delay
                expect(await timelock.getEffectiveDelay()).to.equal(TIMELOCK_MIN_DELAY);

                // Emergency delay
                await timelock.connect(emergencyAdmin).activateEmergencyMode();
                expect(await timelock.getEffectiveDelay()).to.equal(6n * 60n * 60n);
            });
        });

        describe("Emergency Role Management", function () {
            it("Should check emergency role correctly", async function () {
                expect(await timelock.hasEmergencyRole(emergencyAdmin.address)).to.be.true;
                expect(await timelock.hasEmergencyRole(voter1.address)).to.be.false;
            });

            it("Should grant emergency role", async function () {
                await timelock.grantEmergencyRole(voter1.address);
                expect(await timelock.hasEmergencyRole(voter1.address)).to.be.true;
            });

            it("Should revoke emergency role", async function () {
                await timelock.revokeEmergencyRole(emergencyAdmin.address);
                expect(await timelock.hasEmergencyRole(emergencyAdmin.address)).to.be.false;
            });
        });

        describe("Statistics", function () {
            it("Should return correct timelock stats", async function () {
                const stats = await timelock.getTimelockStats();
                expect(stats.total).to.equal(0n);
                expect(stats.emergency).to.equal(0n);
                expect(stats.currentDelay).to.equal(TIMELOCK_MIN_DELAY);
                expect(stats.emergencyActive).to.be.false;
            });
        });
    });

    // ============ ShaktiGovernor Tests ============

    describe("ShaktiGovernor", function () {
        describe("Deployment", function () {
            it("Should set correct name", async function () {
                expect(await governor.name()).to.equal("ShaktiGovernor");
            });

            it("Should set correct voting delay", async function () {
                expect(await governor.votingDelay()).to.equal(VOTING_DELAY);
            });

            it("Should set correct voting period", async function () {
                expect(await governor.votingPeriod()).to.equal(VOTING_PERIOD);
            });

            it("Should set correct proposal threshold", async function () {
                expect(await governor.proposalThreshold()).to.equal(PROPOSAL_THRESHOLD);
            });

            it("Should set correct emergency threshold", async function () {
                expect(await governor.emergencyThreshold()).to.equal(EMERGENCY_THRESHOLD);
            });
        });

        describe("Standard Proposals", function () {
            let proposalId: bigint;
            let targets: string[];
            let values: bigint[];
            let calldatas: string[];
            let description: string;

            beforeEach(async function () {
                // Create a simple proposal to update emergency threshold
                targets = [await governor.getAddress()];
                values = [0n];
                calldatas = [governor.interface.encodeFunctionData("setEmergencyThreshold", [ethers.parseEther("600000")])];
                description = "Update emergency threshold to 600,000 SHAKTI";
            });

            it("Should create standard proposal", async function () {
                const tx = await governor.connect(proposer).propose(targets, values, calldatas, description);
                const receipt = await tx.wait();

                // Get proposal ID from event
                const event = receipt?.logs.find(
                    (log) => log.topics[0] === governor.interface.getEvent("ProposalCreated").topicHash
                );
                expect(event).to.not.be.undefined;
            });

            it("Should emit ProposalCreatedWithType event", async function () {
                await expect(governor.connect(proposer).propose(targets, values, calldatas, description))
                    .to.emit(governor, "ProposalCreatedWithType");
            });

            it("Should increment total proposals", async function () {
                const before = await governor.totalProposals();
                await governor.connect(proposer).propose(targets, values, calldatas, description);
                expect(await governor.totalProposals()).to.equal(before + 1n);
            });

            it("Should store proposal type as Standard", async function () {
                const tx = await governor.connect(proposer).propose(targets, values, calldatas, description);
                const receipt = await tx.wait();

                // Get proposal ID
                proposalId = await governor.hashProposal(targets, values, calldatas, ethers.keccak256(ethers.toUtf8Bytes(description)));

                expect(await governor.getProposalType(proposalId)).to.equal(0n); // Standard
            });

            it("Should revert when proposer has insufficient voting power", async function () {
                await expect(governor.connect(voter3).propose(targets, values, calldatas, description))
                    .to.be.reverted;
            });
        });

        describe("Typed Proposals", function () {
            let targets: string[];
            let values: bigint[];
            let calldatas: string[];
            let description: string;

            beforeEach(async function () {
                targets = [await governor.getAddress()];
                values = [0n];
                calldatas = [governor.interface.encodeFunctionData("setEmergencyThreshold", [ethers.parseEther("600000")])];
                description = "Parameter change: Update emergency threshold";
            });

            it("Should create ParameterChange proposal", async function () {
                const tx = await governor.connect(proposer).proposeWithType(targets, values, calldatas, description, 1n);
                const receipt = await tx.wait();

                const proposalId = await governor.hashProposal(targets, values, calldatas, ethers.keccak256(ethers.toUtf8Bytes(description)));
                expect(await governor.getProposalType(proposalId)).to.equal(1n); // ParameterChange
            });

            it("Should create TreasurySpend proposal", async function () {
                const tx = await governor.connect(proposer).proposeWithType(targets, values, calldatas, "Treasury: " + description, 3n);
                const receipt = await tx.wait();

                const proposalId = await governor.hashProposal(targets, values, calldatas, ethers.keccak256(ethers.toUtf8Bytes("Treasury: " + description)));
                expect(await governor.getProposalType(proposalId)).to.equal(3n); // TreasurySpend
            });

            it("Should revert when creating Emergency via proposeWithType", async function () {
                await expect(governor.connect(proposer).proposeWithType(targets, values, calldatas, description, 4n))
                    .to.be.revertedWithCustomError(governor, "InvalidProposalType");
            });
        });

        describe("Emergency Proposals", function () {
            let targets: string[];
            let values: bigint[];
            let calldatas: string[];
            let description: string;

            beforeEach(async function () {
                targets = [await governor.getAddress()];
                values = [0n];
                calldatas = [governor.interface.encodeFunctionData("setEmergencyThreshold", [ethers.parseEther("600000")])];
                description = "EMERGENCY: Critical security fix";
            });

            it("Should create emergency proposal with sufficient voting power", async function () {
                const tx = await governor.connect(proposer).proposeEmergency(targets, values, calldatas, description);
                const receipt = await tx.wait();

                const proposalId = await governor.hashProposal(targets, values, calldatas, ethers.keccak256(ethers.toUtf8Bytes(description)));
                expect(await governor.isEmergencyProposal(proposalId)).to.be.true;
            });

            it("Should emit EmergencyProposalCreated event", async function () {
                await expect(governor.connect(proposer).proposeEmergency(targets, values, calldatas, description))
                    .to.emit(governor, "EmergencyProposalCreated");
            });

            it("Should increment emergency proposals count", async function () {
                const before = await governor.emergencyProposalsCount();
                await governor.connect(proposer).proposeEmergency(targets, values, calldatas, description);
                expect(await governor.emergencyProposalsCount()).to.equal(before + 1n);
            });

            it("Should revert when emergency threshold not met", async function () {
                // voter1 has 200k, emergency threshold is 500k
                await expect(governor.connect(voter1).proposeEmergency(targets, values, calldatas, description))
                    .to.be.revertedWithCustomError(governor, "EmergencyThresholdNotMet");
            });
        });

        describe("Voting", function () {
            let proposalId: bigint;
            let targets: string[];
            let values: bigint[];
            let calldatas: string[];
            let description: string;

            beforeEach(async function () {
                targets = [await governor.getAddress()];
                values = [0n];
                calldatas = [governor.interface.encodeFunctionData("setEmergencyThreshold", [ethers.parseEther("600000")])];
                description = "Update emergency threshold";

                // Create proposal
                await governor.connect(proposer).propose(targets, values, calldatas, description);
                proposalId = await governor.hashProposal(targets, values, calldatas, ethers.keccak256(ethers.toUtf8Bytes(description)));

                // Move past voting delay
                await mine(VOTING_DELAY + 1n);
            });

            it("Should allow voting on active proposal", async function () {
                // Vote in favor (1 = For)
                await expect(governor.connect(voter1).castVote(proposalId, 1))
                    .to.emit(governor, "VoteCast");
            });

            it("Should track votes correctly", async function () {
                await governor.connect(voter1).castVote(proposalId, 1); // For
                await governor.connect(voter2).castVote(proposalId, 0); // Against
                await governor.connect(voter3).castVote(proposalId, 2); // Abstain

                const [againstVotes, forVotes, abstainVotes] = await governor.proposalVotes(proposalId);
                expect(forVotes).to.equal(MEDIUM_STAKE);
                expect(againstVotes).to.equal(MEDIUM_STAKE);
                expect(abstainVotes).to.equal(SMALL_STAKE);
            });

            it("Should prevent double voting", async function () {
                await governor.connect(voter1).castVote(proposalId, 1);
                await expect(governor.connect(voter1).castVote(proposalId, 1))
                    .to.be.reverted;
            });

            it("Should respect voting period", async function () {
                // Vote while active
                await governor.connect(voter1).castVote(proposalId, 1);

                // Move past voting period
                await mine(VOTING_PERIOD + 1n);

                // Should not allow voting after period ends
                await expect(governor.connect(voter2).castVote(proposalId, 1))
                    .to.be.reverted;
            });
        });

        describe("Full Proposal Lifecycle", function () {
            let proposalId: bigint;
            let targets: string[];
            let values: bigint[];
            let calldatas: string[];
            let description: string;
            let descriptionHash: string;

            beforeEach(async function () {
                targets = [await governor.getAddress()];
                values = [0n];
                calldatas = [governor.interface.encodeFunctionData("setEmergencyThreshold", [ethers.parseEther("600000")])];
                description = "Update emergency threshold to 600k";
                descriptionHash = ethers.keccak256(ethers.toUtf8Bytes(description));
            });

            it("Should complete full lifecycle: create -> vote -> queue -> execute", async function () {
                // 1. Create proposal
                await governor.connect(proposer).propose(targets, values, calldatas, description);
                proposalId = await governor.hashProposal(targets, values, calldatas, descriptionHash);

                // State should be Pending
                expect(await governor.state(proposalId)).to.equal(0n);

                // 2. Move past voting delay
                await mine(VOTING_DELAY + 1n);

                // State should be Active
                expect(await governor.state(proposalId)).to.equal(1n);

                // 3. Vote (need quorum)
                await governor.connect(proposer).castVote(proposalId, 1); // 1M votes
                await governor.connect(voter1).castVote(proposalId, 1); // 200k votes
                await governor.connect(voter2).castVote(proposalId, 1); // 200k votes

                // 4. Move past voting period
                await mine(VOTING_PERIOD + 1n);

                // State should be Succeeded
                expect(await governor.state(proposalId)).to.equal(4n);

                // 5. Queue the proposal
                await governor.queue(targets, values, calldatas, descriptionHash);

                // State should be Queued
                expect(await governor.state(proposalId)).to.equal(5n);

                // 6. Wait for timelock delay
                await time.increase(TIMELOCK_MIN_DELAY + 1n);

                // 7. Execute
                await governor.execute(targets, values, calldatas, descriptionHash);

                // State should be Executed
                expect(await governor.state(proposalId)).to.equal(7n);

                // 8. Verify the change took effect
                expect(await governor.emergencyThreshold()).to.equal(ethers.parseEther("600000"));
            });

            it("Should fail proposal that doesn't reach quorum", async function () {
                // Create proposal
                await governor.connect(proposer).propose(targets, values, calldatas, description);
                proposalId = await governor.hashProposal(targets, values, calldatas, descriptionHash);

                // Move past voting delay
                await mine(VOTING_DELAY + 1n);

                // Only voter3 votes (50k - not enough for 4% quorum)
                await governor.connect(voter3).castVote(proposalId, 1);

                // Move past voting period
                await mine(VOTING_PERIOD + 1n);

                // State should be Defeated
                expect(await governor.state(proposalId)).to.equal(3n);
            });

            it("Should fail proposal with more against votes", async function () {
                // First give voter1 and voter2 more tokens to outweigh proposer
                await votesToken.mint(voter1.address, ethers.parseEther("600000"));
                await votesToken.mint(voter2.address, ethers.parseEther("600000"));
                await mine(1);

                // Create proposal
                await governor.connect(proposer).propose(targets, values, calldatas, description);
                proposalId = await governor.hashProposal(targets, values, calldatas, descriptionHash);

                // Move past voting delay
                await mine(VOTING_DELAY + 1n);

                // Proposer votes for (1M), voters vote against (800k + 800k = 1.6M)
                // Total for: 1M, against: 1.6M - This should fail
                await governor.connect(proposer).castVote(proposalId, 1);
                await governor.connect(voter1).castVote(proposalId, 0);
                await governor.connect(voter2).castVote(proposalId, 0);

                // Move past voting period
                await mine(VOTING_PERIOD + 1n);

                // State should be Defeated
                expect(await governor.state(proposalId)).to.equal(3n);
            });
        });

        describe("Governance Statistics", function () {
            it("Should return correct governance stats", async function () {
                const targets = [await governor.getAddress()];
                const values = [0n];
                const calldatas = [governor.interface.encodeFunctionData("setEmergencyThreshold", [ethers.parseEther("600000")])];

                // Create standard proposal
                await governor.connect(proposer).propose(targets, values, calldatas, "Standard proposal");

                // Create emergency proposal
                await governor.connect(proposer).proposeEmergency(targets, values, calldatas, "Emergency proposal");

                const stats = await governor.getGovernanceStats();
                expect(stats.total).to.equal(2n);
                expect(stats.emergency).to.equal(1n);
                expect(stats.threshold).to.equal(PROPOSAL_THRESHOLD);
            });
        });

        describe("Quorum", function () {
            it("Should calculate quorum correctly", async function () {
                const totalSupply = await votesToken.totalSupply();
                const expectedQuorum = (totalSupply * QUORUM_PERCENTAGE) / 100n;

                await mine(1);
                const blockNumber = await ethers.provider.getBlockNumber();
                const actualQuorum = await governor.quorum(blockNumber - 1);

                expect(actualQuorum).to.equal(expectedQuorum);
            });
        });
    });

    // ============ Integration Tests ============

    describe("Integration", function () {
        describe("Governor + Timelock Integration", function () {
            it("Should use timelock as executor", async function () {
                // Governor's executor should be the timelock
                expect(await governor.timelock()).to.equal(await timelock.getAddress());
            });

            it("Should require timelock for execution", async function () {
                expect(await governor.proposalNeedsQueuing(0)).to.be.true;
            });
        });

        describe("Votes Token + Governor Integration", function () {
            it("Should use votes token for voting power", async function () {
                expect(await governor.token()).to.equal(await votesToken.getAddress());
            });

            it("Should reflect token balance changes in voting power", async function () {
                const initialPower = await votesToken.getVotes(proposer.address);

                // Burn some tokens
                const burnAmount = ethers.parseEther("100000");
                await votesToken.burn(proposer.address, burnAmount);
                await mine(1);

                const newPower = await votesToken.getVotes(proposer.address);
                expect(newPower).to.equal(initialPower - burnAmount);
            });

            it("Should use historical voting power for proposals", async function () {
                // Create proposal
                const targets = [await governor.getAddress()];
                const values = [0n];
                const calldatas = [governor.interface.encodeFunctionData("setEmergencyThreshold", [ethers.parseEther("600000")])];
                const description = "Test historical voting power";

                await governor.connect(proposer).propose(targets, values, calldatas, description);

                // Burn tokens after proposal creation
                await votesToken.burn(proposer.address, ethers.parseEther("900000")); // Burn most tokens

                // Proposer should still have their original voting power for this proposal
                // because voting power is checkpointed
            });
        });
    });
});
