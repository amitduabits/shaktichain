// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {Initializable} from "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import {ReentrancyGuardUpgradeable} from "@openzeppelin/contracts-upgradeable/utils/ReentrancyGuardUpgradeable.sol";
import {AccessControlUpgradeable} from "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import {PausableUpgradeable} from "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";
import {UUPSUpgradeable} from "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";

/**
 * @title IShaktiTokenBurnable
 * @notice Interface for ShaktiToken burn function
 */
interface IShaktiTokenBurnable is IERC20 {
    function burn(uint256 amount) external;
}

/**
 * @title EnergyEscrowUpgradeable
 * @author SHAKTI-CHAIN Team
 * @notice UUPS Upgradeable escrow for secure V2G energy trading settlements
 * @dev Handles deposits, settlements, fees, and dispute resolution
 *
 * Features:
 * - Secure fund locking during auctions
 * - Automated settlement with fee deduction
 * - 2% platform fee (70% treasury, 30% burned)
 * - 24-hour dispute window
 * - Arbiter-based dispute resolution
 * - UUPS upgradeable pattern
 */
contract EnergyEscrowUpgradeable is
    Initializable,
    ReentrancyGuardUpgradeable,
    AccessControlUpgradeable,
    PausableUpgradeable,
    UUPSUpgradeable
{
    using SafeERC20 for IERC20;
    using SafeERC20 for IShaktiTokenBurnable;

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
    bytes32 public constant UPGRADER_ROLE = keccak256("UPGRADER_ROLE");

    uint256 public constant PRICE_PRECISION = 1e18;
    uint256 public constant FEE_PRECISION = 10000;
    uint256 public constant DISPUTE_WINDOW = 24 hours;
    uint256 public constant MAX_FEE_PERCENTAGE = 1000;

    // ============ Enums ============
    enum SettlementStatus { PENDING, COMPLETED, DISPUTED, RESOLVED, REFUNDED }
    enum DisputeOutcome { NONE, BUYER_WINS, SELLER_WINS, SPLIT }

    // ============ Structs ============
    struct Settlement {
        uint256 settlementId;
        uint256 auctionRoundId;
        address buyer;
        address seller;
        uint128 quantity;
        uint128 price;
        uint256 totalAmount;
        uint256 platformFee;
        uint256 burnAmount;
        uint64 timestamp;
        uint64 disputeDeadline;
        SettlementStatus status;
        DisputeOutcome disputeOutcome;
    }

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
    IShaktiTokenBurnable public shaktiToken;
    address public treasury;
    uint256 public platformFeePercentage;
    uint256 public feeBurnPercentage;
    bool public circuitBreakerActive;
    uint256 public nextSettlementId;

    mapping(uint256 => mapping(address => uint256)) public lockedFunds;
    mapping(uint256 => Settlement) public settlements;
    mapping(uint256 => uint256[]) public roundSettlements;
    mapping(uint256 => Dispute) public disputes;
    mapping(address => uint256[]) public traderSettlements;
    mapping(address => uint256) public slashCount;

    uint256 public totalFeesCollected;
    uint256 public totalTokensBurned;

    // ============ Storage Gap ============
    uint256[40] private __gap;

    // ============ Events ============
    event Deposited(uint256 indexed roundId, address indexed trader, uint256 amount);
    event Withdrawn(uint256 indexed roundId, address indexed trader, uint256 amount);
    event SettlementCreated(uint256 indexed settlementId, uint256 indexed roundId, address indexed buyer, address seller, uint256 quantity, uint256 price, uint256 totalAmount);
    event SettlementCompleted(uint256 indexed settlementId, address indexed seller, uint256 sellerAmount, uint256 fee, uint256 burned);
    event Refunded(uint256 indexed settlementId, address indexed buyer, uint256 amount);
    event DisputeRaised(uint256 indexed settlementId, address indexed raisedBy, string reason);
    event DisputeResolved(uint256 indexed settlementId, DisputeOutcome outcome, string resolution);
    event Slashed(address indexed trader, uint256 amount, string reason);
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

    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }

    /**
     * @notice Initializes the escrow contract
     */
    function initialize(
        address _shaktiToken,
        address _treasury,
        address _admin,
        uint256 _platformFee,
        uint256 _feeBurn
    ) public initializer {
        if (_shaktiToken == address(0)) revert ZeroAddress();
        if (_treasury == address(0)) revert ZeroAddress();
        if (_admin == address(0)) revert ZeroAddress();
        if (_platformFee > MAX_FEE_PERCENTAGE) revert InvalidFeePercentage(_platformFee);
        if (_feeBurn > FEE_PRECISION) revert InvalidBurnPercentage(_feeBurn);

        __ReentrancyGuard_init();
        __AccessControl_init();
        __Pausable_init();
        __UUPSUpgradeable_init();

        shaktiToken = IShaktiTokenBurnable(_shaktiToken);
        treasury = _treasury;
        platformFeePercentage = _platformFee;
        feeBurnPercentage = _feeBurn;

        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        _grantRole(ARBITER_ROLE, _admin);
        _grantRole(TREASURY_ROLE, _admin);
        _grantRole(UPGRADER_ROLE, _admin);
    }

    // ============ Deposit Functions ============

    function deposit(uint256 roundId, uint256 amount) external nonReentrant whenNotPaused whenCircuitBreakerOff {
        if (amount == 0) revert ZeroAmount();

        shaktiToken.safeTransferFrom(msg.sender, address(this), amount);
        lockedFunds[roundId][msg.sender] += amount;

        emit Deposited(roundId, msg.sender, amount);
    }

    function depositFor(uint256 roundId, address trader, uint256 amount) external nonReentrant whenNotPaused whenCircuitBreakerOff onlyAuction {
        if (trader == address(0)) revert ZeroAddress();
        if (amount == 0) revert ZeroAmount();

        shaktiToken.safeTransferFrom(msg.sender, address(this), amount);
        lockedFunds[roundId][trader] += amount;

        emit Deposited(roundId, trader, amount);
    }

    function withdraw(uint256 roundId, uint256 amount) external nonReentrant whenNotPaused {
        if (amount == 0) revert ZeroAmount();
        uint256 available = lockedFunds[roundId][msg.sender];
        if (amount > available) revert InsufficientFunds(amount, available);

        lockedFunds[roundId][msg.sender] -= amount;
        shaktiToken.safeTransfer(msg.sender, amount);

        emit Withdrawn(roundId, msg.sender, amount);
    }

    // ============ Settlement Functions ============

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

        lockedFunds[roundId][buyer] -= totalAmount;
        roundSettlements[roundId].push(settlementId);
        traderSettlements[buyer].push(settlementId);
        traderSettlements[seller].push(settlementId);

        emit SettlementCreated(settlementId, roundId, buyer, seller, quantity, price, totalAmount);
    }

    function completeSettlement(uint256 settlementId) external nonReentrant whenNotPaused whenCircuitBreakerOff {
        Settlement storage settlement = settlements[settlementId];

        if (settlement.buyer == address(0)) revert SettlementNotFound(settlementId);
        if (settlement.status != SettlementStatus.PENDING) revert SettlementAlreadyProcessed(settlementId);
        if (block.timestamp < settlement.disputeDeadline) {
            revert DisputeWindowNotExpired(settlement.disputeDeadline, block.timestamp);
        }

        _finalizeSettlement(settlementId);
    }

    function batchCompleteSettlements(uint256[] calldata settlementIds) external nonReentrant whenNotPaused whenCircuitBreakerOff {
        for (uint256 i = 0; i < settlementIds.length; i++) {
            Settlement storage settlement = settlements[settlementIds[i]];

            if (settlement.buyer == address(0)) continue;
            if (settlement.status != SettlementStatus.PENDING) continue;
            if (block.timestamp < settlement.disputeDeadline) continue;

            _finalizeSettlement(settlementIds[i]);
        }
    }

    function refundSettlement(uint256 settlementId) external nonReentrant whenNotPaused onlyAuction {
        Settlement storage settlement = settlements[settlementId];

        if (settlement.buyer == address(0)) revert SettlementNotFound(settlementId);
        if (settlement.status != SettlementStatus.PENDING) revert SettlementAlreadyProcessed(settlementId);

        settlement.status = SettlementStatus.REFUNDED;
        shaktiToken.safeTransfer(settlement.buyer, settlement.totalAmount);

        emit Refunded(settlementId, settlement.buyer, settlement.totalAmount);
    }

    // ============ Dispute Functions ============

    function raiseDispute(uint256 settlementId, string calldata reason) external whenNotPaused {
        Settlement storage settlement = settlements[settlementId];

        if (settlement.buyer == address(0)) revert SettlementNotFound(settlementId);
        if (settlement.status != SettlementStatus.PENDING) revert SettlementAlreadyProcessed(settlementId);
        if (block.timestamp > settlement.disputeDeadline) {
            revert DisputeWindowExpired(settlement.disputeDeadline, block.timestamp);
        }
        if (msg.sender != settlement.buyer && msg.sender != settlement.seller) {
            revert NotPartyToSettlement(msg.sender, settlementId);
        }
        if (disputes[settlementId].raisedBy != address(0)) revert DisputeAlreadyRaised(settlementId);

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

    function resolveDispute(
        uint256 settlementId,
        DisputeOutcome outcome,
        string calldata resolution,
        bool slashBadActor
    ) external nonReentrant onlyRole(ARBITER_ROLE) {
        Settlement storage settlement = settlements[settlementId];
        Dispute storage dispute = disputes[settlementId];

        if (settlement.buyer == address(0)) revert SettlementNotFound(settlementId);
        if (settlement.status != SettlementStatus.DISPUTED) revert NoDisputeRaised(settlementId);

        dispute.resolved = true;
        dispute.outcome = outcome;
        dispute.resolution = resolution;
        settlement.disputeOutcome = outcome;
        settlement.status = SettlementStatus.RESOLVED;

        uint256 totalAmount = settlement.totalAmount;
        uint256 fee = settlement.platformFee;
        uint256 burnAmount = settlement.burnAmount;

        if (outcome == DisputeOutcome.BUYER_WINS) {
            shaktiToken.safeTransfer(settlement.buyer, totalAmount);
            if (slashBadActor) _slashTrader(settlement.seller, "Dispute lost - energy not delivered");
            emit Refunded(settlementId, settlement.buyer, totalAmount);
        } else if (outcome == DisputeOutcome.SELLER_WINS) {
            uint256 sellerAmount = totalAmount - fee;
            uint256 treasuryAmount = fee - burnAmount;

            shaktiToken.safeTransfer(settlement.seller, sellerAmount);
            shaktiToken.safeTransfer(treasury, treasuryAmount);

            if (burnAmount > 0) {
                shaktiToken.burn(burnAmount);
                totalTokensBurned += burnAmount;
            }

            totalFeesCollected += fee;
            if (slashBadActor) _slashTrader(settlement.buyer, "Dispute lost - false claim");
            emit SettlementCompleted(settlementId, settlement.seller, sellerAmount, fee, burnAmount);
        } else if (outcome == DisputeOutcome.SPLIT) {
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

    function getSettlement(uint256 settlementId) external view returns (Settlement memory) {
        return settlements[settlementId];
    }

    function getDispute(uint256 settlementId) external view returns (Dispute memory) {
        return disputes[settlementId];
    }

    function getRoundSettlements(uint256 roundId) external view returns (uint256[] memory) {
        return roundSettlements[roundId];
    }

    function getTraderSettlements(address trader) external view returns (uint256[] memory) {
        return traderSettlements[trader];
    }

    function getLockedFunds(uint256 roundId, address trader) external view returns (uint256) {
        return lockedFunds[roundId][trader];
    }

    function calculateFees(uint256 amount) external view returns (
        uint256 platformFee, uint256 burnAmount, uint256 treasuryAmount, uint256 sellerAmount
    ) {
        platformFee = (amount * platformFeePercentage) / FEE_PRECISION;
        burnAmount = (platformFee * feeBurnPercentage) / FEE_PRECISION;
        treasuryAmount = platformFee - burnAmount;
        sellerAmount = amount - platformFee;
    }

    function version() external pure returns (string memory) {
        return "1.0.0";
    }

    // ============ Admin Functions ============

    function setPlatformFee(uint256 newFee) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (newFee > MAX_FEE_PERCENTAGE) revert InvalidFeePercentage(newFee);
        uint256 oldFee = platformFeePercentage;
        platformFeePercentage = newFee;
        emit FeeUpdated(oldFee, newFee);
    }

    function setFeeBurnPercentage(uint256 newBurnPercentage) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (newBurnPercentage > FEE_PRECISION) revert InvalidBurnPercentage(newBurnPercentage);
        uint256 oldPercentage = feeBurnPercentage;
        feeBurnPercentage = newBurnPercentage;
        emit BurnPercentageUpdated(oldPercentage, newBurnPercentage);
    }

    function setTreasury(address newTreasury) external onlyRole(TREASURY_ROLE) {
        if (newTreasury == address(0)) revert ZeroAddress();
        address oldTreasury = treasury;
        treasury = newTreasury;
        emit TreasuryUpdated(oldTreasury, newTreasury);
    }

    function setCircuitBreaker(bool active) external onlyRole(DEFAULT_ADMIN_ROLE) {
        circuitBreakerActive = active;
        emit CircuitBreakerToggled(active);
    }

    function setAuctionContract(address auctionContract) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (auctionContract == address(0)) revert ZeroAddress();
        _grantRole(AUCTION_ROLE, auctionContract);
    }

    function pause() external onlyRole(DEFAULT_ADMIN_ROLE) { _pause(); }
    function unpause() external onlyRole(DEFAULT_ADMIN_ROLE) { _unpause(); }

    function emergencyWithdrawFor(uint256 roundId, address trader) external nonReentrant onlyRole(DEFAULT_ADMIN_ROLE) {
        if (!circuitBreakerActive) revert CircuitBreakerActive();

        uint256 amount = lockedFunds[roundId][trader];
        if (amount > 0) {
            lockedFunds[roundId][trader] = 0;
            shaktiToken.safeTransfer(trader, amount);
            emit EmergencyWithdraw(trader, amount);
        }
    }

    // ============ Internal Functions ============

    function _finalizeSettlement(uint256 settlementId) internal {
        Settlement storage settlement = settlements[settlementId];

        uint256 totalAmount = settlement.totalAmount;
        uint256 fee = settlement.platformFee;
        uint256 burnAmount = settlement.burnAmount;
        uint256 sellerAmount = totalAmount - fee;
        uint256 treasuryAmount = fee - burnAmount;

        settlement.status = SettlementStatus.COMPLETED;

        shaktiToken.safeTransfer(settlement.seller, sellerAmount);
        shaktiToken.safeTransfer(treasury, treasuryAmount);

        if (burnAmount > 0) {
            shaktiToken.burn(burnAmount);
            totalTokensBurned += burnAmount;
        }

        totalFeesCollected += fee;

        emit SettlementCompleted(settlementId, settlement.seller, sellerAmount, fee, burnAmount);
    }

    function _slashTrader(address trader, string memory reason) internal {
        slashCount[trader]++;
        emit Slashed(trader, slashCount[trader], reason);
    }

    function _authorizeUpgrade(address newImplementation) internal override onlyRole(UPGRADER_ROLE) {}
}
