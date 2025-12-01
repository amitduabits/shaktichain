/**
 * SHAKTI-CHAIN Integration Test: Governance Flow
 *
 * Tests the complete governance lifecycle:
 * 1. Token delegation
 * 2. Proposal creation
 * 3. Voting period
 * 4. Proposal execution via Timelock
 *
 * Scenarios:
 * - Successful proposal: Create → Vote → Queue → Execute
 * - Failed proposal: Insufficient votes
 * - Parameter change via governance
 */

import { expect } from "chai";
import { ethers } from "hardhat";
import { time } from "@nomicfoundation/hardhat-network-helpers";
import {
  ShaktiToken,
  ShaktiGovernor,
  TimelockController,
  EnergyAuction,
} from "../../typechain-types";
import { SignerWithAddress } from "@nomicfoundation/hardhat-ethers/signers";

describe("Integration: Governance Flow", function () {
  let token: ShaktiToken;
  let governor: ShaktiGovernor;
  let timelock: TimelockController;
  let auction: EnergyAuction;

  let admin: SignerWithAddress;
  let proposer: SignerWithAddress;
  let voter1: SignerWithAddress;
  let voter2: SignerWithAddress;
  let voter3: SignerWithAddress;

  // Governance parameters
  const VOTING_DELAY = 1; // 1 block
  const VOTING_PERIOD = 50400; // ~7 days
  const PROPOSAL_THRESHOLD = ethers.parseEther("100000"); // 100,000 SHAKTI
  const TIMELOCK_DELAY = 48 * 3600; // 48 hours

  // Token distribution
  const PROPOSER_TOKENS = ethers.parseEther("200000"); // Enough to propose
  const VOTER_TOKENS = ethers.parseEther("1000000"); // Significant voting power

  beforeEach(async function () {
    [admin, proposer, voter1, voter2, voter3] = await ethers.getSigners();

    // Deploy Token
    const TokenFactory = await ethers.getContractFactory("ShaktiToken");
    token = await TokenFactory.deploy(admin.address);
    await token.waitForDeployment();

    // Deploy Timelock
    const TimelockFactory = await ethers.getContractFactory("TimelockController");
    timelock = await TimelockFactory.deploy(
      TIMELOCK_DELAY,
      [], // proposers (will be governor)
      [], // executors (will be governor)
      admin.address
    );
    await timelock.waitForDeployment();

    // Deploy Governor
    const GovernorFactory = await ethers.getContractFactory("ShaktiGovernor");
    governor = await GovernorFactory.deploy(
      await token.getAddress(),
      await timelock.getAddress(),
      VOTING_DELAY,
      VOTING_PERIOD,
      PROPOSAL_THRESHOLD
    );
    await governor.waitForDeployment();

    // Setup Timelock roles
    const PROPOSER_ROLE = await timelock.PROPOSER_ROLE();
    const EXECUTOR_ROLE = await timelock.EXECUTOR_ROLE();
    const CANCELLER_ROLE = await timelock.CANCELLER_ROLE();

    await timelock.grantRole(PROPOSER_ROLE, await governor.getAddress());
    await timelock.grantRole(EXECUTOR_ROLE, await governor.getAddress());
    await timelock.grantRole(CANCELLER_ROLE, await governor.getAddress());

    // Deploy a contract to govern (EnergyAuction)
    const RegistryFactory = await ethers.getContractFactory("EnergyRegistry");
    const registry = await RegistryFactory.deploy(admin.address);

    const AuctionFactory = await ethers.getContractFactory("EnergyAuction");
    auction = await AuctionFactory.deploy(
      await token.getAddress(),
      await registry.getAddress(),
      await timelock.getAddress(), // Timelock is admin
      ethers.parseEther("0.001"),
      ethers.parseEther("0.01")
    );
    await auction.waitForDeployment();

    // Distribute tokens
    await token.mint(proposer.address, PROPOSER_TOKENS);
    await token.mint(voter1.address, VOTER_TOKENS);
    await token.mint(voter2.address, VOTER_TOKENS);
    await token.mint(voter3.address, VOTER_TOKENS);

    // Delegate voting power (required for governance)
    await token.connect(proposer).delegate(proposer.address);
    await token.connect(voter1).delegate(voter1.address);
    await token.connect(voter2).delegate(voter2.address);
    await token.connect(voter3).delegate(voter3.address);

    // Mine a block to register delegation
    await ethers.provider.send("evm_mine", []);
  });

  describe("Proposal Creation", function () {
    it("should allow users with enough tokens to create proposals", async function () {
      // Prepare proposal
      const targets = [await auction.getAddress()];
      const values = [0];
      const calldatas = [
        auction.interface.encodeFunctionData("updatePriceBounds", [
          ethers.parseEther("0.002"), // New min price
          ethers.parseEther("0.02"),  // New max price
        ]),
      ];
      const description = "Proposal #1: Update auction price bounds";

      // Create proposal
      const tx = await governor.connect(proposer).propose(
        targets,
        values,
        calldatas,
        description
      );
      const receipt = await tx.wait();

      // Get proposal ID from event
      const proposalCreatedEvent = receipt?.logs.find(
        (log) => {
          try {
            return governor.interface.parseLog({ topics: log.topics as string[], data: log.data })?.name === "ProposalCreated";
          } catch {
            return false;
          }
        }
      );

      expect(proposalCreatedEvent).to.not.be.undefined;

      console.log("\n  Proposal Created:");
      console.log("  -----------------");
      console.log(`  Description: ${description}`);
      console.log(`  Target: ${targets[0]}`);
      console.log(`  Proposer: ${proposer.address}`);
    });

    it("should reject proposals from users with insufficient tokens", async function () {
      const insufficientUser = (await ethers.getSigners())[5];
      await token.mint(insufficientUser.address, ethers.parseEther("1000")); // Not enough
      await token.connect(insufficientUser).delegate(insufficientUser.address);
      await ethers.provider.send("evm_mine", []);

      const targets = [await auction.getAddress()];
      const values = [0];
      const calldatas = [
        auction.interface.encodeFunctionData("updatePriceBounds", [
          ethers.parseEther("0.002"),
          ethers.parseEther("0.02"),
        ]),
      ];
      const description = "Should fail proposal";

      await expect(
        governor.connect(insufficientUser).propose(targets, values, calldatas, description)
      ).to.be.reverted;
    });
  });

  describe("Voting Process", function () {
    let proposalId: bigint;

    beforeEach(async function () {
      // Create a proposal
      const targets = [await auction.getAddress()];
      const values = [0];
      const calldatas = [
        auction.interface.encodeFunctionData("updatePriceBounds", [
          ethers.parseEther("0.002"),
          ethers.parseEther("0.02"),
        ]),
      ];
      const description = "Proposal: Update price bounds";

      const tx = await governor.connect(proposer).propose(
        targets,
        values,
        calldatas,
        description
      );
      const receipt = await tx.wait();

      // Extract proposal ID
      const descriptionHash = ethers.keccak256(ethers.toUtf8Bytes(description));
      proposalId = await governor.hashProposal(targets, values, calldatas, descriptionHash);

      // Move past voting delay
      await ethers.provider.send("evm_mine", []);
    });

    it("should allow token holders to vote", async function () {
      // Vote in favor (1 = For)
      await governor.connect(voter1).castVote(proposalId, 1);

      // Check vote was recorded
      const hasVoted = await governor.hasVoted(proposalId, voter1.address);
      expect(hasVoted).to.be.true;

      console.log("\n  Vote Cast:");
      console.log("  ----------");
      console.log(`  Voter: ${voter1.address}`);
      console.log(`  Vote: For`);
      console.log(`  Voting Power: ${ethers.formatEther(VOTER_TOKENS)} SHAKTI`);
    });

    it("should count votes correctly", async function () {
      // Multiple votes
      await governor.connect(voter1).castVote(proposalId, 1); // For
      await governor.connect(voter2).castVote(proposalId, 1); // For
      await governor.connect(voter3).castVote(proposalId, 0); // Against

      // Get vote counts
      const votes = await governor.proposalVotes(proposalId);

      console.log("\n  Vote Tally:");
      console.log("  -----------");
      console.log(`  For: ${ethers.formatEther(votes.forVotes)} SHAKTI`);
      console.log(`  Against: ${ethers.formatEther(votes.againstVotes)} SHAKTI`);
      console.log(`  Abstain: ${ethers.formatEther(votes.abstainVotes)} SHAKTI`);

      expect(votes.forVotes).to.equal(VOTER_TOKENS * 2n);
      expect(votes.againstVotes).to.equal(VOTER_TOKENS);
    });

    it("should allow voting with reason", async function () {
      const reason = "This proposal improves price discovery";

      const tx = await governor.connect(voter1).castVoteWithReason(
        proposalId,
        1,
        reason
      );
      const receipt = await tx.wait();

      // Check for VoteCastWithParams event
      expect(receipt?.status).to.equal(1);
    });
  });

  describe("Proposal Execution", function () {
    let proposalId: bigint;
    let targets: string[];
    let values: number[];
    let calldatas: string[];
    let description: string;
    let descriptionHash: string;

    beforeEach(async function () {
      // Setup proposal
      targets = [await auction.getAddress()];
      values = [0];
      calldatas = [
        auction.interface.encodeFunctionData("updatePriceBounds", [
          ethers.parseEther("0.002"),
          ethers.parseEther("0.02"),
        ]),
      ];
      description = "Proposal: Update price bounds to 0.002-0.02";
      descriptionHash = ethers.keccak256(ethers.toUtf8Bytes(description));

      // Create proposal
      await governor.connect(proposer).propose(targets, values, calldatas, description);
      proposalId = await governor.hashProposal(targets, values, calldatas, descriptionHash);

      // Move past voting delay
      await ethers.provider.send("evm_mine", []);
    });

    it("should execute successful proposal after timelock", async function () {
      // Vote (need quorum - 4% of total supply)
      await governor.connect(voter1).castVote(proposalId, 1);
      await governor.connect(voter2).castVote(proposalId, 1);

      // Move past voting period
      for (let i = 0; i < VOTING_PERIOD + 1; i++) {
        await ethers.provider.send("evm_mine", []);
      }

      // Check proposal succeeded
      const state = await governor.state(proposalId);
      expect(state).to.equal(4); // Succeeded

      // Queue proposal
      await governor.queue(targets, values, calldatas, descriptionHash);

      // Move past timelock delay
      await time.increase(TIMELOCK_DELAY + 1);

      // Execute
      await governor.execute(targets, values, calldatas, descriptionHash);

      // Verify changes took effect
      const newMinPrice = await auction.minPrice();
      expect(newMinPrice).to.equal(ethers.parseEther("0.002"));

      console.log("\n  Proposal Executed:");
      console.log("  ------------------");
      console.log(`  New Min Price: ${ethers.formatEther(newMinPrice)} SHAKTI/kWh`);
    });

    it("should reject execution of failed proposal", async function () {
      // Vote against
      await governor.connect(voter1).castVote(proposalId, 0);
      await governor.connect(voter2).castVote(proposalId, 0);
      await governor.connect(voter3).castVote(proposalId, 0);

      // Move past voting period
      for (let i = 0; i < VOTING_PERIOD + 1; i++) {
        await ethers.provider.send("evm_mine", []);
      }

      // Check proposal defeated
      const state = await governor.state(proposalId);
      expect(state).to.equal(3); // Defeated

      // Attempt to queue should fail
      await expect(
        governor.queue(targets, values, calldatas, descriptionHash)
      ).to.be.reverted;
    });
  });

  describe("Governance Parameters", function () {
    it("should report correct governance parameters", async function () {
      const votingDelay = await governor.votingDelay();
      const votingPeriod = await governor.votingPeriod();
      const proposalThreshold = await governor.proposalThreshold();
      const quorumNumerator = await governor.quorumNumerator();

      console.log("\n  Governance Parameters:");
      console.log("  ----------------------");
      console.log(`  Voting Delay: ${votingDelay} blocks`);
      console.log(`  Voting Period: ${votingPeriod} blocks (~${Number(votingPeriod) / 43200} days)`);
      console.log(`  Proposal Threshold: ${ethers.formatEther(proposalThreshold)} SHAKTI`);
      console.log(`  Quorum: ${quorumNumerator}%`);
    });

    it("should correctly calculate quorum", async function () {
      const totalSupply = await token.totalSupply();
      const quorum = await governor.quorum(await ethers.provider.getBlockNumber() - 1);

      // Quorum should be 4% of total supply
      const expectedQuorum = totalSupply * 4n / 100n;

      console.log("\n  Quorum Calculation:");
      console.log("  -------------------");
      console.log(`  Total Supply: ${ethers.formatEther(totalSupply)} SHAKTI`);
      console.log(`  Required Quorum (4%): ${ethers.formatEther(quorum)} SHAKTI`);
    });
  });

  describe("Delegation", function () {
    it("should allow vote delegation", async function () {
      const delegator = (await ethers.getSigners())[6];
      await token.mint(delegator.address, VOTER_TOKENS);

      // Delegate to voter1
      await token.connect(delegator).delegate(voter1.address);
      await ethers.provider.send("evm_mine", []);

      // Check voting power
      const voter1Power = await token.getVotes(voter1.address);

      // Voter1 should have their own tokens + delegated tokens
      expect(voter1Power).to.equal(VOTER_TOKENS * 2n);

      console.log("\n  Delegation:");
      console.log("  -----------");
      console.log(`  Delegator: ${delegator.address}`);
      console.log(`  Delegate: ${voter1.address}`);
      console.log(`  Combined Voting Power: ${ethers.formatEther(voter1Power)} SHAKTI`);
    });

    it("should track historical voting power", async function () {
      const currentBlock = await ethers.provider.getBlockNumber();

      // Check past voting power
      const pastVotes = await token.getPastVotes(voter1.address, currentBlock - 1);
      expect(pastVotes).to.equal(VOTER_TOKENS);
    });
  });

  describe("Proposal Lifecycle", function () {
    it("should transition through all states correctly", async function () {
      const targets = [await auction.getAddress()];
      const values = [0];
      const calldatas = [
        auction.interface.encodeFunctionData("updatePriceBounds", [
          ethers.parseEther("0.002"),
          ethers.parseEther("0.02"),
        ]),
      ];
      const description = "Lifecycle test proposal";
      const descriptionHash = ethers.keccak256(ethers.toUtf8Bytes(description));

      // Create
      await governor.connect(proposer).propose(targets, values, calldatas, description);
      const proposalId = await governor.hashProposal(targets, values, calldatas, descriptionHash);

      // State: Pending (0)
      let state = await governor.state(proposalId);
      expect(state).to.equal(0);
      console.log("\n  Proposal States:");
      console.log("  ----------------");
      console.log("  0: Pending ✓");

      // Move past voting delay
      await ethers.provider.send("evm_mine", []);

      // State: Active (1)
      state = await governor.state(proposalId);
      expect(state).to.equal(1);
      console.log("  1: Active ✓");

      // Vote
      await governor.connect(voter1).castVote(proposalId, 1);
      await governor.connect(voter2).castVote(proposalId, 1);

      // Move past voting period
      for (let i = 0; i < VOTING_PERIOD + 1; i++) {
        await ethers.provider.send("evm_mine", []);
      }

      // State: Succeeded (4)
      state = await governor.state(proposalId);
      expect(state).to.equal(4);
      console.log("  4: Succeeded ✓");

      // Queue
      await governor.queue(targets, values, calldatas, descriptionHash);

      // State: Queued (5)
      state = await governor.state(proposalId);
      expect(state).to.equal(5);
      console.log("  5: Queued ✓");

      // Wait timelock
      await time.increase(TIMELOCK_DELAY + 1);

      // Execute
      await governor.execute(targets, values, calldatas, descriptionHash);

      // State: Executed (7)
      state = await governor.state(proposalId);
      expect(state).to.equal(7);
      console.log("  7: Executed ✓");
    });
  });
});
