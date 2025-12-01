// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";

/**
 * @title IShaktiToken
 * @notice Interface for ShaktiToken burn function
 */
interface IShaktiToken is IERC20 {
    function burn(uint256 amount) external;
}

/**
 * @title EnergyEscrow
 * @author SHAKTI-CHAIN Team
 * @notice Escrow contract for secure V2G energy trading settlements
 * @dev Handles deposits, settlements, fees, and dispute resolution
 *
 * Features:
 * - Secure fund locking during auctions
 * - Automated settlement with fee deduction
 * - 2% platform fee (70% treasury, 30% burned)
 * - 24-hour dispute window
 * - Arbiter-based dispute resolution
 * - Slashing for bad actors
 * - Emergency circuit breaker
 *
 * Gas Optimizations:
 * - Custom errors
 * - Packed structs
 * - Batch settlements
 */
contract EnergyEscrow is ReentrancyGuard, AccessControl, Pausable {
    using SafeERC20 for IERC20;
    using SafeERC20 for IShaktiToken;

    // ============ Custom Errors ============
    error ZeroAddress();
    error ZeroAmount();
    error InsufficientFunds(uint256 required, uint256 available);
    error SettlementNotFound(uint256 settlementId);
    error SettlementAlreadyProcessed(uint256 settlementId);
    error DisputeWindowExpired(uint256 deadline, uint256 currentTime);
    error DisputeWindowNotExpired(uint256 deadline, uint256 currentTime);
    error DisputeAlreadyRaised(uint256 settlementId);
    error NoDisputeRaised(uint256 settlementId);
    error NotPartyToSettlement(address caller, uint256 settlementId);
    error InvalidFeePercentage(uint256 fee);
    error InvalidBurnPercentage(uint256 burn);
    error CircuitBreakerActive();
    error UnauthorizedAuction(address caller);

    // ============ Constants ============
    bytes32 public constant ARBITER_ROLE = keccak256("ARBITER_ROLE");
    bytes32 public constant AUCTION_ROLE = keccak256("AUCTION_ROLE");
    bytes32 public constant TREASURY_ROLE = keccak256("TREASURY_ROLE");

    /// @notice Price precision for calculations
    uint256 public constant PRICE_PRECISION = 1e18;

    /// @notice Fee precision (10000 = 100%)
    uint256 public constant FEE_PRECISION = 10000;

    /// @notice Dispute window duration (24 hours)
    uint256 public constant DISPUTE_WINDOW = 24 hours;

    /// @notice Maximum fee percentage (10% = 1000)
    uint256 public constant MAX_FEE_PERCENTAGE = 1000;

    // ============ Enums ============
    enum SettlementStatus {
        PENDING,        // Settlement created, waiting for finalization
        COMPLETED,      // Settlement finalized, funds transferred
        DISPUTED,       // Dispute raised
        RESOLVED,       // Dispute resolved
        REFUNDED        // Settlement cancelled, funds returned
    }

    enum DisputeOutcome {
        NONE,
        BUYER_WINS,     // Buyer gets full refund
        SELLER_WINS,    // Seller gets payment
        SPLIT           // Split settlement
    }

    // ============ Structs ============
    /// @notice Settlement record
    struct Settlement {
        uint256 settlementId;
        uint256 auctionRoundId;
        address buyer;
        address seller;
        uint128 quantity;           // Energy quantity in Wh
        uint128 price;              // Price per Wh
        uint256 totalAmount;        // Total settlement amount
        uint256 platformFee;        // Platform fee amount
        uint256 burnAmount;         // Amount to burn
        uint64 timestamp;           // Settlement creation time
        uint64 disputeDeadline;     // Deadline to raise dispute
        SettlementStatus status;
        DisputeOutcome disputeOutcome;
    }

    /// @notice Dispute record
    struct Dispute {
        uint256 settlementId;
        address raisedBy;
        string reason;
        uint64 timestamp;
        bool resolved;
        DisputeOutcome outcome;
        string resolution;
    }

    // ============ State Variables ============
    /// @notice SHAKTI token contract
    IShaktiToken public immutable shaktiToken;

    /// @notice Treasury address for fee collection
    address public treasury;

    /// @notice Platform fee percentage (in basis points, 200 = 2%)
    uint256 public platformFeePercentage;

    /// @notice Burn percentage of fees (in basis points, 3000 = 30%)
    uint256 public feeBurnPercentage;

    /// @notice Circuit breaker status
    bool public circuitBreakerActive;

    /// @notice Next settlement ID
    uint256 public nextSettlementId;

    /// @notice Mapping of round ID to trader to locked funds
    mapping(uint256 => mapping(address => uint256)) public lockedFunds;

    /// @notice Mapping of settlement ID to Settlement
    mapping(uint256 => Settlement) public settlements;

    /// @notice Mapping of round ID to settlement IDs
    mapping(uint256 => uint256[]) public roundSettlements;

    /// @notice Mapping of settlement ID to Dispute
    mapping(uint256 => Dispute) public disputes;

    /// @notice Mapping of trader to their settlement IDs
    mapping(address => uint256[]) public traderSettlements;

    /// @notice Slashing record for bad actors
    mapping(address => uint256) public slashCount;

    /// @notice Total fees collected
    uint256 public totalFeesCollected;

    /// @notice Total tokens burned
    uint256 public totalTokensBurned;

    // ============ Events ============
    event Deposited(
        uint256 indexed roundId,
        address indexed trader,
        uint256 amount
    );
    event Withdrawn(
        uint256 indexed roundId,
        address indexed trader,
        uint256 amount
    );
    event SettlementCreated(
        uint256 indexed settlementId,
        uint256 indexed roundId,
        address indexed buyer,
        address seller,
        uint256 quantity,
        uint256 price,
        uint256 totalAmount
    );
    event SettlementCompleted(
        uint256 indexed settlementId,
        address indexed seller,
        uint256 sellerAmount,
        uint256 fee,
        uint256 burned
    );
    event Refunded(
        uint256 indexed settlementId,
        address indexed buyer,
        uint256 amount
    );
    event DisputeRaised(
        uint256 indexed settlementId,
        address indexed raisedBy,
        string reason
    );
    event DisputeResolved(
        uint256 indexed settlementId,
        DisputeOutcome outcome,
        string resolution
    );
    event Slashed(
        address indexed trader,
        uint256 amount,
        string reason
    );
    event FeeUpdated(uint256 oldFee, uint256 newFee);
    event BurnPercentageUpdated(uint256 oldPercentage, uint256 newPercentage);
    event TreasuryUpdated(address oldTreasury, address newTreasury);
    event CircuitBreakerToggled(bool active);
    event EmergencyWithdraw(address indexed trader, uint256 amount);

    // ============ Modifiers ============
    modifier whenCircuitBreakerOff() {
        if (circuitBreakerActive) revert CircuitBreakerActive();
        _;
    }

    modifier onlyAuction() {
        if (!hasRole(AUCTION_ROLE, msg.sender)) revert UnauthorizedAuction(msg.sender);
        _;
    }

    // ============ Constructor ============
    /**
     * @notice Initializes the EnergyEscrow contract
     * @param _shaktiToken Address of the SHAKTI token
     * @param _treasury Address of the treasury
     * @param _admin Admin address
     * @param _platformFee Platform fee in basis points (200 = 2%)
     * @param _feeBurn Fee burn percentage in basis points (3000 = 30%)
     */
    constructor(
        address _shaktiToken,
        address _treasury,
        address _admin,
        uint256 _platformFee,
        uint256 _feeBurn
    ) {
        if (_shaktiToken == address(0)) revert ZeroAddress();
        if (_treasury == address(0)) revert ZeroAddress();
        if (_admin == address(0)) revert ZeroAddress();
        if (_platformFee > MAX_FEE_PERCENTAGE) revert InvalidFeePercentage(_platformFee);
        if (_feeBurn > FEE_PRECISION) revert InvalidBurnPercentage(_feeBurn);

        shaktiToken = IShaktiToken(_shaktiToken);
        treasury = _treasury;
        platformFeePercentage = _platformFee;
        feeBurnPercentage = _feeBurn;

        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        _grantRole(ARBITER_ROLE, _admin);
        _grantRole(TREASURY_ROLE, _admin);
    }

    // ============ Deposit Functions ============

    /**
     * @notice Deposits funds for an auction round
     * @param roundId The auction round ID
     * @param amount Amount to deposit
     */
    function deposit(
        uint256 roundId,
        uint256 amount
    ) external nonReentrant whenNotPaused whenCircuitBreakerOff {
        if (amount == 0) revert ZeroAmount();

        shaktiToken.safeTransferFrom(msg.sender, address(this), amount);
        lockedFunds[roundId][msg.sender] += amount;

        emit Deposited(roundId, msg.sender, amount);
    }

    /**
     * @notice Deposits funds on behalf of a trader (called by auction contract)
     * @param roundId The auction round ID
     * @param trader The trader address
     * @param amount Amount to deposit
     */
    function depositFor(
        uint256 roundId,
        address trader,
        uint256 amount
    ) external nonReentrant whenNotPaused whenCircuitBreakerOff onlyAuction {
        if (trader == address(0)) revert ZeroAddress();
        if (amount == 0) revert ZeroAmount();

        shaktiToken.safeTransferFrom(msg.sender, address(this), amount);
        lockedFunds[roundId][trader] += amount;

        emit Deposited(roundId, trader, amount);
    }

    /**
     * @notice Withdraws unallocated funds from an auction round
     * @param roundId The auction round ID
     * @param amount Amount to withdraw
     */
    function withdraw(
        uint256 roundId,
        uint256 amount
    ) external nonReentrant whenNotPaused {
        if (amount == 0) revert ZeroAmount();
        uint256 available = lockedFunds[roundId][msg.sender];
        if (amount > available) revert InsufficientFunds(amount, available);

        lockedFunds[roundId][msg.sender] -= amount;
        shaktiToken.safeTransfer(msg.sender, amount);

        emit Withdrawn(roundId, msg.sender, amount);
    }

    // ============ Settlement Functions ============

    /**
     * @notice Creates a settlement record for a matched order pair
     * @param roundId The auction round ID
     * @param buyer Buyer address
     * @param seller Seller address
     * @param quantity Quantity in Wh
     * @param price Price per Wh
     */
    function createSettlement(
        uint256 roundId,
        address buyer,
        address seller,
        uint256 quantity,
        uint256 price
    ) external nonReentrant whenNotPaused whenCircuitBreakerOff onlyAuction returns (uint256 settlementId) {
        if (buyer == address(0) || seller == address(0)) revert ZeroAddress();
        if (quantity == 0) revert ZeroAmount();

        uint256 totalAmount = (quantity * price) / PRICE_PRECISION;
        uint256 fee = (totalAmount * platformFeePercentage) / FEE_PRECISION;
        uint256 burnAmount = (fee * feeBurnPercentage) / FEE_PRECISION;

        // Check buyer has sufficient locked funds
        if (lockedFunds[roundId][buyer] < totalAmount) {
            revert InsufficientFunds(totalAmount, lockedFunds[roundId][buyer]);
        }

        settlementId = nextSettlementId++;

        settlements[settlementId] = Settlement({
            settlementId: settlementId,
            auctionRoundId: roundId,
            buyer: buyer,
            seller: seller,
            quantity: uint128(quantity),
            price: uint128(price),
            totalAmount: totalAmount,
            platformFee: fee,
            burnAmount: burnAmount,
            timestamp: uint64(block.timestamp),
            disputeDeadline: uint64(block.timestamp + DISPUTE_WINDOW),
            status: SettlementStatus.PENDING,
            disputeOutcome: DisputeOutcome.NONE
        });

        // Allocate buyer's locked funds to this settlement
        lockedFunds[roundId][buyer] -= totalAmount;

        roundSettlements[roundId].push(settlementId);
        traderSettlements[buyer].push(settlementId);
        traderSettlements[seller].push(settlementId);

        emit SettlementCreated(
            settlementId,
            roundId,
            buyer,
            seller,
            quantity,
            price,
            totalAmount
        );
    }

    /**
     * @notice Completes a settlement after dispute window
     * @param settlementId The settlement ID
     */
    function completeSettlement(
        uint256 settlementId
    ) external nonReentrant whenNotPaused whenCircuitBreakerOff {
        Settlement storage settlement = settlements[settlementId];

        if (settlement.buyer == address(0)) revert SettlementNotFound(settlementId);
        if (settlement.status != SettlementStatus.PENDING) {
            revert SettlementAlreadyProcessed(settlementId);
        }
        if (block.timestamp < settlement.disputeDeadline) {
            revert DisputeWindowNotExpired(settlement.disputeDeadline, block.timestamp);
        }

        _finalizeSettlement(settlementId);
    }

    /**
     * @notice Batch completes multiple settlements
     * @param settlementIds Array of settlement IDs to complete
     */
    function batchCompleteSettlements(
        uint256[] calldata settlementIds
    ) external nonReentrant whenNotPaused whenCircuitBreakerOff {
        for (uint256 i = 0; i < settlementIds.length; i++) {
            Settlement storage settlement = settlements[settlementIds[i]];

            if (settlement.buyer == address(0)) continue;
            if (settlement.status != SettlementStatus.PENDING) continue;
            if (block.timestamp < settlement.disputeDeadline) continue;

            _finalizeSettlement(settlementIds[i]);
        }
    }

    /**
     * @notice Refunds buyer for a cancelled settlement
     * @param settlementId The settlement ID
     */
    function refundSettlement(
        uint256 settlementId
    ) external nonReentrant whenNotPaused onlyAuction {
        Settlement storage settlement = settlements[settlementId];

        if (settlement.buyer == address(0)) revert SettlementNotFound(settlementId);
        if (settlement.status != SettlementStatus.PENDING) {
            revert SettlementAlreadyProcessed(settlementId);
        }

        settlement.status = SettlementStatus.REFUNDED;

        // Return full amount to buyer
        shaktiToken.safeTransfer(settlement.buyer, settlement.totalAmount);

        emit Refunded(settlementId, settlement.buyer, settlement.totalAmount);
    }

    // ============ Dispute Functions ============

    /**
     * @notice Raises a dispute for a settlement
     * @param settlementId The settlement ID
     * @param reason Reason for the dispute
     */
    function raiseDispute(
        uint256 settlementId,
        string calldata reason
    ) external whenNotPaused {
        Settlement storage settlement = settlements[settlementId];

        if (settlement.buyer == address(0)) revert SettlementNotFound(settlementId);
        if (settlement.status != SettlementStatus.PENDING) {
            revert SettlementAlreadyProcessed(settlementId);
        }
        if (block.timestamp > settlement.disputeDeadline) {
            revert DisputeWindowExpired(settlement.disputeDeadline, block.timestamp);
        }
        if (msg.sender != settlement.buyer && msg.sender != settlement.seller) {
            revert NotPartyToSettlement(msg.sender, settlementId);
        }
        if (disputes[settlementId].raisedBy != address(0)) {
            revert DisputeAlreadyRaised(settlementId);
        }

        settlement.status = SettlementStatus.DISPUTED;

        disputes[settlementId] = Dispute({
            settlementId: settlementId,
            raisedBy: msg.sender,
            reason: reason,
            timestamp: uint64(block.timestamp),
            resolved: false,
            outcome: DisputeOutcome.NONE,
            resolution: ""
        });

        emit DisputeRaised(settlementId, msg.sender, reason);
    }

    /**
     * @notice Resolves a dispute (arbiter only)
     * @param settlementId The settlement ID
     * @param outcome The dispute outcome
     * @param resolution Resolution description
     * @param slashBadActor Whether to slash the losing party
     */
    function resolveDispute(
        uint256 settlementId,
        DisputeOutcome outcome,
        string calldata resolution,
        bool slashBadActor
    ) external nonReentrant onlyRole(ARBITER_ROLE) {
        Settlement storage settlement = settlements[settlementId];
        Dispute storage dispute = disputes[settlementId];

        if (settlement.buyer == address(0)) revert SettlementNotFound(settlementId);
        if (settlement.status != SettlementStatus.DISPUTED) {
            revert NoDisputeRaised(settlementId);
        }

        dispute.resolved = true;
        dispute.outcome = outcome;
        dispute.resolution = resolution;
        settlement.disputeOutcome = outcome;
        settlement.status = SettlementStatus.RESOLVED;

        uint256 totalAmount = settlement.totalAmount;
        uint256 fee = settlement.platformFee;
        uint256 burnAmount = settlement.burnAmount;

        if (outcome == DisputeOutcome.BUYER_WINS) {
            // Full refund to buyer
            shaktiToken.safeTransfer(settlement.buyer, totalAmount);

            if (slashBadActor) {
                _slashTrader(settlement.seller, "Dispute lost - energy not delivered");
            }

            emit Refunded(settlementId, settlement.buyer, totalAmount);
        } else if (outcome == DisputeOutcome.SELLER_WINS) {
            // Pay seller (minus fee)
            uint256 sellerAmount = totalAmount - fee;
            uint256 treasuryAmount = fee - burnAmount;

            shaktiToken.safeTransfer(settlement.seller, sellerAmount);
            shaktiToken.safeTransfer(treasury, treasuryAmount);

            if (burnAmount > 0) {
                shaktiToken.burn(burnAmount);
                totalTokensBurned += burnAmount;
            }

            totalFeesCollected += fee;

            if (slashBadActor) {
                _slashTrader(settlement.buyer, "Dispute lost - false claim");
            }

            emit SettlementCompleted(settlementId, settlement.seller, sellerAmount, fee, burnAmount);
        } else if (outcome == DisputeOutcome.SPLIT) {
            // Split 50/50 (minus fee from total)
            uint256 halfAmount = (totalAmount - fee) / 2;
            uint256 treasuryAmount = fee - burnAmount;

            shaktiToken.safeTransfer(settlement.buyer, halfAmount);
            shaktiToken.safeTransfer(settlement.seller, halfAmount);
            shaktiToken.safeTransfer(treasury, treasuryAmount);

            if (burnAmount > 0) {
                shaktiToken.burn(burnAmount);
                totalTokensBurned += burnAmount;
            }

            totalFeesCollected += fee;

            emit SettlementCompleted(settlementId, settlement.seller, halfAmount, fee, burnAmount);
            emit Refunded(settlementId, settlement.buyer, halfAmount);
        }

        emit DisputeResolved(settlementId, outcome, resolution);
    }

    // ============ View Functions ============

    /**
     * @notice Gets settlement details
     * @param settlementId The settlement ID
     */
    function getSettlement(uint256 settlementId) external view returns (Settlement memory) {
        return settlements[settlementId];
    }

    /**
     * @notice Gets dispute details
     * @param settlementId The settlement ID
     */
    function getDispute(uint256 settlementId) external view returns (Dispute memory) {
        return disputes[settlementId];
    }

    /**
     * @notice Gets all settlements for a round
     * @param roundId The auction round ID
     */
    function getRoundSettlements(uint256 roundId) external view returns (uint256[] memory) {
        return roundSettlements[roundId];
    }

    /**
     * @notice Gets all settlements for a trader
     * @param trader The trader address
     */
    function getTraderSettlements(address trader) external view returns (uint256[] memory) {
        return traderSettlements[trader];
    }

    /**
     * @notice Gets locked funds for a trader in a round
     * @param roundId The auction round ID
     * @param trader The trader address
     */
    function getLockedFunds(uint256 roundId, address trader) external view returns (uint256) {
        return lockedFunds[roundId][trader];
    }

    /**
     * @notice Checks if settlement can be completed
     * @param settlementId The settlement ID
     */
    function canComplete(uint256 settlementId) external view returns (bool) {
        Settlement storage settlement = settlements[settlementId];
        return settlement.status == SettlementStatus.PENDING &&
               block.timestamp >= settlement.disputeDeadline;
    }

    /**
     * @notice Checks if dispute can be raised
     * @param settlementId The settlement ID
     */
    function canRaiseDispute(uint256 settlementId) external view returns (bool) {
        Settlement storage settlement = settlements[settlementId];
        return settlement.status == SettlementStatus.PENDING &&
               block.timestamp <= settlement.disputeDeadline &&
               disputes[settlementId].raisedBy == address(0);
    }

    /**
     * @notice Gets fee info for a transaction amount
     * @param amount Transaction amount
     */
    function calculateFees(uint256 amount) external view returns (
        uint256 platformFee,
        uint256 burnAmount,
        uint256 treasuryAmount,
        uint256 sellerAmount
    ) {
        platformFee = (amount * platformFeePercentage) / FEE_PRECISION;
        burnAmount = (platformFee * feeBurnPercentage) / FEE_PRECISION;
        treasuryAmount = platformFee - burnAmount;
        sellerAmount = amount - platformFee;
    }

    /**
     * @notice Gets pending settlements count for a round
     * @param roundId The auction round ID
     */
    function getPendingSettlementCount(uint256 roundId) external view returns (uint256 count) {
        uint256[] storage ids = roundSettlements[roundId];
        for (uint256 i = 0; i < ids.length; i++) {
            if (settlements[ids[i]].status == SettlementStatus.PENDING) {
                count++;
            }
        }
    }

    // ============ Admin Functions ============

    /**
     * @notice Updates platform fee percentage
     * @param newFee New fee in basis points
     */
    function setPlatformFee(uint256 newFee) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (newFee > MAX_FEE_PERCENTAGE) revert InvalidFeePercentage(newFee);

        uint256 oldFee = platformFeePercentage;
        platformFeePercentage = newFee;

        emit FeeUpdated(oldFee, newFee);
    }

    /**
     * @notice Updates fee burn percentage
     * @param newBurnPercentage New burn percentage in basis points
     */
    function setFeeBurnPercentage(uint256 newBurnPercentage) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (newBurnPercentage > FEE_PRECISION) revert InvalidBurnPercentage(newBurnPercentage);

        uint256 oldPercentage = feeBurnPercentage;
        feeBurnPercentage = newBurnPercentage;

        emit BurnPercentageUpdated(oldPercentage, newBurnPercentage);
    }

    /**
     * @notice Updates treasury address
     * @param newTreasury New treasury address
     */
    function setTreasury(address newTreasury) external onlyRole(TREASURY_ROLE) {
        if (newTreasury == address(0)) revert ZeroAddress();

        address oldTreasury = treasury;
        treasury = newTreasury;

        emit TreasuryUpdated(oldTreasury, newTreasury);
    }

    /**
     * @notice Toggles circuit breaker
     * @param active Whether to activate circuit breaker
     */
    function setCircuitBreaker(bool active) external onlyRole(DEFAULT_ADMIN_ROLE) {
        circuitBreakerActive = active;
        emit CircuitBreakerToggled(active);
    }

    /**
     * @notice Grants auction role to an address
     * @param auctionContract Address of auction contract
     */
    function setAuctionContract(address auctionContract) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (auctionContract == address(0)) revert ZeroAddress();
        _grantRole(AUCTION_ROLE, auctionContract);
    }

    /**
     * @notice Pauses the contract
     */
    function pause() external onlyRole(DEFAULT_ADMIN_ROLE) {
        _pause();
    }

    /**
     * @notice Unpauses the contract
     */
    function unpause() external onlyRole(DEFAULT_ADMIN_ROLE) {
        _unpause();
    }

    /**
     * @notice Emergency withdrawal for stuck funds (admin only, when circuit breaker active)
     * @param roundId The round ID
     * @param trader The trader address
     */
    function emergencyWithdrawFor(
        uint256 roundId,
        address trader
    ) external nonReentrant onlyRole(DEFAULT_ADMIN_ROLE) {
        if (!circuitBreakerActive) revert CircuitBreakerActive();

        uint256 amount = lockedFunds[roundId][trader];
        if (amount > 0) {
            lockedFunds[roundId][trader] = 0;
            shaktiToken.safeTransfer(trader, amount);
            emit EmergencyWithdraw(trader, amount);
        }
    }

    // ============ Internal Functions ============

    /**
     * @dev Finalizes a settlement - transfers funds
     */
    function _finalizeSettlement(uint256 settlementId) internal {
        Settlement storage settlement = settlements[settlementId];

        uint256 totalAmount = settlement.totalAmount;
        uint256 fee = settlement.platformFee;
        uint256 burnAmount = settlement.burnAmount;
        uint256 sellerAmount = totalAmount - fee;
        uint256 treasuryAmount = fee - burnAmount;

        settlement.status = SettlementStatus.COMPLETED;

        // Transfer to seller
        shaktiToken.safeTransfer(settlement.seller, sellerAmount);

        // Transfer fee to treasury
        shaktiToken.safeTransfer(treasury, treasuryAmount);

        // Burn portion
        if (burnAmount > 0) {
            shaktiToken.burn(burnAmount);
            totalTokensBurned += burnAmount;
        }

        totalFeesCollected += fee;

        emit SettlementCompleted(settlementId, settlement.seller, sellerAmount, fee, burnAmount);
    }

    /**
     * @dev Records slash against a trader
     */
    function _slashTrader(address trader, string memory reason) internal {
        slashCount[trader]++;
        emit Slashed(trader, slashCount[trader], reason);
    }
}
