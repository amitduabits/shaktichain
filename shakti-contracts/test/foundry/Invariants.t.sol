// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import "../../contracts/ShaktiToken.sol";
import "../../contracts/StakingPool.sol";
import "../../contracts/EnergyAuction.sol";
import "../../contracts/EnergyEscrow.sol";
import "../../contracts/ReputationSystem.sol";

/**
 * @title SHAKTI-CHAIN Invariant Tests
 * @notice Foundry invariant tests for protocol-wide properties
 * @dev Run with: forge test --match-contract InvariantTest -vvv
 */
contract InvariantTest is Test {
    ShaktiToken public token;
    StakingPool public staking;
    EnergyAuction public auction;
    EnergyEscrow public escrow;
    ReputationSystem public reputation;

    address public admin = address(1);
    address public treasury = address(2);
    address[] public actors;

    function setUp() public {
        vm.startPrank(admin);

        // Deploy token
        token = new ShaktiToken(admin, admin);

        // Deploy staking
        staking = new StakingPool(address(token), admin, 800);

        // Deploy auction
        auction = new EnergyAuction(
            address(token),
            address(0),
            admin,
            1e15,  // minPrice
            1e16   // maxPrice
        );

        // Deploy escrow
        escrow = new EnergyEscrow(
            address(token),
            treasury,
            admin,
            200,   // 2% fee
            3000   // 30% burn
        );

        // Deploy reputation
        reputation = new ReputationSystem(admin);

        // Setup actors
        for (uint i = 0; i < 10; i++) {
            address actor = address(uint160(100 + i));
            actors.push(actor);

            // Fund actors
            token.mint(actor, 1_000_000e18);

            // Approve contracts
            vm.stopPrank();
            vm.startPrank(actor);
            token.approve(address(staking), type(uint256).max);
            token.approve(address(auction), type(uint256).max);
            token.approve(address(escrow), type(uint256).max);
            vm.stopPrank();
            vm.startPrank(admin);
        }

        vm.stopPrank();

        // Target contracts for invariant testing
        targetContract(address(token));
        targetContract(address(staking));
        targetContract(address(auction));
        targetContract(address(reputation));
    }

    // ============ Token Invariants ============

    /// @notice Total supply never exceeds MAX_SUPPLY
    function invariant_tokenSupplyCapped() public view {
        assertLe(token.totalSupply(), token.MAX_SUPPLY());
    }

    /// @notice Total supply >= initial supply - burned
    function invariant_tokenSupplyConsistent() public view {
        uint256 totalSupply = token.totalSupply();
        uint256 feesBurned = token.totalFeesBurned();

        // Supply should be consistent with burns
        assertGe(totalSupply + feesBurned, token.INITIAL_SUPPLY());
    }

    // ============ Staking Invariants ============

    /// @notice Contract balance >= total staked
    function invariant_stakingBalanceConsistent() public view {
        uint256 contractBalance = token.balanceOf(address(staking));
        uint256 totalStaked = staking.totalStaked();

        assertGe(contractBalance, totalStaked);
    }

    /// @notice Reward rate never exceeds maximum
    function invariant_stakingRewardRateBounded() public view {
        assertLe(staking.annualRewardRate(), staking.MAX_REWARD_RATE());
    }

    // ============ Auction Invariants ============

    /// @notice Auction state machine validity
    function invariant_auctionStateValid() public view {
        uint256 currentRound = auction.currentRoundId();
        if (currentRound > 0) {
            EnergyAuction.AuctionRound memory round = auction.getAuctionRound(currentRound);
            // State should be one of the valid enum values
            assertTrue(uint(round.state) <= 3);
        }
    }

    // ============ Reputation Invariants ============

    /// @notice All reputation scores bounded
    function invariant_reputationScoresBounded() public view {
        uint256 userCount = reputation.getRegisteredUsersCount();
        for (uint256 i = 0; i < userCount && i < 100; i++) {
            address user = reputation.getRegisteredUser(i);
            (uint256 score, ) = reputation.getReputation(user);
            assertLe(score, reputation.MAX_REPUTATION());
        }
    }

    /// @notice Starting score is correct for new users
    function invariant_reputationStartingScore() public view {
        assertEq(reputation.STARTING_REPUTATION(), 500);
    }

    // ============ Cross-Contract Invariants ============

    /// @notice Total token supply in all contracts <= totalSupply
    function invariant_tokenDistributionConsistent() public view {
        uint256 totalInContracts =
            token.balanceOf(address(staking)) +
            token.balanceOf(address(auction)) +
            token.balanceOf(address(escrow));

        assertLe(totalInContracts, token.totalSupply());
    }
}

/**
 * @title SHAKTI-CHAIN Fuzz Tests
 * @notice Property-based fuzzing tests
 * @dev Run with: forge test --match-contract FuzzTest -vvv
 */
contract FuzzTest is Test {
    ShaktiToken public token;
    StakingPool public staking;

    address public admin = address(1);
    address public user = address(100);

    function setUp() public {
        vm.startPrank(admin);

        token = new ShaktiToken(admin, admin);
        staking = new StakingPool(address(token), admin, 800);

        token.mint(user, 100_000_000e18);

        vm.stopPrank();

        vm.startPrank(user);
        token.approve(address(staking), type(uint256).max);
        vm.stopPrank();
    }

    // ============ Token Fuzz Tests ============

    /// @notice Transfer never creates tokens
    function testFuzz_TransferConservesSupply(
        address to,
        uint256 amount
    ) public {
        vm.assume(to != address(0) && to != user);
        amount = bound(amount, 0, token.balanceOf(user));

        uint256 supplyBefore = token.totalSupply();

        vm.prank(user);
        token.transfer(to, amount);

        uint256 supplyAfter = token.totalSupply();
        assertEq(supplyBefore, supplyAfter);
    }

    /// @notice Mint respects MAX_SUPPLY
    function testFuzz_MintRespectsCap(uint256 amount) public {
        uint256 remainingMintable = token.remainingMintableSupply();
        amount = bound(amount, 1, remainingMintable + 1e18);

        vm.prank(admin);
        if (amount > remainingMintable) {
            vm.expectRevert();
        }
        token.mint(user, amount);
    }

    // ============ Staking Fuzz Tests ============

    /// @notice Stake amount bounds
    function testFuzz_StakeBounds(uint256 amount) public {
        uint256 minStake = staking.MINIMUM_STAKE();
        uint256 balance = token.balanceOf(user);

        amount = bound(amount, 0, balance);

        vm.prank(user);
        if (amount < minStake) {
            vm.expectRevert();
            staking.stake(amount, 0);
        } else {
            staking.stake(amount, 0);
            (uint256 stakedAmount,,,,) = staking.getStakeInfo(user);
            assertEq(stakedAmount, amount);
        }
    }

    /// @notice Unstake never returns more than staked
    function testFuzz_UnstakeRespectsBounds(
        uint256 stakeAmount,
        uint256 unstakeAmount
    ) public {
        uint256 minStake = staking.MINIMUM_STAKE();
        stakeAmount = bound(stakeAmount, minStake, 1_000_000e18);
        unstakeAmount = bound(unstakeAmount, 0, stakeAmount + 1e18);

        vm.prank(user);
        staking.stake(stakeAmount, 0);

        vm.prank(user);
        if (unstakeAmount > stakeAmount) {
            vm.expectRevert();
            staking.unstake(unstakeAmount);
        } else if (unstakeAmount == 0) {
            vm.expectRevert();
            staking.unstake(unstakeAmount);
        } else {
            staking.unstake(unstakeAmount);
            (uint256 remaining,,,,) = staking.getStakeInfo(user);
            assertEq(remaining, stakeAmount - unstakeAmount);
        }
    }

    /// @notice Lock period validity
    function testFuzz_LockPeriodValidity(uint256 lockPeriod) public {
        uint256 minStake = staking.MINIMUM_STAKE();

        vm.prank(user);

        bool isValidLock = (
            lockPeriod == 0 ||
            lockPeriod == staking.LOCK_30_DAYS() ||
            lockPeriod == staking.LOCK_90_DAYS()
        );

        if (!isValidLock) {
            vm.expectRevert();
        }
        staking.stake(minStake, lockPeriod);
    }

    /// @notice Reward calculation doesn't overflow
    function testFuzz_RewardCalculationSafe(
        uint256 stakeAmount,
        uint256 timeElapsed
    ) public {
        uint256 minStake = staking.MINIMUM_STAKE();
        stakeAmount = bound(stakeAmount, minStake, 100_000_000e18);
        timeElapsed = bound(timeElapsed, 0, 365 days * 100); // Up to 100 years

        vm.prank(user);
        staking.stake(stakeAmount, 0);

        vm.warp(block.timestamp + timeElapsed);

        // Should not revert
        uint256 rewards = staking.getRewards(user);
        assertGe(rewards, 0);
    }

    // ============ Edge Case Fuzz Tests ============

    /// @notice Multiple operations in sequence
    function testFuzz_MultipleStakeUnstake(
        uint256 stake1,
        uint256 stake2,
        uint256 unstake1
    ) public {
        uint256 minStake = staking.MINIMUM_STAKE();
        uint256 balance = token.balanceOf(user);

        stake1 = bound(stake1, minStake, balance / 3);
        stake2 = bound(stake2, minStake, balance / 3);
        unstake1 = bound(unstake1, 1, stake1);

        vm.startPrank(user);

        staking.stake(stake1, 0);
        staking.stake(stake2, 0);
        staking.unstake(unstake1);

        (uint256 finalStake,,,,) = staking.getStakeInfo(user);
        assertEq(finalStake, stake1 + stake2 - unstake1);

        vm.stopPrank();
    }
}

/**
 * @title Handler for Invariant Testing
 * @notice Provides bounded actions for invariant testing
 */
contract StakingHandler is Test {
    StakingPool public staking;
    ShaktiToken public token;
    address[] public actors;

    constructor(StakingPool _staking, ShaktiToken _token, address[] memory _actors) {
        staking = _staking;
        token = _token;
        actors = _actors;
    }

    function stake(uint256 actorSeed, uint256 amount) public {
        address actor = actors[actorSeed % actors.length];
        amount = bound(amount, staking.MINIMUM_STAKE(), token.balanceOf(actor));

        if (amount >= staking.MINIMUM_STAKE()) {
            vm.prank(actor);
            try staking.stake(amount, 0) {} catch {}
        }
    }

    function unstake(uint256 actorSeed, uint256 amount) public {
        address actor = actors[actorSeed % actors.length];
        (uint256 stakedAmount,,,,) = staking.getStakeInfo(actor);

        if (stakedAmount > 0) {
            amount = bound(amount, 1, stakedAmount);
            vm.prank(actor);
            try staking.unstake(amount) {} catch {}
        }
    }

    function claimRewards(uint256 actorSeed) public {
        address actor = actors[actorSeed % actors.length];
        vm.prank(actor);
        try staking.claimRewards() {} catch {}
    }

    function warpTime(uint256 timeToWarp) public {
        timeToWarp = bound(timeToWarp, 0, 30 days);
        vm.warp(block.timestamp + timeToWarp);
    }
}
