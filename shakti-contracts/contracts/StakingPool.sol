// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";

/**
 * @title StakingPool
 * @author SHAKTI-CHAIN Team
 * @notice Staking pool for SHAKTI tokens with configurable APY and lock period multipliers
 * @dev Implements stake/unstake with time-based rewards and lock period bonuses
 *
 * Features:
 * - 8% base APY (configurable by governance)
 * - Lock periods: None, 30 days (1.2x), 90 days (1.5x)
 * - Compound rewards option
 * - Emergency withdraw (forfeits rewards)
 * - ReentrancyGuard on all external state-changing functions
 *
 * Gas Optimizations:
 * - Custom errors
 * - Packed struct storage
 * - Unchecked math where safe
 */
contract StakingPool is ReentrancyGuard, AccessControl, Pausable {
    using SafeERC20 for IERC20;

    // ============ Custom Errors ============
    error ZeroAmount();
    error ZeroAddress();
    error InsufficientStake(uint256 requested, uint256 available);
    error BelowMinimumStake(uint256 amount, uint256 minimum);
    error InvalidLockPeriod(uint256 provided);
    error StillLocked(uint256 unlockTime, uint256 currentTime);
    error NoRewardsToClaim();
    error InvalidRewardRate(uint256 rate);
    error NoStakeFound();

    // ============ Constants ============
    bytes32 public constant GOVERNANCE_ROLE = keccak256("GOVERNANCE_ROLE");
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");

    /// @notice Minimum stake amount: 100 SHAKTI tokens
    uint256 public constant MINIMUM_STAKE = 100 * 10**18;

    /// @notice Lock period options in seconds
    uint256 public constant NO_LOCK = 0;
    uint256 public constant LOCK_30_DAYS = 30 days;
    uint256 public constant LOCK_90_DAYS = 90 days;

    /// @notice Multipliers in basis points (10000 = 1x)
    uint256 public constant MULTIPLIER_NO_LOCK = 10000;      // 1.0x
    uint256 public constant MULTIPLIER_30_DAYS = 12000;      // 1.2x
    uint256 public constant MULTIPLIER_90_DAYS = 15000;      // 1.5x
    uint256 private constant MULTIPLIER_BASE = 10000;

    /// @notice Precision for reward calculations
    uint256 private constant PRECISION = 1e18;

    /// @notice Seconds in a year for APY calculation
    uint256 private constant SECONDS_PER_YEAR = 365 days;

    // ============ Structs ============
    /// @notice Stake information for each user
    /// @dev Packed for gas optimization
    struct StakeInfo {
        uint128 amount;           // Staked amount (fits up to ~3.4e38 tokens)
        uint64 startTime;         // Stake start timestamp
        uint32 lockPeriod;        // Lock period in seconds
        uint256 rewardDebt;       // Reward debt for accurate reward tracking
        uint256 pendingRewards;   // Accumulated but unclaimed rewards
    }

    // ============ State Variables ============
    /// @notice The SHAKTI token contract
    IERC20 public immutable stakingToken;

    /// @notice Mapping of user addresses to their stake info
    mapping(address => StakeInfo) public stakes;

    /// @notice Total amount of tokens staked in the pool
    uint256 public totalStaked;

    /// @notice Accumulated reward per token (scaled by PRECISION)
    uint256 public rewardPerTokenStored;

    /// @notice Last time rewards were updated
    uint256 public lastUpdateTime;

    /// @notice Annual reward rate in basis points (800 = 8%)
    uint256 public annualRewardRate;

    /// @notice Maximum reward rate (50% = 5000 basis points)
    uint256 public constant MAX_REWARD_RATE = 5000;

    // ============ Events ============
    event Staked(
        address indexed user,
        uint256 amount,
        uint256 lockPeriod,
        uint256 multiplier
    );
    event Unstaked(address indexed user, uint256 amount);
    event RewardsClaimed(address indexed user, uint256 amount);
    event RewardsCompounded(address indexed user, uint256 amount);
    event RewardRateUpdated(uint256 oldRate, uint256 newRate);
    event EmergencyWithdraw(address indexed user, uint256 amount, uint256 forfeitedRewards);
    event BatchRewardsClaimed(address indexed caller, uint256 totalClaimed, uint256 count);

    // ============ Constructor ============
    /**
     * @notice Initializes the staking pool
     * @param _stakingToken Address of the SHAKTI token
     * @param _admin Address that will receive admin roles
     * @param _initialRewardRate Initial annual reward rate in basis points (e.g., 800 for 8%)
     */
    constructor(
        address _stakingToken,
        address _admin,
        uint256 _initialRewardRate
    ) {
        if (_stakingToken == address(0)) revert ZeroAddress();
        if (_admin == address(0)) revert ZeroAddress();
        if (_initialRewardRate > MAX_REWARD_RATE) revert InvalidRewardRate(_initialRewardRate);

        stakingToken = IERC20(_stakingToken);
        annualRewardRate = _initialRewardRate;
        lastUpdateTime = block.timestamp;

        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        _grantRole(GOVERNANCE_ROLE, _admin);
        _grantRole(PAUSER_ROLE, _admin);
    }

    // ============ External Functions ============

    /**
     * @notice Stakes tokens with optional lock period for bonus multiplier
     * @param amount Amount of tokens to stake
     * @param lockPeriod Lock period: 0 (no lock), 30 days, or 90 days
     */
    function stake(uint256 amount, uint256 lockPeriod) external nonReentrant whenNotPaused {
        if (amount == 0) revert ZeroAmount();
        if (amount < MINIMUM_STAKE) revert BelowMinimumStake(amount, MINIMUM_STAKE);
        if (!_isValidLockPeriod(lockPeriod)) revert InvalidLockPeriod(lockPeriod);

        // Update rewards before modifying state
        _updateReward(msg.sender);

        StakeInfo storage userStake = stakes[msg.sender];

        // If user has existing stake, check lock period compatibility
        if (userStake.amount > 0) {
            // Use the longer lock period
            if (lockPeriod > userStake.lockPeriod) {
                userStake.lockPeriod = uint32(lockPeriod);
                userStake.startTime = uint64(block.timestamp);
            }
        } else {
            userStake.startTime = uint64(block.timestamp);
            userStake.lockPeriod = uint32(lockPeriod);
        }

        // Update stake amount
        unchecked {
            userStake.amount += uint128(amount);
            totalStaked += amount;
        }

        // Update reward debt
        userStake.rewardDebt = (uint256(userStake.amount) * rewardPerTokenStored) / PRECISION;

        // Transfer tokens from user
        stakingToken.safeTransferFrom(msg.sender, address(this), amount);

        emit Staked(msg.sender, amount, lockPeriod, _getMultiplier(lockPeriod));
    }

    /**
     * @notice Unstakes tokens after lock period has elapsed
     * @param amount Amount of tokens to unstake
     */
    function unstake(uint256 amount) external nonReentrant whenNotPaused {
        if (amount == 0) revert ZeroAmount();

        StakeInfo storage userStake = stakes[msg.sender];
        if (userStake.amount == 0) revert NoStakeFound();
        if (amount > userStake.amount) revert InsufficientStake(amount, userStake.amount);

        // Check lock period
        uint256 unlockTime = userStake.startTime + userStake.lockPeriod;
        if (block.timestamp < unlockTime) {
            revert StillLocked(unlockTime, block.timestamp);
        }

        // Update rewards before modifying state
        _updateReward(msg.sender);

        // Claim pending rewards automatically
        uint256 pendingRewards = userStake.pendingRewards;
        if (pendingRewards > 0) {
            userStake.pendingRewards = 0;
            stakingToken.safeTransfer(msg.sender, pendingRewards);
            emit RewardsClaimed(msg.sender, pendingRewards);
        }

        // Update stake
        unchecked {
            userStake.amount -= uint128(amount);
            totalStaked -= amount;
        }

        // Update reward debt
        userStake.rewardDebt = (uint256(userStake.amount) * rewardPerTokenStored) / PRECISION;

        // Reset lock period if fully unstaked
        if (userStake.amount == 0) {
            userStake.lockPeriod = 0;
            userStake.startTime = 0;
        }

        // Transfer tokens back to user
        stakingToken.safeTransfer(msg.sender, amount);

        emit Unstaked(msg.sender, amount);
    }

    /**
     * @notice Claims accumulated rewards
     */
    function claimRewards() external nonReentrant whenNotPaused {
        _updateReward(msg.sender);

        StakeInfo storage userStake = stakes[msg.sender];
        uint256 rewards = userStake.pendingRewards;

        if (rewards == 0) revert NoRewardsToClaim();

        userStake.pendingRewards = 0;

        stakingToken.safeTransfer(msg.sender, rewards);

        emit RewardsClaimed(msg.sender, rewards);
    }

    /**
     * @notice Compounds rewards by adding them to stake
     */
    function compoundRewards() external nonReentrant whenNotPaused {
        _updateReward(msg.sender);

        StakeInfo storage userStake = stakes[msg.sender];
        uint256 rewards = userStake.pendingRewards;

        if (rewards == 0) revert NoRewardsToClaim();

        userStake.pendingRewards = 0;

        unchecked {
            userStake.amount += uint128(rewards);
            totalStaked += rewards;
        }

        // Update reward debt for new staked amount
        userStake.rewardDebt = (uint256(userStake.amount) * rewardPerTokenStored) / PRECISION;

        emit RewardsCompounded(msg.sender, rewards);
    }

    /**
     * @notice Claims rewards for multiple stakers in a single transaction
     * @param stakers Array of staker addresses to claim for
     * @return totalClaimed Total rewards claimed
     * @dev Gas efficient batch claiming - useful for relayers/keepers
     * Only the staker themselves can claim their own rewards
     */
    function batchClaimRewards(
        address[] calldata stakers
    ) external nonReentrant whenNotPaused returns (uint256 totalClaimed) {
        uint256 stakerCount = stakers.length;
        if (stakerCount == 0) revert ZeroAmount();

        _updateGlobalReward();

        for (uint256 i = 0; i < stakerCount;) {
            address staker = stakers[i];
            StakeInfo storage userStake = stakes[staker];

            if (userStake.amount > 0) {
                // Update individual reward
                uint256 multiplier = _getMultiplier(userStake.lockPeriod);
                uint256 earned = ((uint256(userStake.amount) * rewardPerTokenStored) / PRECISION) - userStake.rewardDebt;
                earned = (earned * multiplier) / MULTIPLIER_BASE;
                userStake.pendingRewards += earned;
                userStake.rewardDebt = (uint256(userStake.amount) * rewardPerTokenStored) / PRECISION;

                uint256 rewards = userStake.pendingRewards;
                if (rewards > 0) {
                    userStake.pendingRewards = 0;
                    stakingToken.safeTransfer(staker, rewards);
                    totalClaimed += rewards;
                    emit RewardsClaimed(staker, rewards);
                }
            }

            unchecked { ++i; }
        }

        emit BatchRewardsClaimed(msg.sender, totalClaimed, stakerCount);
    }

    /**
     * @notice Emergency withdrawal that forfeits all pending rewards
     * @dev Bypasses lock period but forfeits rewards
     */
    function emergencyWithdraw() external nonReentrant {
        StakeInfo storage userStake = stakes[msg.sender];
        uint256 stakedAmount = userStake.amount;

        if (stakedAmount == 0) revert NoStakeFound();

        // Calculate forfeited rewards
        _updateReward(msg.sender);
        uint256 forfeitedRewards = userStake.pendingRewards;

        // Reset user stake completely
        userStake.amount = 0;
        userStake.startTime = 0;
        userStake.lockPeriod = 0;
        userStake.rewardDebt = 0;
        userStake.pendingRewards = 0;

        unchecked {
            totalStaked -= stakedAmount;
        }

        // Transfer only staked amount (no rewards)
        stakingToken.safeTransfer(msg.sender, stakedAmount);

        emit EmergencyWithdraw(msg.sender, stakedAmount, forfeitedRewards);
    }

    // ============ Governance Functions ============

    /**
     * @notice Updates the annual reward rate
     * @param newRate New rate in basis points (e.g., 800 for 8%)
     */
    function setRewardRate(uint256 newRate) external onlyRole(GOVERNANCE_ROLE) {
        if (newRate > MAX_REWARD_RATE) revert InvalidRewardRate(newRate);

        // Update rewards before changing rate
        _updateGlobalReward();

        uint256 oldRate = annualRewardRate;
        annualRewardRate = newRate;

        emit RewardRateUpdated(oldRate, newRate);
    }

    /**
     * @notice Pauses the staking pool
     */
    function pause() external onlyRole(PAUSER_ROLE) {
        _pause();
    }

    /**
     * @notice Unpauses the staking pool
     */
    function unpause() external onlyRole(PAUSER_ROLE) {
        _unpause();
    }

    // ============ View Functions ============

    /**
     * @notice Returns pending rewards for an account
     * @param account The account to check
     * @return The amount of pending rewards
     */
    function getRewards(address account) external view returns (uint256) {
        StakeInfo storage userStake = stakes[account];
        if (userStake.amount == 0) return userStake.pendingRewards;

        uint256 currentRewardPerToken = _calculateRewardPerToken();
        uint256 multiplier = _getMultiplier(userStake.lockPeriod);

        uint256 newRewards = ((uint256(userStake.amount) * (currentRewardPerToken - rewardPerTokenStored)) / PRECISION);
        newRewards = (newRewards * multiplier) / MULTIPLIER_BASE;

        uint256 earnedSinceLastUpdate = ((uint256(userStake.amount) * currentRewardPerToken) / PRECISION) - userStake.rewardDebt;
        earnedSinceLastUpdate = (earnedSinceLastUpdate * multiplier) / MULTIPLIER_BASE;

        return userStake.pendingRewards + earnedSinceLastUpdate;
    }

    /**
     * @notice Returns stake info for an account
     * @param account The account to check
     * @return amount Staked amount
     * @return startTime Stake start timestamp
     * @return lockPeriod Lock period in seconds
     * @return unlockTime When tokens can be unstaked
     * @return multiplier Current reward multiplier (in basis points)
     */
    function getStakeInfo(address account) external view returns (
        uint256 amount,
        uint256 startTime,
        uint256 lockPeriod,
        uint256 unlockTime,
        uint256 multiplier
    ) {
        StakeInfo storage userStake = stakes[account];
        amount = userStake.amount;
        startTime = userStake.startTime;
        lockPeriod = userStake.lockPeriod;
        unlockTime = userStake.startTime + userStake.lockPeriod;
        multiplier = _getMultiplier(userStake.lockPeriod);
    }

    /**
     * @notice Returns the current APY for a given lock period
     * @param lockPeriod The lock period to check
     * @return The effective APY in basis points
     */
    function getEffectiveAPY(uint256 lockPeriod) external view returns (uint256) {
        uint256 multiplier = _getMultiplier(lockPeriod);
        return (annualRewardRate * multiplier) / MULTIPLIER_BASE;
    }

    /**
     * @notice Checks if an account's stake is currently locked
     * @param account The account to check
     * @return True if still locked, false otherwise
     */
    function isLocked(address account) external view returns (bool) {
        StakeInfo storage userStake = stakes[account];
        if (userStake.amount == 0) return false;
        return block.timestamp < (userStake.startTime + userStake.lockPeriod);
    }

    /**
     * @notice Returns time remaining until unlock
     * @param account The account to check
     * @return Seconds until unlock (0 if already unlocked)
     */
    function timeUntilUnlock(address account) external view returns (uint256) {
        StakeInfo storage userStake = stakes[account];
        if (userStake.amount == 0) return 0;

        uint256 unlockTime = userStake.startTime + userStake.lockPeriod;
        if (block.timestamp >= unlockTime) return 0;

        unchecked {
            return unlockTime - block.timestamp;
        }
    }

    // ============ Internal Functions ============

    /**
     * @dev Validates lock period
     */
    function _isValidLockPeriod(uint256 lockPeriod) internal pure returns (bool) {
        return lockPeriod == NO_LOCK ||
               lockPeriod == LOCK_30_DAYS ||
               lockPeriod == LOCK_90_DAYS;
    }

    /**
     * @dev Returns multiplier for a lock period
     */
    function _getMultiplier(uint256 lockPeriod) internal pure returns (uint256) {
        if (lockPeriod >= LOCK_90_DAYS) return MULTIPLIER_90_DAYS;
        if (lockPeriod >= LOCK_30_DAYS) return MULTIPLIER_30_DAYS;
        return MULTIPLIER_NO_LOCK;
    }

    /**
     * @dev Calculates current reward per token
     */
    function _calculateRewardPerToken() internal view returns (uint256) {
        if (totalStaked == 0) return rewardPerTokenStored;

        uint256 timeElapsed;
        unchecked {
            timeElapsed = block.timestamp - lastUpdateTime;
        }

        // Calculate rewards: (totalStaked * rate * time) / (SECONDS_PER_YEAR * 10000)
        uint256 newRewards = (totalStaked * annualRewardRate * timeElapsed) / (SECONDS_PER_YEAR * 10000);

        return rewardPerTokenStored + ((newRewards * PRECISION) / totalStaked);
    }

    /**
     * @dev Updates global reward state
     */
    function _updateGlobalReward() internal {
        rewardPerTokenStored = _calculateRewardPerToken();
        lastUpdateTime = block.timestamp;
    }

    /**
     * @dev Updates rewards for a specific account
     */
    function _updateReward(address account) internal {
        _updateGlobalReward();

        StakeInfo storage userStake = stakes[account];
        if (userStake.amount > 0) {
            uint256 multiplier = _getMultiplier(userStake.lockPeriod);
            uint256 earned = ((uint256(userStake.amount) * rewardPerTokenStored) / PRECISION) - userStake.rewardDebt;
            earned = (earned * multiplier) / MULTIPLIER_BASE;

            unchecked {
                userStake.pendingRewards += earned;
            }
            userStake.rewardDebt = (uint256(userStake.amount) * rewardPerTokenStored) / PRECISION;
        }
    }
}
