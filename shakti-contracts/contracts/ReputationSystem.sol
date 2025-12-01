// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";

/**
 * @title ReputationSystem
 * @author SHAKTI-CHAIN Team
 * @notice Trust layer for SHAKTI-CHAIN V2G platform with tiered reputation
 * @dev Manages reputation scores, tier benefits, and fee discounts
 *
 * Reputation Score (0-1000):
 * - Starting score: 500
 * - Successful trade: +5 (max +10 for large trades)
 * - Failed delivery: -50
 * - Dispute lost: -30
 * - Dispute won: +10
 * - Time-weighted decay: -1 per week of inactivity
 *
 * Tiers:
 * - Bronze (0-300): Basic access, higher fees (2.5%)
 * - Silver (300-500): Standard access, standard fees (2%)
 * - Gold (500-700): Priority matching, lower fees (1.5%)
 * - Platinum (700-850): Premium features, lowest fees (1%)
 * - Diamond (850-1000): Governance multiplier, fee rebates
 *
 * Sybil Resistance:
 * - Minimum stake required to build reputation
 * - KYC-verified accounts get 1.5x reputation gains
 * - Suspicious patterns flagged for review
 */
contract ReputationSystem is AccessControl, ReentrancyGuard, Pausable {
    // ============ Custom Errors ============
    error ZeroAddress();
    error UserNotRegistered();
    error UserAlreadyRegistered();
    error InsufficientStake(uint256 required, uint256 actual);
    error InvalidReputationChange();
    error UserFlagged();
    error InvalidTier();
    error UnauthorizedReporter();
    error CooldownNotExpired(uint256 remaining);
    error InvalidMultiplier();

    // ============ Constants ============
    bytes32 public constant REPORTER_ROLE = keccak256("REPORTER_ROLE");
    bytes32 public constant VERIFIER_ROLE = keccak256("VERIFIER_ROLE");
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");

    uint256 public constant BASIS_POINTS = 10000;
    uint256 public constant MAX_REPUTATION = 1000;
    uint256 public constant STARTING_REPUTATION = 500;

    // Reputation changes
    int256 public constant SUCCESSFUL_TRADE_BASE = 5;
    int256 public constant SUCCESSFUL_TRADE_LARGE = 10;
    int256 public constant FAILED_DELIVERY = -50;
    int256 public constant DISPUTE_LOST = -30;
    int256 public constant DISPUTE_WON = 10;
    int256 public constant WEEKLY_DECAY = -1;

    // Tier thresholds
    uint256 public constant BRONZE_MAX = 300;
    uint256 public constant SILVER_MAX = 500;
    uint256 public constant GOLD_MAX = 700;
    uint256 public constant PLATINUM_MAX = 850;
    // Diamond: 850-1000

    // Fee rates in basis points
    uint256 public constant BRONZE_FEE = 250;    // 2.5%
    uint256 public constant SILVER_FEE = 200;    // 2%
    uint256 public constant GOLD_FEE = 150;      // 1.5%
    uint256 public constant PLATINUM_FEE = 100;  // 1%
    uint256 public constant DIAMOND_FEE = 50;    // 0.5% (with rebates)

    // KYC multiplier (1.5x = 150%)
    uint256 public constant KYC_MULTIPLIER = 150;
    uint256 public constant MULTIPLIER_BASE = 100;

    // Time constants
    uint256 public constant DECAY_INTERVAL = 7 days;
    uint256 public constant LARGE_TRADE_THRESHOLD = 100 * 1e18; // 100 kWh

    // Sybil resistance
    uint256 public constant MIN_STAKE_FOR_REPUTATION = 100 * 1e18; // 100 SHAKTI

    // ============ Enums ============
    enum Tier {
        Bronze,
        Silver,
        Gold,
        Platinum,
        Diamond
    }

    enum ReputationType {
        SuccessfulTrade,
        SuccessfulTradeLarge,
        FailedDelivery,
        DisputeLost,
        DisputeWon,
        WeeklyDecay,
        AdminAdjustment,
        FlagPenalty
    }

    // ============ Structs ============
    struct UserReputation {
        uint256 score;
        uint256 totalTrades;
        uint256 successfulTrades;
        uint256 failedTrades;
        uint256 disputesWon;
        uint256 disputesLost;
        uint256 lastActivityTime;
        uint256 registeredAt;
        uint256 stakedAmount;
        bool isKYCVerified;
        bool isFlagged;
        string flagReason;
    }

    struct TierBenefits {
        Tier tier;
        uint256 feeRate;           // In basis points
        uint256 feeDiscount;       // Discount from standard 2% fee
        uint256 transactionLimit;  // Max trade value
        uint256 governanceMultiplier; // Voting power multiplier (100 = 1x)
        bool priorityMatching;
        bool premiumFeatures;
        bool feeRebates;
    }

    struct ReputationChange {
        uint256 timestamp;
        ReputationType changeType;
        int256 delta;
        uint256 newScore;
        string description;
    }

    struct LeaderboardEntry {
        address user;
        uint256 score;
        Tier tier;
    }

    // ============ State Variables ============
    /// @notice Mapping of user address to reputation data
    mapping(address => UserReputation) public userReputations;

    /// @notice Mapping of user address to reputation history
    mapping(address => ReputationChange[]) public reputationHistory;

    /// @notice Mapping of tier to benefits
    mapping(Tier => TierBenefits) public tierBenefits;

    /// @notice Array of registered users
    address[] public registeredUsers;

    /// @notice Mapping to check if user is registered
    mapping(address => bool) public isRegistered;

    /// @notice Connected staking contract for stake verification
    address public stakingContract;

    /// @notice Connected KYC registry for verification
    address public kycRegistry;

    /// @notice Total registered users
    uint256 public totalUsers;

    /// @notice Total reputation points distributed
    uint256 public totalReputationDistributed;

    /// @notice Total reputation points deducted
    uint256 public totalReputationDeducted;

    // ============ Events ============
    event UserRegistered(address indexed user, uint256 initialScore);
    event ReputationUpdated(
        address indexed user,
        int256 delta,
        uint256 newScore,
        Tier newTier,
        ReputationType changeType
    );
    event TierChanged(address indexed user, Tier oldTier, Tier newTier);
    event UserFlaggedEvent(address indexed user, string reason);
    event UserUnflagged(address indexed user);
    event KYCStatusUpdated(address indexed user, bool verified);
    event StakeUpdated(address indexed user, uint256 newStake);
    event DecayApplied(address indexed user, uint256 decayAmount, uint256 newScore);
    event TierBenefitsUpdated(Tier indexed tier, uint256 feeRate, uint256 transactionLimit);

    // ============ Constructor ============
    /**
     * @notice Initializes the ReputationSystem contract
     * @param _admin Admin address
     */
    constructor(address _admin) {
        if (_admin == address(0)) revert ZeroAddress();

        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        _grantRole(VERIFIER_ROLE, _admin);
        _grantRole(PAUSER_ROLE, _admin);

        // Initialize tier benefits
        _initializeTierBenefits();
    }

    // ============ Registration ============

    /**
     * @notice Registers a new user in the reputation system
     * @param user User address to register
     */
    function registerUser(address user) external whenNotPaused {
        if (user == address(0)) revert ZeroAddress();
        if (isRegistered[user]) revert UserAlreadyRegistered();

        isRegistered[user] = true;
        registeredUsers.push(user);
        totalUsers++;

        userReputations[user] = UserReputation({
            score: STARTING_REPUTATION,
            totalTrades: 0,
            successfulTrades: 0,
            failedTrades: 0,
            disputesWon: 0,
            disputesLost: 0,
            lastActivityTime: block.timestamp,
            registeredAt: block.timestamp,
            stakedAmount: 0,
            isKYCVerified: false,
            isFlagged: false,
            flagReason: ""
        });

        // Record initial reputation
        reputationHistory[user].push(ReputationChange({
            timestamp: block.timestamp,
            changeType: ReputationType.AdminAdjustment,
            delta: int256(STARTING_REPUTATION),
            newScore: STARTING_REPUTATION,
            description: "Initial registration"
        }));

        emit UserRegistered(user, STARTING_REPUTATION);
    }

    // ============ Reputation Updates ============

    /**
     * @notice Updates user reputation based on activity
     * @param user User address
     * @param delta Reputation change (positive or negative)
     * @param rtype Type of reputation change
     */
    function updateReputation(
        address user,
        int256 delta,
        ReputationType rtype
    ) external onlyRole(REPORTER_ROLE) nonReentrant whenNotPaused {
        _updateReputation(user, delta, rtype, "");
    }

    /**
     * @notice Updates reputation with description
     * @param user User address
     * @param delta Reputation change
     * @param rtype Type of change
     * @param description Description of the change
     */
    function updateReputationWithDescription(
        address user,
        int256 delta,
        ReputationType rtype,
        string calldata description
    ) external onlyRole(REPORTER_ROLE) nonReentrant whenNotPaused {
        _updateReputation(user, delta, rtype, description);
    }

    /**
     * @notice Records a successful trade
     * @param user User address
     * @param tradeValue Value of the trade
     */
    function recordSuccessfulTrade(
        address user,
        uint256 tradeValue
    ) external onlyRole(REPORTER_ROLE) nonReentrant whenNotPaused {
        if (!isRegistered[user]) revert UserNotRegistered();

        UserReputation storage rep = userReputations[user];
        if (rep.isFlagged) revert UserFlagged();

        // Check stake requirement
        if (rep.stakedAmount < MIN_STAKE_FOR_REPUTATION) {
            revert InsufficientStake(MIN_STAKE_FOR_REPUTATION, rep.stakedAmount);
        }

        // Determine base delta based on trade size
        int256 baseDelta = tradeValue >= LARGE_TRADE_THRESHOLD
            ? SUCCESSFUL_TRADE_LARGE
            : SUCCESSFUL_TRADE_BASE;

        // Apply KYC multiplier if verified
        int256 delta = rep.isKYCVerified
            ? (baseDelta * int256(KYC_MULTIPLIER)) / int256(MULTIPLIER_BASE)
            : baseDelta;

        ReputationType rtype = tradeValue >= LARGE_TRADE_THRESHOLD
            ? ReputationType.SuccessfulTradeLarge
            : ReputationType.SuccessfulTrade;

        rep.totalTrades++;
        rep.successfulTrades++;

        _applyReputationChange(user, delta, rtype, "Successful trade completion");
    }

    /**
     * @notice Records a failed delivery
     * @param user User address (seller who failed to deliver)
     */
    function recordFailedDelivery(
        address user
    ) external onlyRole(REPORTER_ROLE) nonReentrant whenNotPaused {
        if (!isRegistered[user]) revert UserNotRegistered();

        UserReputation storage rep = userReputations[user];
        rep.totalTrades++;
        rep.failedTrades++;

        _applyReputationChange(user, FAILED_DELIVERY, ReputationType.FailedDelivery, "Failed delivery");
    }

    /**
     * @notice Records dispute outcome
     * @param user User address
     * @param won Whether user won the dispute
     */
    function recordDisputeOutcome(
        address user,
        bool won
    ) external onlyRole(REPORTER_ROLE) nonReentrant whenNotPaused {
        if (!isRegistered[user]) revert UserNotRegistered();

        UserReputation storage rep = userReputations[user];

        if (won) {
            rep.disputesWon++;
            _applyReputationChange(user, DISPUTE_WON, ReputationType.DisputeWon, "Dispute won");
        } else {
            rep.disputesLost++;
            _applyReputationChange(user, DISPUTE_LOST, ReputationType.DisputeLost, "Dispute lost");
        }
    }

    /**
     * @notice Applies weekly decay for inactive users
     * @param user User address
     */
    function applyDecay(address user) external nonReentrant whenNotPaused {
        if (!isRegistered[user]) revert UserNotRegistered();

        UserReputation storage rep = userReputations[user];
        uint256 timeSinceActivity = block.timestamp - rep.lastActivityTime;

        if (timeSinceActivity < DECAY_INTERVAL) {
            revert CooldownNotExpired(DECAY_INTERVAL - timeSinceActivity);
        }

        uint256 weeksInactive = timeSinceActivity / DECAY_INTERVAL;
        int256 totalDecay = WEEKLY_DECAY * int256(weeksInactive);

        // Cap decay at -10 per call to prevent abuse
        if (totalDecay < -10) {
            totalDecay = -10;
        }

        _applyReputationChange(user, totalDecay, ReputationType.WeeklyDecay, "Inactivity decay");
    }

    /**
     * @notice Batch apply decay to multiple users
     * @param users Array of user addresses
     */
    function batchApplyDecay(address[] calldata users) external nonReentrant whenNotPaused {
        for (uint256 i = 0; i < users.length; i++) {
            if (isRegistered[users[i]]) {
                UserReputation storage rep = userReputations[users[i]];
                uint256 timeSinceActivity = block.timestamp - rep.lastActivityTime;

                if (timeSinceActivity >= DECAY_INTERVAL) {
                    uint256 weeksInactive = timeSinceActivity / DECAY_INTERVAL;
                    int256 totalDecay = WEEKLY_DECAY * int256(weeksInactive);

                    if (totalDecay < -10) {
                        totalDecay = -10;
                    }

                    _applyReputationChange(users[i], totalDecay, ReputationType.WeeklyDecay, "Batch decay");
                }
            }
        }
    }

    // ============ Internal Functions ============

    function _updateReputation(
        address user,
        int256 delta,
        ReputationType rtype,
        string memory description
    ) internal {
        if (!isRegistered[user]) revert UserNotRegistered();

        UserReputation storage rep = userReputations[user];
        if (rep.isFlagged && delta > 0) revert UserFlagged();

        _applyReputationChange(user, delta, rtype, description);
    }

    function _applyReputationChange(
        address user,
        int256 delta,
        ReputationType rtype,
        string memory description
    ) internal {
        UserReputation storage rep = userReputations[user];
        Tier oldTier = _getTier(rep.score);

        // Calculate new score with bounds
        uint256 newScore;
        if (delta >= 0) {
            newScore = rep.score + uint256(delta);
            if (newScore > MAX_REPUTATION) {
                newScore = MAX_REPUTATION;
            }
            totalReputationDistributed += uint256(delta);
        } else {
            uint256 absDelta = uint256(-delta);
            if (absDelta >= rep.score) {
                newScore = 0;
            } else {
                newScore = rep.score - absDelta;
            }
            totalReputationDeducted += absDelta;
        }

        rep.score = newScore;
        rep.lastActivityTime = block.timestamp;

        // Record in history
        reputationHistory[user].push(ReputationChange({
            timestamp: block.timestamp,
            changeType: rtype,
            delta: delta,
            newScore: newScore,
            description: description
        }));

        Tier newTier = _getTier(newScore);

        emit ReputationUpdated(user, delta, newScore, newTier, rtype);

        if (oldTier != newTier) {
            emit TierChanged(user, oldTier, newTier);
        }
    }

    function _getTier(uint256 score) internal pure returns (Tier) {
        if (score <= BRONZE_MAX) return Tier.Bronze;
        if (score <= SILVER_MAX) return Tier.Silver;
        if (score <= GOLD_MAX) return Tier.Gold;
        if (score <= PLATINUM_MAX) return Tier.Platinum;
        return Tier.Diamond;
    }

    function _initializeTierBenefits() internal {
        // Bronze (0-300)
        tierBenefits[Tier.Bronze] = TierBenefits({
            tier: Tier.Bronze,
            feeRate: BRONZE_FEE,
            feeDiscount: 0,
            transactionLimit: 50 * 1e18,    // 50 kWh
            governanceMultiplier: 100,       // 1x
            priorityMatching: false,
            premiumFeatures: false,
            feeRebates: false
        });

        // Silver (300-500)
        tierBenefits[Tier.Silver] = TierBenefits({
            tier: Tier.Silver,
            feeRate: SILVER_FEE,
            feeDiscount: 50,                 // 0.5% discount
            transactionLimit: 100 * 1e18,    // 100 kWh
            governanceMultiplier: 100,       // 1x
            priorityMatching: false,
            premiumFeatures: false,
            feeRebates: false
        });

        // Gold (500-700)
        tierBenefits[Tier.Gold] = TierBenefits({
            tier: Tier.Gold,
            feeRate: GOLD_FEE,
            feeDiscount: 100,                // 1% discount
            transactionLimit: 250 * 1e18,    // 250 kWh
            governanceMultiplier: 120,       // 1.2x
            priorityMatching: true,
            premiumFeatures: false,
            feeRebates: false
        });

        // Platinum (700-850)
        tierBenefits[Tier.Platinum] = TierBenefits({
            tier: Tier.Platinum,
            feeRate: PLATINUM_FEE,
            feeDiscount: 150,                // 1.5% discount
            transactionLimit: 500 * 1e18,    // 500 kWh
            governanceMultiplier: 150,       // 1.5x
            priorityMatching: true,
            premiumFeatures: true,
            feeRebates: false
        });

        // Diamond (850-1000)
        tierBenefits[Tier.Diamond] = TierBenefits({
            tier: Tier.Diamond,
            feeRate: DIAMOND_FEE,
            feeDiscount: 200,                // 2% discount (with rebates)
            transactionLimit: 1000 * 1e18,   // 1000 kWh
            governanceMultiplier: 200,       // 2x
            priorityMatching: true,
            premiumFeatures: true,
            feeRebates: true
        });
    }

    // ============ Sybil Resistance ============

    /**
     * @notice Updates user's staked amount
     * @param user User address
     * @param amount New staked amount
     */
    function updateStake(
        address user,
        uint256 amount
    ) external onlyRole(REPORTER_ROLE) {
        if (!isRegistered[user]) revert UserNotRegistered();

        userReputations[user].stakedAmount = amount;
        emit StakeUpdated(user, amount);
    }

    /**
     * @notice Updates user's KYC verification status
     * @param user User address
     * @param verified Whether user is KYC verified
     */
    function updateKYCStatus(
        address user,
        bool verified
    ) external onlyRole(VERIFIER_ROLE) {
        if (!isRegistered[user]) revert UserNotRegistered();

        userReputations[user].isKYCVerified = verified;
        emit KYCStatusUpdated(user, verified);
    }

    /**
     * @notice Flags a user for suspicious activity
     * @param user User address
     * @param reason Reason for flagging
     */
    function flagUser(
        address user,
        string calldata reason
    ) external onlyRole(VERIFIER_ROLE) {
        if (!isRegistered[user]) revert UserNotRegistered();

        UserReputation storage rep = userReputations[user];
        rep.isFlagged = true;
        rep.flagReason = reason;

        // Apply penalty
        _applyReputationChange(user, -100, ReputationType.FlagPenalty, reason);

        emit UserFlaggedEvent(user, reason);
    }

    /**
     * @notice Removes flag from user
     * @param user User address
     */
    function unflagUser(address user) external onlyRole(VERIFIER_ROLE) {
        if (!isRegistered[user]) revert UserNotRegistered();

        UserReputation storage rep = userReputations[user];
        rep.isFlagged = false;
        rep.flagReason = "";

        emit UserUnflagged(user);
    }

    // ============ View Functions ============

    /**
     * @notice Gets user reputation and tier
     * @param user User address
     * @return score Current reputation score
     * @return tier Current tier
     */
    function getReputation(address user) external view returns (uint256 score, Tier tier) {
        if (!isRegistered[user]) {
            return (0, Tier.Bronze);
        }

        score = userReputations[user].score;
        tier = _getTier(score);
    }

    /**
     * @notice Gets full user reputation data
     * @param user User address
     * @return UserReputation struct
     */
    function getUserReputation(address user) external view returns (UserReputation memory) {
        return userReputations[user];
    }

    /**
     * @notice Gets tier benefits
     * @param tier Tier to query
     * @return TierBenefits struct
     */
    function getTierBenefits(Tier tier) external view returns (TierBenefits memory) {
        return tierBenefits[tier];
    }

    /**
     * @notice Calculates fee discount for user
     * @param user User address
     * @return discount Fee discount in basis points
     */
    function calculateFeeDiscount(address user) external view returns (uint256 discount) {
        if (!isRegistered[user]) {
            return 0;
        }

        Tier tier = _getTier(userReputations[user].score);
        return tierBenefits[tier].feeDiscount;
    }

    /**
     * @notice Gets effective fee rate for user
     * @param user User address
     * @return feeRate Fee rate in basis points
     */
    function getEffectiveFeeRate(address user) external view returns (uint256 feeRate) {
        if (!isRegistered[user]) {
            return BRONZE_FEE; // Default to highest fee
        }

        Tier tier = _getTier(userReputations[user].score);
        return tierBenefits[tier].feeRate;
    }

    /**
     * @notice Gets user's governance voting multiplier
     * @param user User address
     * @return multiplier Governance multiplier (100 = 1x)
     */
    function getGovernanceMultiplier(address user) external view returns (uint256 multiplier) {
        if (!isRegistered[user]) {
            return 100; // Default 1x
        }

        Tier tier = _getTier(userReputations[user].score);
        return tierBenefits[tier].governanceMultiplier;
    }

    /**
     * @notice Gets user's transaction limit
     * @param user User address
     * @return limit Maximum transaction value
     */
    function getTransactionLimit(address user) external view returns (uint256 limit) {
        if (!isRegistered[user]) {
            return tierBenefits[Tier.Bronze].transactionLimit;
        }

        Tier tier = _getTier(userReputations[user].score);
        return tierBenefits[tier].transactionLimit;
    }

    /**
     * @notice Checks if user has priority matching
     * @param user User address
     * @return hasPriority True if user has priority matching
     */
    function hasPriorityMatching(address user) external view returns (bool hasPriority) {
        if (!isRegistered[user]) {
            return false;
        }

        Tier tier = _getTier(userReputations[user].score);
        return tierBenefits[tier].priorityMatching;
    }

    /**
     * @notice Gets user's reputation history
     * @param user User address
     * @return Array of reputation changes
     */
    function getReputationHistory(address user) external view returns (ReputationChange[] memory) {
        return reputationHistory[user];
    }

    /**
     * @notice Gets reputation history length
     * @param user User address
     * @return Number of history entries
     */
    function getReputationHistoryLength(address user) external view returns (uint256) {
        return reputationHistory[user].length;
    }

    /**
     * @notice Gets specific history entry
     * @param user User address
     * @param index History index
     * @return ReputationChange at index
     */
    function getReputationHistoryAt(
        address user,
        uint256 index
    ) external view returns (ReputationChange memory) {
        return reputationHistory[user][index];
    }

    /**
     * @notice Compares two users for auction priority
     * @param user1 First user
     * @param user2 Second user
     * @return winner Address of user with priority (higher reputation)
     */
    function compareForPriority(
        address user1,
        address user2
    ) external view returns (address winner) {
        uint256 score1 = isRegistered[user1] ? userReputations[user1].score : 0;
        uint256 score2 = isRegistered[user2] ? userReputations[user2].score : 0;

        // Higher score wins, tie goes to user1 (first in)
        return score1 >= score2 ? user1 : user2;
    }

    /**
     * @notice Gets leaderboard (top N users)
     * @param count Number of users to return
     * @return Array of leaderboard entries
     */
    function getLeaderboard(uint256 count) external view returns (LeaderboardEntry[] memory) {
        uint256 resultCount = count > registeredUsers.length ? registeredUsers.length : count;
        LeaderboardEntry[] memory entries = new LeaderboardEntry[](resultCount);

        // Simple insertion sort for top N (good enough for reasonable N)
        for (uint256 i = 0; i < registeredUsers.length; i++) {
            address user = registeredUsers[i];
            uint256 score = userReputations[user].score;

            // Find position in sorted array
            for (uint256 j = 0; j < resultCount; j++) {
                if (score > entries[j].score) {
                    // Shift lower scores down
                    for (uint256 k = resultCount - 1; k > j; k--) {
                        entries[k] = entries[k - 1];
                    }
                    entries[j] = LeaderboardEntry({
                        user: user,
                        score: score,
                        tier: _getTier(score)
                    });
                    break;
                }
            }
        }

        return entries;
    }

    /**
     * @notice Gets all registered users count
     * @return Total number of registered users
     */
    function getRegisteredUsersCount() external view returns (uint256) {
        return registeredUsers.length;
    }

    /**
     * @notice Gets user at index
     * @param index User index
     * @return User address
     */
    function getRegisteredUser(uint256 index) external view returns (address) {
        return registeredUsers[index];
    }

    /**
     * @notice Gets system statistics
     * @return users Total registered users
     * @return distributed Total reputation distributed
     * @return deducted Total reputation deducted
     */
    function getSystemStats() external view returns (
        uint256 users,
        uint256 distributed,
        uint256 deducted
    ) {
        return (totalUsers, totalReputationDistributed, totalReputationDeducted);
    }

    /**
     * @notice Gets tier distribution
     * @return bronze Number of Bronze users
     * @return silver Number of Silver users
     * @return gold Number of Gold users
     * @return platinum Number of Platinum users
     * @return diamond Number of Diamond users
     */
    function getTierDistribution() external view returns (
        uint256 bronze,
        uint256 silver,
        uint256 gold,
        uint256 platinum,
        uint256 diamond
    ) {
        for (uint256 i = 0; i < registeredUsers.length; i++) {
            Tier tier = _getTier(userReputations[registeredUsers[i]].score);
            if (tier == Tier.Bronze) bronze++;
            else if (tier == Tier.Silver) silver++;
            else if (tier == Tier.Gold) gold++;
            else if (tier == Tier.Platinum) platinum++;
            else diamond++;
        }
    }

    /**
     * @notice Checks if user can build reputation (has minimum stake)
     * @param user User address
     * @return canBuild True if user meets stake requirement
     */
    function canBuildReputation(address user) external view returns (bool canBuild) {
        if (!isRegistered[user]) return false;
        return userReputations[user].stakedAmount >= MIN_STAKE_FOR_REPUTATION;
    }

    /**
     * @notice Gets time since last activity
     * @param user User address
     * @return seconds Time since last activity
     */
    function getTimeSinceLastActivity(address user) external view returns (uint256) {
        if (!isRegistered[user]) return 0;
        return block.timestamp - userReputations[user].lastActivityTime;
    }

    /**
     * @notice Calculates pending decay for user
     * @param user User address
     * @return decay Pending decay amount (absolute value)
     */
    function getPendingDecay(address user) external view returns (uint256 decay) {
        if (!isRegistered[user]) return 0;

        uint256 timeSinceActivity = block.timestamp - userReputations[user].lastActivityTime;
        if (timeSinceActivity < DECAY_INTERVAL) return 0;

        uint256 weeksInactive = timeSinceActivity / DECAY_INTERVAL;
        decay = weeksInactive; // 1 point per week
        if (decay > 10) decay = 10; // Cap at 10
    }

    // ============ Admin Functions ============

    /**
     * @notice Updates tier benefits
     * @param tier Tier to update
     * @param feeRate New fee rate
     * @param transactionLimit New transaction limit
     * @param governanceMultiplier New governance multiplier
     */
    function updateTierBenefits(
        Tier tier,
        uint256 feeRate,
        uint256 transactionLimit,
        uint256 governanceMultiplier
    ) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (feeRate > 500) revert InvalidMultiplier(); // Max 5%
        if (governanceMultiplier > 300) revert InvalidMultiplier(); // Max 3x

        TierBenefits storage benefits = tierBenefits[tier];
        benefits.feeRate = feeRate;
        benefits.transactionLimit = transactionLimit;
        benefits.governanceMultiplier = governanceMultiplier;

        emit TierBenefitsUpdated(tier, feeRate, transactionLimit);
    }

    /**
     * @notice Sets staking contract address
     * @param _stakingContract New staking contract
     */
    function setStakingContract(address _stakingContract) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (_stakingContract == address(0)) revert ZeroAddress();
        stakingContract = _stakingContract;
        _grantRole(REPORTER_ROLE, _stakingContract);
    }

    /**
     * @notice Sets KYC registry address
     * @param _kycRegistry New KYC registry
     */
    function setKYCRegistry(address _kycRegistry) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (_kycRegistry == address(0)) revert ZeroAddress();
        kycRegistry = _kycRegistry;
    }

    /**
     * @notice Grants reporter role to a contract
     * @param reporter Address to grant role
     */
    function grantReporterRole(address reporter) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (reporter == address(0)) revert ZeroAddress();
        _grantRole(REPORTER_ROLE, reporter);
    }

    /**
     * @notice Revokes reporter role from a contract
     * @param reporter Address to revoke role from
     */
    function revokeReporterRole(address reporter) external onlyRole(DEFAULT_ADMIN_ROLE) {
        _revokeRole(REPORTER_ROLE, reporter);
    }

    /**
     * @notice Admin adjustment of reputation
     * @param user User address
     * @param delta Reputation change
     * @param reason Reason for adjustment
     */
    function adminAdjustReputation(
        address user,
        int256 delta,
        string calldata reason
    ) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (!isRegistered[user]) revert UserNotRegistered();
        _applyReputationChange(user, delta, ReputationType.AdminAdjustment, reason);
    }

    /**
     * @notice Pauses the contract
     */
    function pause() external onlyRole(PAUSER_ROLE) {
        _pause();
    }

    /**
     * @notice Unpauses the contract
     */
    function unpause() external onlyRole(PAUSER_ROLE) {
        _unpause();
    }
}
