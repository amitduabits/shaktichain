// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";
import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import {MessageHashUtils} from "@openzeppelin/contracts/utils/cryptography/MessageHashUtils.sol";

/**
 * @title EnergyVerification
 * @author SHAKTI-CHAIN Team
 * @notice Delivery verification contract for V2G energy trades
 * @dev Implements multiple verification methods with slashing for non-delivery
 *
 * Verification Flow:
 * 1. Trade matched in auction
 * 2. Seller has 4 hours to deliver energy
 * 3. Smart meter reports delivery to DISCOM
 * 4. DISCOM attests delivery on-chain
 * 5. Settlement releases funds
 *
 * Verification Methods:
 * 1. DISCOM Attestation (Primary) - Signed attestation from trusted DISCOM
 * 2. Smart Meter Oracle (Secondary) - Chainlink Functions reads meter API
 * 3. Peer Attestation (Backup) - Buyer confirms for small trades < 10 kWh
 *
 * Slashing:
 * - Non-delivery: 10% of trade value slashed from seller
 * - False dispute: 5% slashed from buyer
 * - Repeated offenses: Temporary/permanent ban
 */
contract EnergyVerification is AccessControl, ReentrancyGuard, Pausable {
    using ECDSA for bytes32;
    using MessageHashUtils for bytes32;

    // ============ Custom Errors ============
    error ZeroAddress();
    error ZeroAmount();
    error InvalidTradeId();
    error TradeAlreadyExists();
    error TradeNotFound();
    error DeliveryAlreadyReported();
    error DeliveryAlreadyConfirmed();
    error DeliveryAlreadyDisputed();
    error DeliveryNotPending();
    error DeliveryWindowExpired();
    error DeliveryWindowNotExpired();
    error InvalidSignature();
    error UntrustedDISCOM();
    error NotBuyer();
    error NotSeller();
    error NotParty();
    error QuantityMismatch(uint256 expected, uint256 delivered, uint256 tolerance);
    error TradeNotDisputed();
    error AlreadyResolved();
    error UserIsBanned();
    error PeerAttestationNotAllowed();
    error InsufficientReputation();

    // ============ Constants ============
    bytes32 public constant ARBITER_ROLE = keccak256("ARBITER_ROLE");
    bytes32 public constant ORACLE_ROLE = keccak256("ORACLE_ROLE");
    bytes32 public constant ESCROW_ROLE = keccak256("ESCROW_ROLE");
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");

    uint256 public constant BASIS_POINTS = 10000;
    uint256 public constant DELIVERY_WINDOW = 4 hours;
    uint256 public constant QUANTITY_TOLERANCE = 500; // 5% tolerance
    uint256 public constant PEER_ATTESTATION_THRESHOLD = 10 * 1e18; // 10 kWh
    uint256 public constant NON_DELIVERY_SLASH = 1000; // 10%
    uint256 public constant FALSE_DISPUTE_SLASH = 500; // 5%
    uint256 public constant TEMP_BAN_THRESHOLD = 3; // 3 offenses
    uint256 public constant PERM_BAN_THRESHOLD = 5; // 5 offenses
    uint256 public constant TEMP_BAN_DURATION = 30 days;
    uint256 public constant MIN_REPUTATION_FOR_PEER = 70; // 70% reputation

    // ============ Enums ============
    enum DeliveryStatus {
        Pending,
        Reported,
        Confirmed,
        Disputed,
        Resolved,
        Failed
    }

    enum VerificationMethod {
        None,
        DISCOMAttestation,
        SmartMeterOracle,
        PeerAttestation
    }

    enum DisputeResolution {
        None,
        DeliveryConfirmed,
        NonDelivery,
        PartialDelivery
    }

    // ============ Structs ============
    struct Trade {
        uint256 tradeId;
        address seller;
        address buyer;
        uint256 quantity;          // kWh in wei (1e18 = 1 kWh)
        uint256 value;             // Trade value in SHAKTI
        uint256 createdAt;
        uint256 deliveryDeadline;
        uint256 deliveredQuantity;
        DeliveryStatus status;
        VerificationMethod method;
        DisputeResolution resolution;
        address discom;
        bytes32 meterReadingHash;
        bool sellerSlashed;
        bool buyerSlashed;
    }

    struct UserStats {
        uint256 totalTrades;
        uint256 successfulDeliveries;
        uint256 failedDeliveries;
        uint256 disputesRaised;
        uint256 disputesLost;
        uint256 offenseCount;
        uint256 banExpiry;
        bool permanentlyBanned;
        uint256 totalSlashed;
    }

    struct SlashRecord {
        uint256 tradeId;
        address user;
        uint256 amount;
        string reason;
        uint256 timestamp;
    }

    // ============ State Variables ============
    /// @notice Mapping of trade ID to Trade details
    mapping(uint256 => Trade) public trades;

    /// @notice Mapping of user address to stats
    mapping(address => UserStats) public userStats;

    /// @notice Mapping of DISCOM address to trusted status
    mapping(address => bool) public trustedDISCOMs;

    /// @notice Mapping of trade ID to DISCOM signature
    mapping(uint256 => bytes) public discomSignatures;

    /// @notice Array of all trade IDs
    uint256[] public tradeIds;

    /// @notice Array of slash records
    SlashRecord[] public slashHistory;

    /// @notice Total trades processed
    uint256 public totalTrades;

    /// @notice Total successful deliveries
    uint256 public totalSuccessfulDeliveries;

    /// @notice Total failed deliveries
    uint256 public totalFailedDeliveries;

    /// @notice Total value slashed
    uint256 public totalSlashed;

    /// @notice Connected escrow contract
    address public escrowContract;

    /// @notice Connected staking contract (for slashing)
    address public stakingContract;

    // ============ Events ============
    event TradeRegistered(
        uint256 indexed tradeId,
        address indexed seller,
        address indexed buyer,
        uint256 quantity,
        uint256 value,
        uint256 deliveryDeadline
    );

    event DeliveryReported(
        uint256 indexed tradeId,
        address indexed reporter,
        uint256 deliveredQuantity,
        VerificationMethod method
    );

    event DeliveryConfirmed(
        uint256 indexed tradeId,
        address indexed confirmer,
        VerificationMethod method
    );

    event DeliveryDisputed(
        uint256 indexed tradeId,
        address indexed disputer,
        string reason
    );

    event DeliveryResolved(
        uint256 indexed tradeId,
        DisputeResolution resolution,
        address resolver
    );

    event SlashApplied(
        uint256 indexed tradeId,
        address indexed user,
        uint256 amount,
        string reason
    );

    event UserBanned(
        address indexed user,
        bool permanent,
        uint256 banExpiry
    );

    event DISCOMTrustUpdated(address indexed discom, bool trusted);
    event OracleReportReceived(uint256 indexed tradeId, uint256 quantity, bytes32 readingHash);

    // ============ Constructor ============
    /**
     * @notice Initializes the EnergyVerification contract
     * @param _admin Admin address
     */
    constructor(address _admin) {
        if (_admin == address(0)) revert ZeroAddress();

        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        _grantRole(ARBITER_ROLE, _admin);
        _grantRole(PAUSER_ROLE, _admin);
    }

    // ============ Trade Registration ============

    /**
     * @notice Registers a new trade for verification
     * @param tradeId Unique trade ID from auction
     * @param seller Seller address
     * @param buyer Buyer address
     * @param quantity Energy quantity in kWh (wei units)
     * @param value Trade value in SHAKTI tokens
     * @param discom DISCOM for this trade (if known)
     */
    function registerTrade(
        uint256 tradeId,
        address seller,
        address buyer,
        uint256 quantity,
        uint256 value,
        address discom
    ) external onlyRole(ESCROW_ROLE) whenNotPaused {
        if (seller == address(0) || buyer == address(0)) revert ZeroAddress();
        if (quantity == 0) revert ZeroAmount();
        if (trades[tradeId].createdAt != 0) revert TradeAlreadyExists();

        // Check if users are banned
        _checkBan(seller);
        _checkBan(buyer);

        uint256 deadline = block.timestamp + DELIVERY_WINDOW;

        trades[tradeId] = Trade({
            tradeId: tradeId,
            seller: seller,
            buyer: buyer,
            quantity: quantity,
            value: value,
            createdAt: block.timestamp,
            deliveryDeadline: deadline,
            deliveredQuantity: 0,
            status: DeliveryStatus.Pending,
            method: VerificationMethod.None,
            resolution: DisputeResolution.None,
            discom: discom,
            meterReadingHash: bytes32(0),
            sellerSlashed: false,
            buyerSlashed: false
        });

        tradeIds.push(tradeId);
        totalTrades++;

        // Update user stats
        userStats[seller].totalTrades++;
        userStats[buyer].totalTrades++;

        emit TradeRegistered(tradeId, seller, buyer, quantity, value, deadline);
    }

    // ============ DISCOM Attestation (Primary) ============

    /**
     * @notice Reports delivery with DISCOM attestation
     * @param tradeId Trade ID
     * @param deliveredQuantity Actual delivered quantity
     * @param signature DISCOM signature of (tradeId, seller, buyer, deliveredQuantity, timestamp)
     */
    function reportDeliveryWithDISCOM(
        uint256 tradeId,
        uint256 deliveredQuantity,
        bytes calldata signature
    ) external nonReentrant whenNotPaused {
        Trade storage trade = trades[tradeId];
        _validateTradeForDelivery(trade, tradeId);

        // Verify DISCOM signature
        address discom = _verifyDISCOMSignature(
            tradeId,
            trade.seller,
            trade.buyer,
            deliveredQuantity,
            signature
        );

        if (!trustedDISCOMs[discom]) revert UntrustedDISCOM();

        // Check quantity tolerance
        _validateQuantity(trade.quantity, deliveredQuantity);

        trade.deliveredQuantity = deliveredQuantity;
        trade.status = DeliveryStatus.Reported;
        trade.method = VerificationMethod.DISCOMAttestation;
        trade.discom = discom;
        discomSignatures[tradeId] = signature;

        emit DeliveryReported(tradeId, discom, deliveredQuantity, VerificationMethod.DISCOMAttestation);

        // Auto-confirm if within tolerance
        if (_isWithinTolerance(trade.quantity, deliveredQuantity)) {
            _confirmDelivery(tradeId);
        }
    }

    // ============ Smart Meter Oracle (Secondary) ============

    /**
     * @notice Reports delivery from smart meter oracle
     * @param tradeId Trade ID
     * @param deliveredQuantity Measured delivery quantity
     * @param meterReadingHash Hash of meter reading data
     */
    function reportDeliveryFromOracle(
        uint256 tradeId,
        uint256 deliveredQuantity,
        bytes32 meterReadingHash
    ) external onlyRole(ORACLE_ROLE) nonReentrant whenNotPaused {
        Trade storage trade = trades[tradeId];
        _validateTradeForDelivery(trade, tradeId);

        trade.deliveredQuantity = deliveredQuantity;
        trade.meterReadingHash = meterReadingHash;
        trade.status = DeliveryStatus.Reported;
        trade.method = VerificationMethod.SmartMeterOracle;

        emit OracleReportReceived(tradeId, deliveredQuantity, meterReadingHash);
        emit DeliveryReported(tradeId, msg.sender, deliveredQuantity, VerificationMethod.SmartMeterOracle);

        // Auto-confirm if within tolerance
        if (_isWithinTolerance(trade.quantity, deliveredQuantity)) {
            _confirmDelivery(tradeId);
        }
    }

    // ============ Peer Attestation (Backup) ============

    /**
     * @notice Buyer confirms receipt for small trades
     * @param tradeId Trade ID
     */
    function confirmReceipt(uint256 tradeId) external nonReentrant whenNotPaused {
        Trade storage trade = trades[tradeId];

        if (trade.createdAt == 0) revert TradeNotFound();
        if (msg.sender != trade.buyer) revert NotBuyer();

        // Peer attestation only for small trades
        if (trade.quantity > PEER_ATTESTATION_THRESHOLD) {
            revert PeerAttestationNotAllowed();
        }

        // Check buyer reputation
        if (_getUserReputation(trade.buyer) < MIN_REPUTATION_FOR_PEER) {
            revert InsufficientReputation();
        }

        if (trade.status == DeliveryStatus.Confirmed) revert DeliveryAlreadyConfirmed();
        if (trade.status == DeliveryStatus.Resolved) revert AlreadyResolved();

        // If not yet reported, set delivered quantity to contracted
        if (trade.status == DeliveryStatus.Pending) {
            trade.deliveredQuantity = trade.quantity;
            trade.status = DeliveryStatus.Reported;
            trade.method = VerificationMethod.PeerAttestation;

            emit DeliveryReported(tradeId, trade.buyer, trade.quantity, VerificationMethod.PeerAttestation);
        }

        _confirmDelivery(tradeId);
    }

    // ============ Dispute Handling ============

    /**
     * @notice Raises non-delivery dispute
     * @param tradeId Trade ID
     */
    function raiseNonDelivery(uint256 tradeId) external nonReentrant whenNotPaused {
        Trade storage trade = trades[tradeId];

        if (trade.createdAt == 0) revert TradeNotFound();
        if (msg.sender != trade.buyer) revert NotBuyer();
        if (trade.status == DeliveryStatus.Confirmed) revert DeliveryAlreadyConfirmed();
        if (trade.status == DeliveryStatus.Disputed) revert DeliveryAlreadyDisputed();
        if (trade.status == DeliveryStatus.Resolved) revert AlreadyResolved();

        // Can only dispute after some time or if reported with issues
        if (trade.status == DeliveryStatus.Pending && block.timestamp < trade.deliveryDeadline) {
            revert DeliveryWindowNotExpired();
        }

        trade.status = DeliveryStatus.Disputed;
        userStats[trade.buyer].disputesRaised++;

        emit DeliveryDisputed(tradeId, trade.buyer, "Non-delivery claimed by buyer");
    }

    /**
     * @notice Resolves a disputed delivery
     * @param tradeId Trade ID
     * @param resolution Resolution decision
     * @param partialQuantity Partial quantity for PartialDelivery resolution
     */
    function resolveDelivery(
        uint256 tradeId,
        DisputeResolution resolution,
        uint256 partialQuantity
    ) external onlyRole(ARBITER_ROLE) nonReentrant {
        Trade storage trade = trades[tradeId];

        if (trade.createdAt == 0) revert TradeNotFound();
        if (trade.status != DeliveryStatus.Disputed) revert TradeNotDisputed();
        if (resolution == DisputeResolution.None) revert InvalidTradeId();

        trade.resolution = resolution;
        trade.status = DeliveryStatus.Resolved;

        if (resolution == DisputeResolution.DeliveryConfirmed) {
            // Buyer raised false dispute
            _applyBuyerSlash(tradeId);
            userStats[trade.buyer].disputesLost++;
            _recordSuccessfulDelivery(trade);
        } else if (resolution == DisputeResolution.NonDelivery) {
            // Seller failed to deliver
            _applySellerSlash(tradeId);
            _recordFailedDelivery(trade);
        } else if (resolution == DisputeResolution.PartialDelivery) {
            // Partial delivery - proportional handling
            trade.deliveredQuantity = partialQuantity;
            // Slash seller proportionally
            _applyPartialSlash(tradeId, trade.quantity, partialQuantity);
        }

        emit DeliveryResolved(tradeId, resolution, msg.sender);
    }

    /**
     * @notice Marks a trade as failed after deadline
     * @param tradeId Trade ID
     */
    function markDeliveryFailed(uint256 tradeId) external nonReentrant {
        Trade storage trade = trades[tradeId];

        if (trade.createdAt == 0) revert TradeNotFound();
        if (trade.status != DeliveryStatus.Pending) revert DeliveryNotPending();
        if (block.timestamp <= trade.deliveryDeadline) revert DeliveryWindowNotExpired();

        trade.status = DeliveryStatus.Failed;
        _applySellerSlash(tradeId);
        _recordFailedDelivery(trade);

        emit DeliveryResolved(tradeId, DisputeResolution.NonDelivery, msg.sender);
    }

    // ============ Internal Functions ============

    function _validateTradeForDelivery(Trade storage trade, uint256 /* tradeId */) internal view {
        if (trade.createdAt == 0) revert TradeNotFound();
        if (trade.status != DeliveryStatus.Pending) revert DeliveryNotPending();
        if (block.timestamp > trade.deliveryDeadline) revert DeliveryWindowExpired();
    }

    function _verifyDISCOMSignature(
        uint256 tradeId,
        address seller,
        address buyer,
        uint256 quantity,
        bytes calldata signature
    ) internal view returns (address) {
        bytes32 messageHash = keccak256(abi.encodePacked(
            tradeId,
            seller,
            buyer,
            quantity,
            block.chainid
        ));

        bytes32 ethSignedHash = messageHash.toEthSignedMessageHash();
        address signer = ethSignedHash.recover(signature);

        if (signer == address(0)) revert InvalidSignature();

        return signer;
    }

    function _validateQuantity(uint256 expected, uint256 delivered) internal pure {
        uint256 tolerance = (expected * QUANTITY_TOLERANCE) / BASIS_POINTS;
        uint256 minAcceptable = expected > tolerance ? expected - tolerance : 0;
        uint256 maxAcceptable = expected + tolerance;

        if (delivered < minAcceptable || delivered > maxAcceptable) {
            revert QuantityMismatch(expected, delivered, tolerance);
        }
    }

    function _isWithinTolerance(uint256 expected, uint256 delivered) internal pure returns (bool) {
        uint256 tolerance = (expected * QUANTITY_TOLERANCE) / BASIS_POINTS;
        uint256 minAcceptable = expected > tolerance ? expected - tolerance : 0;
        uint256 maxAcceptable = expected + tolerance;

        return delivered >= minAcceptable && delivered <= maxAcceptable;
    }

    function _confirmDelivery(uint256 tradeId) internal {
        Trade storage trade = trades[tradeId];

        trade.status = DeliveryStatus.Confirmed;
        _recordSuccessfulDelivery(trade);

        emit DeliveryConfirmed(tradeId, msg.sender, trade.method);
    }

    function _recordSuccessfulDelivery(Trade storage trade) internal {
        userStats[trade.seller].successfulDeliveries++;
        totalSuccessfulDeliveries++;
    }

    function _recordFailedDelivery(Trade storage trade) internal {
        userStats[trade.seller].failedDeliveries++;
        totalFailedDeliveries++;
    }

    function _applySellerSlash(uint256 tradeId) internal {
        Trade storage trade = trades[tradeId];

        if (trade.sellerSlashed) return;

        uint256 slashAmount = (trade.value * NON_DELIVERY_SLASH) / BASIS_POINTS;
        trade.sellerSlashed = true;

        _recordSlash(tradeId, trade.seller, slashAmount, "Non-delivery");
        _updateOffenseCount(trade.seller);
    }

    function _applyBuyerSlash(uint256 tradeId) internal {
        Trade storage trade = trades[tradeId];

        if (trade.buyerSlashed) return;

        uint256 slashAmount = (trade.value * FALSE_DISPUTE_SLASH) / BASIS_POINTS;
        trade.buyerSlashed = true;

        _recordSlash(tradeId, trade.buyer, slashAmount, "False dispute");
        _updateOffenseCount(trade.buyer);
    }

    function _applyPartialSlash(uint256 tradeId, uint256 expected, uint256 delivered) internal {
        Trade storage trade = trades[tradeId];

        if (trade.sellerSlashed) return;

        // Calculate proportional slash based on shortfall
        uint256 shortfall = expected > delivered ? expected - delivered : 0;
        uint256 shortfallRatio = (shortfall * BASIS_POINTS) / expected;
        uint256 slashAmount = (trade.value * shortfallRatio * NON_DELIVERY_SLASH) / (BASIS_POINTS * BASIS_POINTS);

        if (slashAmount > 0) {
            trade.sellerSlashed = true;
            _recordSlash(tradeId, trade.seller, slashAmount, "Partial delivery shortfall");

            // Only update offense count if significant shortfall
            if (shortfallRatio > 2000) { // > 20%
                _updateOffenseCount(trade.seller);
            }
        }
    }

    function _recordSlash(uint256 tradeId, address user, uint256 amount, string memory reason) internal {
        userStats[user].totalSlashed += amount;
        totalSlashed += amount;

        slashHistory.push(SlashRecord({
            tradeId: tradeId,
            user: user,
            amount: amount,
            reason: reason,
            timestamp: block.timestamp
        }));

        emit SlashApplied(tradeId, user, amount, reason);
    }

    function _updateOffenseCount(address user) internal {
        UserStats storage stats = userStats[user];
        stats.offenseCount++;

        if (stats.offenseCount >= PERM_BAN_THRESHOLD) {
            stats.permanentlyBanned = true;
            emit UserBanned(user, true, 0);
        } else if (stats.offenseCount >= TEMP_BAN_THRESHOLD) {
            stats.banExpiry = block.timestamp + TEMP_BAN_DURATION;
            emit UserBanned(user, false, stats.banExpiry);
        }
    }

    function _checkBan(address user) internal view {
        UserStats storage stats = userStats[user];

        if (stats.permanentlyBanned) revert UserIsBanned();
        if (stats.banExpiry > block.timestamp) revert UserIsBanned();
    }

    function _getUserReputation(address user) internal view returns (uint256) {
        UserStats storage stats = userStats[user];

        // Calculate completed trades (successful + failed)
        uint256 completedTrades = stats.successfulDeliveries + stats.failedDeliveries;

        // New users or users without completed trades start with 100%
        if (completedTrades == 0) return 100;

        uint256 successRate = (stats.successfulDeliveries * 100) / completedTrades;
        uint256 disputePenalty = stats.disputesLost * 5; // -5% per lost dispute

        return successRate > disputePenalty ? successRate - disputePenalty : 0;
    }

    // ============ Admin Functions ============

    /**
     * @notice Sets DISCOM trust status
     * @param discom DISCOM address
     * @param trusted Trust status
     */
    function setDISCOMTrust(address discom, bool trusted) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (discom == address(0)) revert ZeroAddress();
        trustedDISCOMs[discom] = trusted;
        emit DISCOMTrustUpdated(discom, trusted);
    }

    /**
     * @notice Sets escrow contract address
     * @param _escrow Escrow contract address
     */
    function setEscrowContract(address _escrow) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (_escrow == address(0)) revert ZeroAddress();
        escrowContract = _escrow;
        _grantRole(ESCROW_ROLE, _escrow);
    }

    /**
     * @notice Sets staking contract address
     * @param _staking Staking contract address
     */
    function setStakingContract(address _staking) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (_staking == address(0)) revert ZeroAddress();
        stakingContract = _staking;
    }

    /**
     * @notice Lifts a temporary ban
     * @param user User address
     */
    function liftBan(address user) external onlyRole(DEFAULT_ADMIN_ROLE) {
        UserStats storage stats = userStats[user];
        stats.banExpiry = 0;
        // Note: Cannot lift permanent ban, offense count remains
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

    // ============ View Functions ============

    /**
     * @notice Gets delivery status for a trade
     * @param tradeId Trade ID
     * @return status Current delivery status
     */
    function getDeliveryStatus(uint256 tradeId) external view returns (DeliveryStatus status) {
        return trades[tradeId].status;
    }

    /**
     * @notice Gets full trade details
     * @param tradeId Trade ID
     * @return Trade struct
     */
    function getTrade(uint256 tradeId) external view returns (Trade memory) {
        return trades[tradeId];
    }

    /**
     * @notice Gets user statistics
     * @param user User address
     * @return UserStats struct
     */
    function getUserStats(address user) external view returns (UserStats memory) {
        return userStats[user];
    }

    /**
     * @notice Gets user reputation score (0-100)
     * @param user User address
     * @return Reputation percentage
     */
    function getUserReputation(address user) external view returns (uint256) {
        return _getUserReputation(user);
    }

    /**
     * @notice Checks if user is banned
     * @param user User address
     * @return banned True if currently banned
     * @return permanent True if permanently banned
     * @return expiry Ban expiry timestamp (0 if permanent or not banned)
     */
    function isBanned(address user) external view returns (bool banned, bool permanent, uint256 expiry) {
        UserStats storage stats = userStats[user];

        if (stats.permanentlyBanned) {
            return (true, true, 0);
        }

        if (stats.banExpiry > block.timestamp) {
            return (true, false, stats.banExpiry);
        }

        return (false, false, 0);
    }

    /**
     * @notice Gets verification statistics
     * @return total Total trades
     * @return successful Successful deliveries
     * @return failed Failed deliveries
     * @return slashed Total value slashed
     */
    function getVerificationStats() external view returns (
        uint256 total,
        uint256 successful,
        uint256 failed,
        uint256 slashed
    ) {
        return (totalTrades, totalSuccessfulDeliveries, totalFailedDeliveries, totalSlashed);
    }

    /**
     * @notice Gets time remaining for delivery
     * @param tradeId Trade ID
     * @return Seconds remaining, 0 if expired
     */
    function getDeliveryTimeRemaining(uint256 tradeId) external view returns (uint256) {
        Trade storage trade = trades[tradeId];

        if (trade.createdAt == 0) return 0;
        if (block.timestamp >= trade.deliveryDeadline) return 0;

        return trade.deliveryDeadline - block.timestamp;
    }

    /**
     * @notice Gets all trade IDs
     * @return Array of trade IDs
     */
    function getAllTradeIds() external view returns (uint256[] memory) {
        return tradeIds;
    }

    /**
     * @notice Gets slash history length
     * @return Number of slash records
     */
    function getSlashHistoryLength() external view returns (uint256) {
        return slashHistory.length;
    }

    /**
     * @notice Gets slash record at index
     * @param index Index in slash history
     * @return SlashRecord struct
     */
    function getSlashRecord(uint256 index) external view returns (SlashRecord memory) {
        return slashHistory[index];
    }

    /**
     * @notice Checks if a DISCOM is trusted
     * @param discom DISCOM address
     * @return True if trusted
     */
    function isDISCOMTrusted(address discom) external view returns (bool) {
        return trustedDISCOMs[discom];
    }

    /**
     * @notice Gets trades by user (seller or buyer)
     * @param user User address
     * @return Array of trade IDs where user is seller or buyer
     */
    function getTradesByUser(address user) external view returns (uint256[] memory) {
        uint256 count = 0;

        // First, count matching trades
        for (uint256 i = 0; i < tradeIds.length; i++) {
            Trade storage trade = trades[tradeIds[i]];
            if (trade.seller == user || trade.buyer == user) {
                count++;
            }
        }

        // Then populate array
        uint256[] memory userTrades = new uint256[](count);
        uint256 index = 0;

        for (uint256 i = 0; i < tradeIds.length; i++) {
            Trade storage trade = trades[tradeIds[i]];
            if (trade.seller == user || trade.buyer == user) {
                userTrades[index] = tradeIds[i];
                index++;
            }
        }

        return userTrades;
    }

    /**
     * @notice Gets pending trades count
     * @return Number of pending trades
     */
    function getPendingTradesCount() external view returns (uint256) {
        uint256 count = 0;

        for (uint256 i = 0; i < tradeIds.length; i++) {
            if (trades[tradeIds[i]].status == DeliveryStatus.Pending) {
                count++;
            }
        }

        return count;
    }
}
