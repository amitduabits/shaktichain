// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Initializable} from "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import {AccessControlUpgradeable} from "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import {PausableUpgradeable} from "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";
import {UUPSUpgradeable} from "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";

/**
 * @title ReputationSystemUpgradeable
 * @author SHAKTI-CHAIN Team
 * @notice UUPS Upgradeable reputation system for V2G platform trust layer
 * @dev Tiered reputation with decay, sybil resistance, and governance integration
 *
 * Features:
 * - Score 0-1000, starting at 500
 * - 5 tiers: Bronze, Silver, Gold, Platinum, Diamond
 * - Weekly decay for inactivity
 * - Sybil resistance via staking + KYC
 * - Governance multiplier for voting power
 * - UUPS upgradeable pattern
 */
contract ReputationSystemUpgradeable is
    Initializable,
    AccessControlUpgradeable,
    PausableUpgradeable,
    UUPSUpgradeable
{
    // ============ Custom Errors ============
    error ZeroAddress();
    error UserAlreadyRegistered(address user);
    error UserNotRegistered(address user);
    error InsufficientStake(uint256 required, uint256 available);
    error DecayCooldownNotExpired(uint256 nextDecayTime);
    error UserFlagged(address user);
    error InvalidTier(uint8 tier);
    error InvalidFeeRate(uint256 rate);
    error InvalidMultiplier(uint256 multiplier);

    // ============ Constants ============
    bytes32 public constant REPORTER_ROLE = keccak256("REPORTER_ROLE");
    bytes32 public constant TRADE_REPORTER_ROLE = keccak256("TRADE_REPORTER_ROLE");
    bytes32 public constant KYC_VERIFIER_ROLE = keccak256("KYC_VERIFIER_ROLE");
    bytes32 public constant UPGRADER_ROLE = keccak256("UPGRADER_ROLE");

    uint256 public constant MAX_REPUTATION = 1000;
    uint256 public constant STARTING_REPUTATION = 500;

    uint256 public constant BRONZE_MAX = 300;
    uint256 public constant SILVER_MAX = 500;
    uint256 public constant GOLD_MAX = 700;
    uint256 public constant PLATINUM_MAX = 850;

    uint256 public constant SUCCESSFUL_TRADE_GAIN = 5;
    uint256 public constant LARGE_TRADE_BONUS = 5;
    uint256 public constant FAILED_DELIVERY_PENALTY = 50;
    uint256 public constant DISPUTE_WON_GAIN = 10;
    uint256 public constant DISPUTE_LOST_PENALTY = 30;

    uint256 public constant DECAY_PER_WEEK = 1;
    uint256 public constant MAX_DECAY_WEEKS = 10;
    uint256 public constant DECAY_COOLDOWN = 7 days;

    uint256 public constant LARGE_TRADE_THRESHOLD = 10000 * 1e18;
    uint256 public constant MIN_STAKE_FOR_REPUTATION = 100 * 1e18;
    uint256 public constant KYC_MULTIPLIER = 150;
    uint256 public constant MULTIPLIER_BASE = 100;

    uint256 public constant BRONZE_FEE = 250;
    uint256 public constant SILVER_FEE = 200;
    uint256 public constant GOLD_FEE = 150;
    uint256 public constant PLATINUM_FEE = 100;
    uint256 public constant DIAMOND_FEE = 50;

    // ============ Enums ============
    enum Tier { BRONZE, SILVER, GOLD, PLATINUM, DIAMOND }

    // ============ Structs ============
    struct UserReputation {
        uint256 score;
        Tier tier;
        uint256 totalTrades;
        uint256 successfulTrades;
        uint256 failedDeliveries;
        uint256 disputesWon;
        uint256 disputesLost;
        uint256 lastActivityTime;
        uint256 lastDecayTime;
        uint256 registrationTime;
        bool isKYCVerified;
        bool isFlagged;
        uint256 stakedAmount;
    }

    struct TierBenefits {
        uint256 feeRate;
        uint256 maxTransactionLimit;
        uint256 priorityMatchingEnabled;
        uint256 governanceMultiplier;
    }

    struct ReputationChange {
        uint256 timestamp;
        int256 change;
        string reason;
    }

    // ============ State Variables ============
    mapping(address => UserReputation) public userReputations;
    mapping(address => ReputationChange[]) public reputationHistory;
    mapping(Tier => TierBenefits) public tierBenefits;

    address[] public registeredUsers;
    address public stakingContract;
    address public kycRegistry;

    uint256 public totalUsers;
    uint256 public totalReputationPoints;

    // ============ Storage Gap ============
    uint256[40] private __gap;

    // ============ Events ============
    event UserRegistered(address indexed user, uint256 initialReputation, Tier tier);
    event ReputationUpdated(address indexed user, uint256 oldScore, uint256 newScore, string reason);
    event TierChanged(address indexed user, Tier oldTier, Tier newTier);
    event DecayApplied(address indexed user, uint256 decayAmount, uint256 weeksInactive);
    event UserFlaggedEvent(address indexed user, address indexed reporter, string reason);
    event UserUnflagged(address indexed user, address indexed admin);
    event StakeUpdated(address indexed user, uint256 oldStake, uint256 newStake);
    event KYCStatusUpdated(address indexed user, bool verified);
    event TierBenefitsUpdated(Tier tier, uint256 feeRate, uint256 governanceMultiplier);

    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }

    /**
     * @notice Initializes the reputation system
     */
    function initialize(address _admin) public initializer {
        if (_admin == address(0)) revert ZeroAddress();

        __AccessControl_init();
        __Pausable_init();
        __UUPSUpgradeable_init();

        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        _grantRole(REPORTER_ROLE, _admin);
        _grantRole(TRADE_REPORTER_ROLE, _admin);
        _grantRole(KYC_VERIFIER_ROLE, _admin);
        _grantRole(UPGRADER_ROLE, _admin);

        _initializeTierBenefits();
    }

    // ============ Registration ============

    function registerUser(address user) external whenNotPaused onlyRole(TRADE_REPORTER_ROLE) {
        if (user == address(0)) revert ZeroAddress();
        if (userReputations[user].registrationTime != 0) revert UserAlreadyRegistered(user);

        userReputations[user] = UserReputation({
            score: STARTING_REPUTATION,
            tier: Tier.SILVER,
            totalTrades: 0,
            successfulTrades: 0,
            failedDeliveries: 0,
            disputesWon: 0,
            disputesLost: 0,
            lastActivityTime: block.timestamp,
            lastDecayTime: block.timestamp,
            registrationTime: block.timestamp,
            isKYCVerified: false,
            isFlagged: false,
            stakedAmount: 0
        });

        registeredUsers.push(user);
        totalUsers++;
        totalReputationPoints += STARTING_REPUTATION;

        reputationHistory[user].push(ReputationChange({
            timestamp: block.timestamp,
            change: int256(STARTING_REPUTATION),
            reason: "Initial registration"
        }));

        emit UserRegistered(user, STARTING_REPUTATION, Tier.SILVER);
    }

    // ============ Reputation Updates ============

    function recordSuccessfulTrade(
        address user,
        uint256 tradeValue
    ) external whenNotPaused onlyRole(TRADE_REPORTER_ROLE) {
        _validateUser(user);
        _checkStakeRequirement(user);

        uint256 gain = SUCCESSFUL_TRADE_GAIN;
        if (tradeValue >= LARGE_TRADE_THRESHOLD) {
            gain += LARGE_TRADE_BONUS;
        }

        if (userReputations[user].isKYCVerified) {
            gain = (gain * KYC_MULTIPLIER) / MULTIPLIER_BASE;
        }

        _updateReputation(user, int256(gain), "Successful trade");

        userReputations[user].totalTrades++;
        userReputations[user].successfulTrades++;
        userReputations[user].lastActivityTime = block.timestamp;
    }

    function recordFailedDelivery(address user) external whenNotPaused onlyRole(TRADE_REPORTER_ROLE) {
        _validateUser(user);

        _updateReputation(user, -int256(FAILED_DELIVERY_PENALTY), "Failed delivery");

        userReputations[user].totalTrades++;
        userReputations[user].failedDeliveries++;
        userReputations[user].lastActivityTime = block.timestamp;
    }

    function recordDisputeWon(address user) external whenNotPaused onlyRole(TRADE_REPORTER_ROLE) {
        _validateUser(user);

        _updateReputation(user, int256(DISPUTE_WON_GAIN), "Dispute won");
        userReputations[user].disputesWon++;
        userReputations[user].lastActivityTime = block.timestamp;
    }

    function recordDisputeLost(address user) external whenNotPaused onlyRole(TRADE_REPORTER_ROLE) {
        _validateUser(user);

        _updateReputation(user, -int256(DISPUTE_LOST_PENALTY), "Dispute lost");
        userReputations[user].disputesLost++;
        userReputations[user].lastActivityTime = block.timestamp;
    }

    // ============ Decay ============

    function applyDecay(address user) external whenNotPaused {
        _validateUser(user);

        UserReputation storage rep = userReputations[user];

        if (block.timestamp < rep.lastDecayTime + DECAY_COOLDOWN) {
            revert DecayCooldownNotExpired(rep.lastDecayTime + DECAY_COOLDOWN);
        }

        uint256 weeksInactive = (block.timestamp - rep.lastActivityTime) / DECAY_COOLDOWN;
        if (weeksInactive == 0) {
            weeksInactive = 1;
        }
        if (weeksInactive > MAX_DECAY_WEEKS) {
            weeksInactive = MAX_DECAY_WEEKS;
        }

        uint256 decayAmount = DECAY_PER_WEEK * weeksInactive;
        if (decayAmount > rep.score) {
            decayAmount = rep.score;
        }

        _updateReputation(user, -int256(decayAmount), "Weekly inactivity decay");
        rep.lastDecayTime = block.timestamp;

        emit DecayApplied(user, decayAmount, weeksInactive);
    }

    function batchApplyDecay(address[] calldata users) external whenNotPaused {
        for (uint256 i = 0; i < users.length;) {
            address user = users[i];
            UserReputation storage rep = userReputations[user];

            if (rep.registrationTime != 0 && block.timestamp >= rep.lastDecayTime + DECAY_COOLDOWN) {
                uint256 weeksInactive = (block.timestamp - rep.lastActivityTime) / DECAY_COOLDOWN;
                if (weeksInactive == 0) weeksInactive = 1;
                if (weeksInactive > MAX_DECAY_WEEKS) weeksInactive = MAX_DECAY_WEEKS;

                uint256 decayAmount = DECAY_PER_WEEK * weeksInactive;
                if (decayAmount > rep.score) decayAmount = rep.score;

                _updateReputation(user, -int256(decayAmount), "Weekly inactivity decay");
                rep.lastDecayTime = block.timestamp;

                emit DecayApplied(user, decayAmount, weeksInactive);
            }

            unchecked { ++i; }
        }
    }

    // ============ Sybil Resistance ============

    function updateStake(address user, uint256 newStake) external whenNotPaused onlyRole(TRADE_REPORTER_ROLE) {
        if (userReputations[user].registrationTime == 0) revert UserNotRegistered(user);

        uint256 oldStake = userReputations[user].stakedAmount;
        userReputations[user].stakedAmount = newStake;

        emit StakeUpdated(user, oldStake, newStake);
    }

    function setKYCStatus(address user, bool verified) external whenNotPaused onlyRole(KYC_VERIFIER_ROLE) {
        if (userReputations[user].registrationTime == 0) revert UserNotRegistered(user);

        userReputations[user].isKYCVerified = verified;
        emit KYCStatusUpdated(user, verified);
    }

    // ============ Flagging ============

    function flagUser(address user, string calldata reason) external whenNotPaused onlyRole(REPORTER_ROLE) {
        if (userReputations[user].registrationTime == 0) revert UserNotRegistered(user);

        userReputations[user].isFlagged = true;
        _updateReputation(user, -int256(DISPUTE_LOST_PENALTY), "Flagged for suspicious activity");

        emit UserFlaggedEvent(user, msg.sender, reason);
    }

    function unflagUser(address user) external whenNotPaused onlyRole(DEFAULT_ADMIN_ROLE) {
        if (userReputations[user].registrationTime == 0) revert UserNotRegistered(user);

        userReputations[user].isFlagged = false;
        emit UserUnflagged(user, msg.sender);
    }

    // ============ View Functions ============

    function getReputation(address user) external view returns (UserReputation memory) {
        return userReputations[user];
    }

    function getTier(address user) external view returns (Tier) {
        return userReputations[user].tier;
    }

    function getScore(address user) external view returns (uint256) {
        return userReputations[user].score;
    }

    function getFeeRate(address user) external view returns (uint256) {
        if (userReputations[user].registrationTime == 0) {
            return BRONZE_FEE;
        }
        return tierBenefits[userReputations[user].tier].feeRate;
    }

    function getFeeDiscount(address user) external view returns (uint256) {
        if (userReputations[user].registrationTime == 0) return 0;
        uint256 baseFee = BRONZE_FEE;
        uint256 currentFee = tierBenefits[userReputations[user].tier].feeRate;
        return baseFee - currentFee;
    }

    function getGovernanceMultiplier(address user) external view returns (uint256) {
        if (userReputations[user].registrationTime == 0) return 100;
        return tierBenefits[userReputations[user].tier].governanceMultiplier;
    }

    function hasPriorityMatching(address user) external view returns (bool) {
        if (userReputations[user].registrationTime == 0) return false;
        return tierBenefits[userReputations[user].tier].priorityMatchingEnabled == 1;
    }

    function canBuildReputation(address user) external view returns (bool hasMinStake, bool isKYC, bool notFlagged) {
        UserReputation storage rep = userReputations[user];
        hasMinStake = rep.stakedAmount >= MIN_STAKE_FOR_REPUTATION;
        isKYC = rep.isKYCVerified;
        notFlagged = !rep.isFlagged;
    }

    function getPendingDecay(address user) external view returns (uint256) {
        UserReputation storage rep = userReputations[user];
        if (rep.registrationTime == 0) return 0;
        if (block.timestamp < rep.lastDecayTime + DECAY_COOLDOWN) return 0;

        uint256 weeksInactive = (block.timestamp - rep.lastActivityTime) / DECAY_COOLDOWN;
        if (weeksInactive == 0) weeksInactive = 1;
        if (weeksInactive > MAX_DECAY_WEEKS) weeksInactive = MAX_DECAY_WEEKS;

        return DECAY_PER_WEEK * weeksInactive;
    }

    function comparePriority(address user1, address user2) external view returns (int256) {
        uint256 score1 = userReputations[user1].registrationTime != 0 ? userReputations[user1].score : 0;
        uint256 score2 = userReputations[user2].registrationTime != 0 ? userReputations[user2].score : 0;

        if (score1 > score2) return 1;
        if (score1 < score2) return -1;
        return 0;
    }

    function getTopUsers(uint256 count) external view returns (address[] memory, uint256[] memory, Tier[] memory) {
        uint256 resultCount = count > totalUsers ? totalUsers : count;

        address[] memory topAddresses = new address[](resultCount);
        uint256[] memory topScores = new uint256[](resultCount);
        Tier[] memory topTiers = new Tier[](resultCount);

        address[] memory tempAddresses = new address[](totalUsers);
        uint256[] memory tempScores = new uint256[](totalUsers);

        for (uint256 i = 0; i < totalUsers; i++) {
            tempAddresses[i] = registeredUsers[i];
            tempScores[i] = userReputations[registeredUsers[i]].score;
        }

        for (uint256 i = 0; i < resultCount; i++) {
            uint256 maxIdx = i;
            for (uint256 j = i + 1; j < totalUsers; j++) {
                if (tempScores[j] > tempScores[maxIdx]) {
                    maxIdx = j;
                }
            }

            if (maxIdx != i) {
                (tempAddresses[i], tempAddresses[maxIdx]) = (tempAddresses[maxIdx], tempAddresses[i]);
                (tempScores[i], tempScores[maxIdx]) = (tempScores[maxIdx], tempScores[i]);
            }

            topAddresses[i] = tempAddresses[i];
            topScores[i] = tempScores[i];
            topTiers[i] = userReputations[tempAddresses[i]].tier;
        }

        return (topAddresses, topScores, topTiers);
    }

    function getReputationHistory(address user) external view returns (ReputationChange[] memory) {
        return reputationHistory[user];
    }

    function getSystemStats() external view returns (
        uint256 users, uint256 totalPoints, uint256 averageScore
    ) {
        users = totalUsers;
        totalPoints = totalReputationPoints;
        averageScore = totalUsers > 0 ? totalReputationPoints / totalUsers : 0;
    }

    function getTierDistribution() external view returns (uint256[5] memory) {
        uint256[5] memory distribution;

        for (uint256 i = 0; i < totalUsers; i++) {
            Tier tier = userReputations[registeredUsers[i]].tier;
            distribution[uint256(tier)]++;
        }

        return distribution;
    }

    function version() external pure returns (string memory) {
        return "1.0.0";
    }

    // ============ Admin Functions ============

    function adminAdjustReputation(
        address user,
        int256 adjustment,
        string calldata reason
    ) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (userReputations[user].registrationTime == 0) revert UserNotRegistered(user);
        _updateReputation(user, adjustment, reason);
    }

    function updateTierBenefits(
        Tier tier,
        uint256 feeRate,
        uint256 maxTxLimit,
        uint256 priorityEnabled,
        uint256 govMultiplier
    ) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (feeRate > 500) revert InvalidFeeRate(feeRate);
        if (govMultiplier > 300) revert InvalidMultiplier(govMultiplier);

        tierBenefits[tier] = TierBenefits({
            feeRate: feeRate,
            maxTransactionLimit: maxTxLimit,
            priorityMatchingEnabled: priorityEnabled,
            governanceMultiplier: govMultiplier
        });

        emit TierBenefitsUpdated(tier, feeRate, govMultiplier);
    }

    function setStakingContract(address _stakingContract) external onlyRole(DEFAULT_ADMIN_ROLE) {
        stakingContract = _stakingContract;
    }

    function setKYCRegistry(address _kycRegistry) external onlyRole(DEFAULT_ADMIN_ROLE) {
        kycRegistry = _kycRegistry;
    }

    function pause() external onlyRole(DEFAULT_ADMIN_ROLE) { _pause(); }
    function unpause() external onlyRole(DEFAULT_ADMIN_ROLE) { _unpause(); }

    // ============ Internal Functions ============

    function _validateUser(address user) internal view {
        if (userReputations[user].registrationTime == 0) revert UserNotRegistered(user);
        if (userReputations[user].isFlagged) revert UserFlagged(user);
    }

    function _checkStakeRequirement(address user) internal view {
        if (userReputations[user].stakedAmount < MIN_STAKE_FOR_REPUTATION) {
            revert InsufficientStake(MIN_STAKE_FOR_REPUTATION, userReputations[user].stakedAmount);
        }
    }

    function _updateReputation(address user, int256 change, string memory reason) internal {
        UserReputation storage rep = userReputations[user];
        uint256 oldScore = rep.score;

        if (change > 0) {
            uint256 newScore = oldScore + uint256(change);
            rep.score = newScore > MAX_REPUTATION ? MAX_REPUTATION : newScore;
        } else {
            uint256 penalty = uint256(-change);
            rep.score = penalty > oldScore ? 0 : oldScore - penalty;
        }

        totalReputationPoints = totalReputationPoints - oldScore + rep.score;

        Tier oldTier = rep.tier;
        Tier newTier = _calculateTier(rep.score);

        if (newTier != oldTier) {
            rep.tier = newTier;
            emit TierChanged(user, oldTier, newTier);
        }

        reputationHistory[user].push(ReputationChange({
            timestamp: block.timestamp,
            change: change,
            reason: reason
        }));

        emit ReputationUpdated(user, oldScore, rep.score, reason);
    }

    function _calculateTier(uint256 score) internal pure returns (Tier) {
        if (score > PLATINUM_MAX) return Tier.DIAMOND;
        if (score > GOLD_MAX) return Tier.PLATINUM;
        if (score > SILVER_MAX) return Tier.GOLD;
        if (score > BRONZE_MAX) return Tier.SILVER;
        return Tier.BRONZE;
    }

    function _initializeTierBenefits() internal {
        tierBenefits[Tier.BRONZE] = TierBenefits({
            feeRate: BRONZE_FEE,
            maxTransactionLimit: 1000 * 1e18,
            priorityMatchingEnabled: 0,
            governanceMultiplier: 100
        });

        tierBenefits[Tier.SILVER] = TierBenefits({
            feeRate: SILVER_FEE,
            maxTransactionLimit: 5000 * 1e18,
            priorityMatchingEnabled: 0,
            governanceMultiplier: 110
        });

        tierBenefits[Tier.GOLD] = TierBenefits({
            feeRate: GOLD_FEE,
            maxTransactionLimit: 10000 * 1e18,
            priorityMatchingEnabled: 1,
            governanceMultiplier: 130
        });

        tierBenefits[Tier.PLATINUM] = TierBenefits({
            feeRate: PLATINUM_FEE,
            maxTransactionLimit: 50000 * 1e18,
            priorityMatchingEnabled: 1,
            governanceMultiplier: 150
        });

        tierBenefits[Tier.DIAMOND] = TierBenefits({
            feeRate: DIAMOND_FEE,
            maxTransactionLimit: type(uint256).max,
            priorityMatchingEnabled: 1,
            governanceMultiplier: 200
        });
    }

    function _authorizeUpgrade(address newImplementation) internal override onlyRole(UPGRADER_ROLE) {}
}
