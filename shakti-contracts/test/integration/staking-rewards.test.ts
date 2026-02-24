import { expect } from "chai";
import { ethers } from "hardhat";
import { time } from "@nomicfoundation/hardhat-network-helpers";
import { ShaktiToken, StakingPool } from "../../typechain-types";

describe("Integration: Staking & Rewards", function () {
  let token: ShaktiToken;
  let staking: StakingPool;

  const INITIAL_BALANCE = ethers.parseEther("100000");
  const STAKE_AMOUNT = ethers.parseEther("10000");
  const REWARD_POOL = ethers.parseEther("1000000");
  const LOCK_30_DAYS = 30 * 24 * 60 * 60;
  const LOCK_90_DAYS = 90 * 24 * 60 * 60;

  beforeEach(async function () {
    const [admin, staker1, staker2] = await ethers.getSigners();

    const TokenFactory = await ethers.getContractFactory("ShaktiToken");
    token = await TokenFactory.deploy(admin.address, admin.address);
    await token.waitForDeployment();

    const StakingFactory = await ethers.getContractFactory("StakingPool");
    staking = await StakingFactory.deploy(await token.getAddress(), admin.address, 800);
    await staking.waitForDeployment();

    await token.transfer(await staking.getAddress(), REWARD_POOL);
    await token.transfer(staker1.address, INITIAL_BALANCE);
    await token.transfer(staker2.address, INITIAL_BALANCE);

    await token.connect(staker1).approve(await staking.getAddress(), ethers.MaxUint256);
    await token.connect(staker2).approve(await staking.getAddress(), ethers.MaxUint256);
  });

  it("accrues and claims rewards for locked stake", async function () {
    const [, staker1] = await ethers.getSigners();

    await staking.connect(staker1).stake(STAKE_AMOUNT, LOCK_30_DAYS);
    await time.increase(LOCK_30_DAYS + 1);

    const rewards = await staking.getRewards(staker1.address);
    expect(rewards).to.be.gt(0n);

    const balanceBefore = await token.balanceOf(staker1.address);
    await staking.connect(staker1).claimRewards();
    const balanceAfter = await token.balanceOf(staker1.address);

    expect(balanceAfter).to.be.gt(balanceBefore);
  });

  it("enforces lock period before unstake", async function () {
    const [, staker1] = await ethers.getSigners();

    await staking.connect(staker1).stake(STAKE_AMOUNT, LOCK_30_DAYS);
    await expect(staking.connect(staker1).unstake(STAKE_AMOUNT)).to.be.reverted;

    await time.increase(LOCK_30_DAYS + 1);
    await staking.connect(staker1).unstake(STAKE_AMOUNT);

    const info = await staking.stakes(staker1.address);
    expect(info.amount).to.equal(0n);
  });

  it("gives higher rewards for longer lock multipliers", async function () {
    const [, staker1, staker2] = await ethers.getSigners();

    await staking.connect(staker1).stake(STAKE_AMOUNT, LOCK_30_DAYS);
    await staking.connect(staker2).stake(STAKE_AMOUNT, LOCK_90_DAYS);

    await time.increase(LOCK_30_DAYS + 1);

    const rewards30 = await staking.getRewards(staker1.address);
    const rewards90 = await staking.getRewards(staker2.address);

    expect(rewards90).to.be.gt(rewards30);
  });
});
