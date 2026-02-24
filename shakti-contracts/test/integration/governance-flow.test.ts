import { expect } from "chai";
import { ethers } from "hardhat";
import { mine, time } from "@nomicfoundation/hardhat-network-helpers";
import {
  EnergyAuction,
  ShaktiGovernor,
  ShaktiTimelock,
  ShaktiToken,
  StakedShaktiVotes,
} from "../../typechain-types";

describe("Integration: Governance Flow", function () {
  let votes: StakedShaktiVotes;
  let timelock: ShaktiTimelock;
  let governor: ShaktiGovernor;
  let token: ShaktiToken;
  let auction: EnergyAuction;

  const VOTING_DELAY = 1n;
  const VOTING_PERIOD = 10n;
  const PROPOSAL_THRESHOLD = ethers.parseEther("1000");
  const TIMELOCK_DELAY = 2n * 24n * 60n * 60n;

  beforeEach(async function () {
    const [admin, proposer, voter1, voter2] = await ethers.getSigners();

    const VotesFactory = await ethers.getContractFactory("StakedShaktiVotes");
    votes = await VotesFactory.deploy(admin.address);
    await votes.waitForDeployment();
    await votes.authorizeMinter(admin.address);

    const TimelockFactory = await ethers.getContractFactory("ShaktiTimelock");
    timelock = await TimelockFactory.deploy(
      TIMELOCK_DELAY,
      [admin.address],
      [admin.address],
      admin.address
    );
    await timelock.waitForDeployment();

    const GovernorFactory = await ethers.getContractFactory("ShaktiGovernor");
    governor = await GovernorFactory.deploy(
      await votes.getAddress(),
      await timelock.getAddress(),
      VOTING_DELAY,
      VOTING_PERIOD,
      PROPOSAL_THRESHOLD
    );
    await governor.waitForDeployment();

    const PROPOSER_ROLE = await timelock.PROPOSER_ROLE();
    const CANCELLER_ROLE = await timelock.CANCELLER_ROLE();
    const EXECUTOR_ROLE = await timelock.EXECUTOR_ROLE();
    await timelock.grantRole(PROPOSER_ROLE, await governor.getAddress());
    await timelock.grantRole(CANCELLER_ROLE, await governor.getAddress());
    await timelock.grantRole(EXECUTOR_ROLE, await governor.getAddress());

    const TokenFactory = await ethers.getContractFactory("ShaktiToken");
    token = await TokenFactory.deploy(admin.address, admin.address);
    await token.waitForDeployment();

    const AuctionFactory = await ethers.getContractFactory("EnergyAuction");
    auction = await AuctionFactory.deploy(
      await token.getAddress(),
      ethers.ZeroAddress,
      await timelock.getAddress(),
      ethers.parseEther("0.002"),
      ethers.parseEther("0.015")
    );
    await auction.waitForDeployment();

    await votes.mint(proposer.address, ethers.parseEther("200000"));
    await votes.mint(voter1.address, ethers.parseEther("200000"));
    await votes.mint(voter2.address, ethers.parseEther("200000"));

    await votes.connect(proposer).delegate(proposer.address);
    await votes.connect(voter1).delegate(voter1.address);
    await votes.connect(voter2).delegate(voter2.address);
    await mine(1);
  });

  it("executes a parameter update through proposal -> vote -> queue -> execute", async function () {
    const [, proposer, voter1, voter2] = await ethers.getSigners();

    const targets = [await auction.getAddress()];
    const values = [0n];
    const calldatas = [
      auction.interface.encodeFunctionData("setPriceBounds", [
        ethers.parseEther("0.003"),
        ethers.parseEther("0.02"),
      ]),
    ];
    const description = "Update auction bounds";
    const descriptionHash = ethers.keccak256(ethers.toUtf8Bytes(description));

    await governor.connect(proposer).propose(targets, values, calldatas, description);
    const proposalId = await governor.hashProposal(targets, values, calldatas, descriptionHash);

    await mine(VOTING_DELAY + 1n);
    await governor.connect(proposer).castVote(proposalId, 1);
    await governor.connect(voter1).castVote(proposalId, 1);
    await governor.connect(voter2).castVote(proposalId, 1);

    await mine(VOTING_PERIOD + 1n);
    expect(await governor.state(proposalId)).to.equal(4n); // Succeeded

    await governor.queue(targets, values, calldatas, descriptionHash);
    await time.increase(TIMELOCK_DELAY + 1n);
    await governor.execute(targets, values, calldatas, descriptionHash);

    expect(await auction.minPrice()).to.equal(ethers.parseEther("0.003"));
    expect(await auction.maxPrice()).to.equal(ethers.parseEther("0.02"));
  });
});
