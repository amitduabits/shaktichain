// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";

/**
 * @title EnergyAuction
 * @author SHAKTI-CHAIN Team
 * @notice McAfee Double Auction implementation for V2G energy trading
 * @dev Implements periodic double auction mechanism for energy trading
 *
 * Mathematical Foundation:
 * - Buyers submit bids: (quantity_kWh, max_price_per_kWh)
 * - Sellers submit asks: (quantity_kWh, min_price_per_kWh)
 * - Sort bids descending by price, asks ascending by price
 * - Find clearing point where bid[i] >= ask[i]
 * - Clearing price = (bid[k] + ask[k+1]) / 2 where k is last matched pair
 *
 * Gas Optimizations:
 * - Batch processing up to 50 orders per clearMarket call
 * - Efficient storage packing
 * - Custom errors
 */
contract EnergyAuction is ReentrancyGuard, AccessControl, Pausable {
    using SafeERC20 for IERC20;

    // ============ Custom Errors ============
    error ZeroAddress();
    error ZeroAmount();
    error InvalidDuration(uint256 provided, uint256 min, uint256 max);
    error InvalidPrice(uint256 provided, uint256 min, uint256 max);
    error InvalidQuantity(uint256 provided, uint256 min, uint256 max);
    error AuctionNotOpen(uint256 roundId, AuctionState state);
    error AuctionNotClosed(uint256 roundId, AuctionState state);
    error AuctionNotClearing(uint256 roundId, AuctionState state);
    error AuctionNotEnded(uint256 roundId, uint256 endTime, uint256 currentTime);
    error AuctionAlreadyEnded(uint256 roundId);
    error InsufficientDeposit(uint256 required, uint256 available);
    error OrderNotFound(uint256 orderId);
    error NotOrderOwner(address caller, address owner);
    error OrderAlreadyMatched(uint256 orderId);
    error NoActiveAuction();
    error MaxOrdersReached(uint256 max);
    error ClearingNotComplete();
    error RoundNotFound(uint256 roundId);
    error InvalidCommitment();
    error RevealWindowInvalid(uint256 provided, uint256 max);
    error RevealWindowOpen(uint256 roundId, uint256 deadline, uint256 currentTime);
    error RevealWindowClosed(uint256 roundId, uint256 deadline, uint256 currentTime);
    error CommitmentNotFound(uint256 commitmentId);
    error AlreadyRevealed(uint256 commitmentId);
    error InvalidRevealData();
    error InvalidSettlementMatch(uint256 bidOrderId, uint256 askOrderId);
    error BatchSizeExceeded(uint256 provided, uint256 max);

    // ============ Constants ============
    bytes32 public constant AUCTIONEER_ROLE = keccak256("AUCTIONEER_ROLE");
    bytes32 public constant OPERATOR_ROLE = keccak256("OPERATOR_ROLE");

    /// @notice Minimum and maximum order quantity in Wh (1 kWh = 1000 Wh)
    uint256 public constant MIN_QUANTITY = 1000; // 1 kWh in Wh
    uint256 public constant MAX_QUANTITY = 100000; // 100 kWh in Wh

    /// @notice Price precision (prices in wei per Wh, scaled by 1e18)
    uint256 public constant PRICE_PRECISION = 1e18;

    /// @notice Minimum and maximum auction duration in seconds
    uint256 public constant MIN_DURATION = 5 minutes;
    uint256 public constant MAX_DURATION = 60 minutes;

    /// @notice Maximum orders per auction round
    uint256 public constant MAX_ORDERS_PER_ROUND = 500;

    /// @notice Maximum orders to process per clearMarket call
    uint256 public constant BATCH_SIZE = 50;

    /// @notice Maximum reveal window duration
    uint256 public constant MAX_REVEAL_WINDOW = 24 hours;

    // ============ Enums ============
    enum AuctionState {
        OPEN,       // Accepting orders
        CLOSED,     // No more orders, waiting for clearing
        CLEARING,   // Clearing in progress
        SETTLED     // All matched orders settled
    }

    enum OrderStatus {
        ACTIVE,     // Order is active
        MATCHED,    // Order was matched
        CANCELLED,  // Order was cancelled
        EXPIRED     // Order expired unmatched
    }

    // ============ Structs ============
    /// @notice Order structure for bids and asks
    struct Order {
        uint256 orderId;
        address trader;
        uint128 quantity;       // Quantity in Wh
        uint128 price;          // Price per Wh (scaled by PRICE_PRECISION)
        bool isBid;             // true = buy order, false = sell order
        uint64 timestamp;
        OrderStatus status;
        uint128 matchedQuantity;
        uint128 matchedPrice;
    }

    /// @notice Auction round information
    struct AuctionRound {
        uint256 roundId;
        uint64 startTime;
        uint64 endTime;
        AuctionState state;
        uint128 clearingPrice;
        uint32 totalBids;
        uint32 totalAsks;
        uint32 matchedOrders;
        uint256 totalVolume;    // Total matched volume in Wh
    }

    /// @notice Clearing result for a single order
    struct ClearingResult {
        uint256 orderId;
        address trader;
        uint128 matchedQuantity;
        uint128 price;
        bool isBid;
    }

    /// @notice Committed order hash metadata for commit/reveal flow
    struct Commitment {
        address trader;
        bytes32 commitment;
        uint64 committedAt;
        uint64 revealDeadline;
        bool revealed;
    }

    /// @notice Operator-provided settlement pair for batch settlement
    struct SettlementMatch {
        uint256 bidOrderId;
        uint256 askOrderId;
        uint128 quantity;
    }

    // ============ State Variables ============
    /// @notice SHAKTI token for payments
    IERC20 public immutable shaktiToken;

    /// @notice Energy Registry for prosumer verification
    address public energyRegistry;

    /// @notice Current auction round ID
    uint256 public currentRoundId;

    /// @notice Price bounds (in price precision units per Wh)
    uint128 public minPrice;
    uint128 public maxPrice;

    /// @notice Mapping of round ID to auction round
    mapping(uint256 => AuctionRound) public auctionRounds;

    /// @notice Mapping of round ID to order ID to Order
    mapping(uint256 => mapping(uint256 => Order)) public orders;

    /// @notice Mapping of round ID to bid order IDs (sorted descending by price)
    mapping(uint256 => uint256[]) public bidOrderIds;

    /// @notice Mapping of round ID to ask order IDs (sorted ascending by price)
    mapping(uint256 => uint256[]) public askOrderIds;

    /// @notice Mapping of round ID to next order ID
    mapping(uint256 => uint256) public nextOrderId;

    /// @notice Mapping of trader to their active order IDs per round
    mapping(address => mapping(uint256 => uint256[])) public traderOrders;

    /// @notice Mapping of trader to their locked deposits per round
    mapping(address => mapping(uint256 => uint256)) public lockedDeposits;

    /// @notice Clearing progress tracking
    mapping(uint256 => uint256) public clearingIndex;

    /// @notice Mapping of round ID to commitment ID to commitment metadata
    mapping(uint256 => mapping(uint256 => Commitment)) public commitments;

    /// @notice Mapping of round ID to next commitment ID
    mapping(uint256 => uint256) public nextCommitmentId;

    /// @notice Outstanding (unrevealed) commitments per round
    mapping(uint256 => uint256) public outstandingCommitments;

    /// @notice Maximum reveal deadline configured for each round
    mapping(uint256 => uint64) public roundRevealDeadline;

    /// @notice Mapping of round and commitment ID to resulting revealed order ID
    mapping(uint256 => mapping(uint256 => uint256)) public commitmentOrderId;

    // ============ Events ============
    event AuctionRoundCreated(
        uint256 indexed roundId,
        uint256 startTime,
        uint256 endTime,
        uint256 duration
    );
    event AuctionRoundClosed(uint256 indexed roundId, uint256 totalBids, uint256 totalAsks);
    event AuctionCleared(
        uint256 indexed roundId,
        uint128 clearingPrice,
        uint256 matchedOrders,
        uint256 totalVolume
    );
    event AuctionSettled(uint256 indexed roundId);

    event BidSubmitted(
        uint256 indexed roundId,
        uint256 indexed orderId,
        address indexed trader,
        uint256 quantity,
        uint256 maxPrice
    );
    event AskSubmitted(
        uint256 indexed roundId,
        uint256 indexed orderId,
        address indexed trader,
        uint256 quantity,
        uint256 minPrice
    );
    event OrderCancelled(uint256 indexed roundId, uint256 indexed orderId, address indexed trader);
    event OrderMatched(
        uint256 indexed roundId,
        uint256 indexed orderId,
        address indexed trader,
        uint256 matchedQuantity,
        uint256 price,
        bool isBid
    );

    event PriceBoundsUpdated(uint128 minPrice, uint128 maxPrice);
    event DepositRefunded(address indexed trader, uint256 amount);
    event BatchBidsSubmitted(uint256 indexed roundId, address indexed trader, uint256 count);
    event BatchAsksSubmitted(uint256 indexed roundId, address indexed trader, uint256 count);
    event OrderCommitted(
        uint256 indexed roundId,
        uint256 indexed commitmentId,
        address indexed trader,
        bytes32 commitment,
        uint256 revealDeadline
    );
    event OrderRevealed(
        uint256 indexed roundId,
        uint256 indexed commitmentId,
        uint256 indexed orderId,
        address trader,
        uint256 quantity,
        uint256 price,
        bool isBid
    );
    event BatchSettled(
        uint256 indexed roundId,
        uint128 settlementPrice,
        uint256 matchedPairs,
        uint256 totalVolume
    );

    // ============ Constructor ============
    /**
     * @notice Initializes the EnergyAuction contract
     * @param _shaktiToken Address of the SHAKTI token
     * @param _energyRegistry Address of the Energy Registry
     * @param _admin Admin address
     * @param _minPrice Minimum price per Wh (scaled by PRICE_PRECISION)
     * @param _maxPrice Maximum price per Wh (scaled by PRICE_PRECISION)
     */
    constructor(
        address _shaktiToken,
        address _energyRegistry,
        address _admin,
        uint128 _minPrice,
        uint128 _maxPrice
    ) {
        if (_shaktiToken == address(0)) revert ZeroAddress();
        if (_admin == address(0)) revert ZeroAddress();
        if (_minPrice >= _maxPrice) revert InvalidPrice(_minPrice, 0, _maxPrice);

        shaktiToken = IERC20(_shaktiToken);
        energyRegistry = _energyRegistry;
        minPrice = _minPrice;
        maxPrice = _maxPrice;

        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        _grantRole(AUCTIONEER_ROLE, _admin);
        _grantRole(OPERATOR_ROLE, _admin);
    }

    // ============ Auction Management Functions ============

    /**
     * @notice Creates a new auction round
     * @param duration Duration of the auction in seconds
     * @return roundId The ID of the created auction round
     */
    function createAuctionRound(
        uint256 duration
    ) external onlyRole(AUCTIONEER_ROLE) whenNotPaused returns (uint256 roundId) {
        if (duration < MIN_DURATION || duration > MAX_DURATION) {
            revert InvalidDuration(duration, MIN_DURATION, MAX_DURATION);
        }

        // Ensure previous auction is settled
        if (currentRoundId > 0) {
            AuctionRound storage prevRound = auctionRounds[currentRoundId];
            if (prevRound.state != AuctionState.SETTLED && prevRound.state != AuctionState.OPEN) {
                // Allow creating new round if previous is still open but ended
                if (block.timestamp < prevRound.endTime) {
                    revert AuctionNotEnded(currentRoundId, prevRound.endTime, block.timestamp);
                }
            }
        }

        unchecked {
            roundId = ++currentRoundId;
        }

        auctionRounds[roundId] = AuctionRound({
            roundId: roundId,
            startTime: uint64(block.timestamp),
            endTime: uint64(block.timestamp + duration),
            state: AuctionState.OPEN,
            clearingPrice: 0,
            totalBids: 0,
            totalAsks: 0,
            matchedOrders: 0,
            totalVolume: 0
        });

        emit AuctionRoundCreated(roundId, block.timestamp, block.timestamp + duration, duration);
    }

    /**
     * @notice Deterministically computes commitment hash for commit/reveal flow
     * @param roundId Auction round ID
     * @param trader Trader address
     * @param quantity Quantity in Wh
     * @param pricePerWh Price per Wh
     * @param isBid True for bid, false for ask
     * @param nonce User-generated random nonce
     */
    function computeCommitment(
        uint256 roundId,
        address trader,
        uint256 quantity,
        uint256 pricePerWh,
        bool isBid,
        bytes32 nonce
    ) public pure returns (bytes32) {
        return keccak256(abi.encode(roundId, trader, quantity, pricePerWh, isBid, nonce));
    }

    /**
     * @notice Commits sealed order hash before round closes
     * @param roundId Auction round ID
     * @param commitmentHash Keccak commitment of reveal payload
     * @param revealWindowSeconds Reveal deadline extension after round end
     */
    function commitOrder(
        uint256 roundId,
        bytes32 commitmentHash,
        uint256 revealWindowSeconds
    ) external whenNotPaused returns (uint256 commitmentId) {
        AuctionRound storage round = auctionRounds[roundId];
        if (round.roundId == 0) revert RoundNotFound(roundId);
        if (round.state != AuctionState.OPEN) revert AuctionNotOpen(roundId, round.state);
        if (block.timestamp >= round.endTime) revert AuctionAlreadyEnded(roundId);
        if (commitmentHash == bytes32(0)) revert InvalidCommitment();
        if (revealWindowSeconds == 0 || revealWindowSeconds > MAX_REVEAL_WINDOW) {
            revert RevealWindowInvalid(revealWindowSeconds, MAX_REVEAL_WINDOW);
        }
        if (round.totalBids + round.totalAsks + outstandingCommitments[roundId] >= MAX_ORDERS_PER_ROUND) {
            revert MaxOrdersReached(MAX_ORDERS_PER_ROUND);
        }

        uint64 revealDeadline = uint64(uint256(round.endTime) + revealWindowSeconds);
        commitmentId = nextCommitmentId[roundId]++;
        commitments[roundId][commitmentId] = Commitment({
            trader: msg.sender,
            commitment: commitmentHash,
            committedAt: uint64(block.timestamp),
            revealDeadline: revealDeadline,
            revealed: false
        });
        unchecked {
            outstandingCommitments[roundId] += 1;
        }
        if (revealDeadline > roundRevealDeadline[roundId]) {
            roundRevealDeadline[roundId] = revealDeadline;
        }

        emit OrderCommitted(roundId, commitmentId, msg.sender, commitmentHash, revealDeadline);
    }

    /**
     * @notice Reveals committed order and creates active orderbook entry
     * @param roundId Auction round ID
     * @param commitmentId Commitment ID created in commit phase
     * @param quantity Quantity in Wh
     * @param pricePerWh Price per Wh
     * @param isBid True for bid, false for ask
     * @param nonce Reveal nonce used to derive commitment hash
     */
    function revealOrder(
        uint256 roundId,
        uint256 commitmentId,
        uint256 quantity,
        uint256 pricePerWh,
        bool isBid,
        bytes32 nonce
    ) external nonReentrant whenNotPaused returns (uint256 orderId) {
        AuctionRound storage round = auctionRounds[roundId];
        if (round.roundId == 0) revert RoundNotFound(roundId);
        if (round.state == AuctionState.CLEARING || round.state == AuctionState.SETTLED) {
            revert AuctionNotClosed(roundId, round.state);
        }
        if (block.timestamp < round.endTime) {
            revert AuctionNotEnded(roundId, round.endTime, block.timestamp);
        }

        Commitment storage record = commitments[roundId][commitmentId];
        if (record.trader == address(0)) revert CommitmentNotFound(commitmentId);
        if (record.trader != msg.sender) revert NotOrderOwner(msg.sender, record.trader);
        if (record.revealed) revert AlreadyRevealed(commitmentId);
        if (block.timestamp > record.revealDeadline) {
            revert RevealWindowClosed(roundId, record.revealDeadline, block.timestamp);
        }

        _validateOrder(quantity, pricePerWh);
        bytes32 expected = computeCommitment(roundId, msg.sender, quantity, pricePerWh, isBid, nonce);
        if (expected != record.commitment) revert InvalidRevealData();

        record.revealed = true;
        unchecked {
            outstandingCommitments[roundId] -= 1;
        }

        orderId = _createOrder(roundId, msg.sender, quantity, pricePerWh, isBid);
        commitmentOrderId[roundId][commitmentId] = orderId;

        emit OrderRevealed(roundId, commitmentId, orderId, msg.sender, quantity, pricePerWh, isBid);
    }

    // ============ Batch Order Structs ============
    /// @notice Struct for batch bid submission
    struct BidOrder {
        uint128 quantity;       // Quantity in Wh
        uint128 maxPricePerWh;  // Maximum price per Wh
    }

    /// @notice Struct for batch ask submission
    struct AskOrder {
        uint128 quantity;       // Quantity in Wh
        uint128 minPricePerWh;  // Minimum price per Wh
    }

    /**
     * @notice Submits a buy order (bid)
     * @param quantity Quantity in Wh
     * @param maxPricePerWh Maximum price willing to pay per Wh
     */
    function submitBid(
        uint256 quantity,
        uint256 maxPricePerWh
    ) external nonReentrant whenNotPaused returns (uint256 orderId) {
        if (currentRoundId == 0) revert NoActiveAuction();

        AuctionRound storage round = auctionRounds[currentRoundId];
        if (round.state != AuctionState.OPEN) {
            revert AuctionNotOpen(currentRoundId, round.state);
        }
        if (block.timestamp >= round.endTime) {
            revert AuctionAlreadyEnded(currentRoundId);
        }

        _validateOrder(quantity, maxPricePerWh);

        if (round.totalBids + round.totalAsks >= MAX_ORDERS_PER_ROUND) {
            revert MaxOrdersReached(MAX_ORDERS_PER_ROUND);
        }

        // Calculate required deposit (quantity * maxPrice)
        uint256 requiredDeposit = (quantity * maxPricePerWh) / PRICE_PRECISION;

        // Transfer deposit from buyer
        shaktiToken.safeTransferFrom(msg.sender, address(this), requiredDeposit);
        lockedDeposits[msg.sender][currentRoundId] += requiredDeposit;

        // Create order
        orderId = nextOrderId[currentRoundId]++;
        orders[currentRoundId][orderId] = Order({
            orderId: orderId,
            trader: msg.sender,
            quantity: uint128(quantity),
            price: uint128(maxPricePerWh),
            isBid: true,
            timestamp: uint64(block.timestamp),
            status: OrderStatus.ACTIVE,
            matchedQuantity: 0,
            matchedPrice: 0
        });

        // Insert into sorted bid list (descending by price)
        _insertBidSorted(currentRoundId, orderId, maxPricePerWh);

        round.totalBids++;
        traderOrders[msg.sender][currentRoundId].push(orderId);

        emit BidSubmitted(currentRoundId, orderId, msg.sender, quantity, maxPricePerWh);
    }

    /**
     * @notice Submits a sell order (ask)
     * @param quantity Quantity in Wh
     * @param minPricePerWh Minimum price willing to accept per Wh
     */
    function submitAsk(
        uint256 quantity,
        uint256 minPricePerWh
    ) external nonReentrant whenNotPaused returns (uint256 orderId) {
        if (currentRoundId == 0) revert NoActiveAuction();

        AuctionRound storage round = auctionRounds[currentRoundId];
        if (round.state != AuctionState.OPEN) {
            revert AuctionNotOpen(currentRoundId, round.state);
        }
        if (block.timestamp >= round.endTime) {
            revert AuctionAlreadyEnded(currentRoundId);
        }

        _validateOrder(quantity, minPricePerWh);

        if (round.totalBids + round.totalAsks >= MAX_ORDERS_PER_ROUND) {
            revert MaxOrdersReached(MAX_ORDERS_PER_ROUND);
        }

        // Create order
        orderId = nextOrderId[currentRoundId]++;
        orders[currentRoundId][orderId] = Order({
            orderId: orderId,
            trader: msg.sender,
            quantity: uint128(quantity),
            price: uint128(minPricePerWh),
            isBid: false,
            timestamp: uint64(block.timestamp),
            status: OrderStatus.ACTIVE,
            matchedQuantity: 0,
            matchedPrice: 0
        });

        // Insert into sorted ask list (ascending by price)
        _insertAskSorted(currentRoundId, orderId, minPricePerWh);

        round.totalAsks++;
        traderOrders[msg.sender][currentRoundId].push(orderId);

        emit AskSubmitted(currentRoundId, orderId, msg.sender, quantity, minPricePerWh);
    }

    /**
     * @notice Submits multiple buy orders (bids) in a single transaction
     * @param bids Array of bid orders
     * @return orderIds Array of created order IDs
     * @dev Gas efficient batch submission - saves ~20k gas per additional bid
     */
    function submitBids(
        BidOrder[] calldata bids
    ) external nonReentrant whenNotPaused returns (uint256[] memory orderIds) {
        if (currentRoundId == 0) revert NoActiveAuction();
        uint256 bidCount = bids.length;
        if (bidCount == 0) revert ZeroAmount();

        AuctionRound storage round = auctionRounds[currentRoundId];
        if (round.state != AuctionState.OPEN) {
            revert AuctionNotOpen(currentRoundId, round.state);
        }
        if (block.timestamp >= round.endTime) {
            revert AuctionAlreadyEnded(currentRoundId);
        }
        if (round.totalBids + round.totalAsks + bidCount > MAX_ORDERS_PER_ROUND) {
            revert MaxOrdersReached(MAX_ORDERS_PER_ROUND);
        }

        orderIds = new uint256[](bidCount);
        uint256 totalDeposit;

        // Calculate total deposit needed
        for (uint256 i = 0; i < bidCount;) {
            _validateOrder(bids[i].quantity, bids[i].maxPricePerWh);
            unchecked {
                totalDeposit += (uint256(bids[i].quantity) * uint256(bids[i].maxPricePerWh)) / PRICE_PRECISION;
                ++i;
            }
        }

        // Single transfer for all deposits
        shaktiToken.safeTransferFrom(msg.sender, address(this), totalDeposit);
        lockedDeposits[msg.sender][currentRoundId] += totalDeposit;

        // Create all orders
        for (uint256 i = 0; i < bidCount;) {
            uint256 orderId = nextOrderId[currentRoundId]++;
            orderIds[i] = orderId;

            orders[currentRoundId][orderId] = Order({
                orderId: orderId,
                trader: msg.sender,
                quantity: bids[i].quantity,
                price: bids[i].maxPricePerWh,
                isBid: true,
                timestamp: uint64(block.timestamp),
                status: OrderStatus.ACTIVE,
                matchedQuantity: 0,
                matchedPrice: 0
            });

            _insertBidSorted(currentRoundId, orderId, bids[i].maxPricePerWh);
            traderOrders[msg.sender][currentRoundId].push(orderId);

            emit BidSubmitted(currentRoundId, orderId, msg.sender, bids[i].quantity, bids[i].maxPricePerWh);

            unchecked { ++i; }
        }

        unchecked {
            round.totalBids += uint32(bidCount);
        }

        emit BatchBidsSubmitted(currentRoundId, msg.sender, bidCount);
    }

    /**
     * @notice Submits multiple sell orders (asks) in a single transaction
     * @param asks Array of ask orders
     * @return orderIds Array of created order IDs
     * @dev Gas efficient batch submission - saves ~20k gas per additional ask
     */
    function submitAsks(
        AskOrder[] calldata asks
    ) external nonReentrant whenNotPaused returns (uint256[] memory orderIds) {
        if (currentRoundId == 0) revert NoActiveAuction();
        uint256 askCount = asks.length;
        if (askCount == 0) revert ZeroAmount();

        AuctionRound storage round = auctionRounds[currentRoundId];
        if (round.state != AuctionState.OPEN) {
            revert AuctionNotOpen(currentRoundId, round.state);
        }
        if (block.timestamp >= round.endTime) {
            revert AuctionAlreadyEnded(currentRoundId);
        }
        if (round.totalBids + round.totalAsks + askCount > MAX_ORDERS_PER_ROUND) {
            revert MaxOrdersReached(MAX_ORDERS_PER_ROUND);
        }

        orderIds = new uint256[](askCount);

        // Create all orders
        for (uint256 i = 0; i < askCount;) {
            _validateOrder(asks[i].quantity, asks[i].minPricePerWh);

            uint256 orderId = nextOrderId[currentRoundId]++;
            orderIds[i] = orderId;

            orders[currentRoundId][orderId] = Order({
                orderId: orderId,
                trader: msg.sender,
                quantity: asks[i].quantity,
                price: asks[i].minPricePerWh,
                isBid: false,
                timestamp: uint64(block.timestamp),
                status: OrderStatus.ACTIVE,
                matchedQuantity: 0,
                matchedPrice: 0
            });

            _insertAskSorted(currentRoundId, orderId, asks[i].minPricePerWh);
            traderOrders[msg.sender][currentRoundId].push(orderId);

            emit AskSubmitted(currentRoundId, orderId, msg.sender, asks[i].quantity, asks[i].minPricePerWh);

            unchecked { ++i; }
        }

        unchecked {
            round.totalAsks += uint32(askCount);
        }

        emit BatchAsksSubmitted(currentRoundId, msg.sender, askCount);
    }

    /**
     * @notice Cancels an active order
     * @param roundId The auction round ID
     * @param orderId The order ID to cancel
     */
    function cancelOrder(
        uint256 roundId,
        uint256 orderId
    ) external nonReentrant whenNotPaused {
        AuctionRound storage round = auctionRounds[roundId];
        if (round.state != AuctionState.OPEN) {
            revert AuctionNotOpen(roundId, round.state);
        }

        Order storage order = orders[roundId][orderId];
        if (order.trader == address(0)) revert OrderNotFound(orderId);
        if (order.trader != msg.sender) revert NotOrderOwner(msg.sender, order.trader);
        if (order.status != OrderStatus.ACTIVE) revert OrderAlreadyMatched(orderId);

        order.status = OrderStatus.CANCELLED;

        // Refund deposit for bids
        if (order.isBid) {
            uint256 refund = (uint256(order.quantity) * uint256(order.price)) / PRICE_PRECISION;
            lockedDeposits[msg.sender][roundId] -= refund;
            shaktiToken.safeTransfer(msg.sender, refund);
            round.totalBids--;
            emit DepositRefunded(msg.sender, refund);
        } else {
            round.totalAsks--;
        }

        emit OrderCancelled(roundId, orderId, msg.sender);
    }

    /**
     * @notice Closes the auction round for new orders
     * @param roundId The auction round ID to close
     */
    function closeAuction(uint256 roundId) external onlyRole(AUCTIONEER_ROLE) {
        AuctionRound storage round = auctionRounds[roundId];
        if (round.state != AuctionState.OPEN) {
            revert AuctionNotOpen(roundId, round.state);
        }
        if (block.timestamp < round.endTime) {
            revert AuctionNotEnded(roundId, round.endTime, block.timestamp);
        }

        round.state = AuctionState.CLOSED;

        emit AuctionRoundClosed(roundId, round.totalBids, round.totalAsks);
    }

    /**
     * @notice Executes the McAfee double auction clearing algorithm
     * @param roundId The auction round ID to clear
     * @dev Can be called multiple times if there are many orders (batch processing)
     */
    function clearMarket(uint256 roundId) external onlyRole(OPERATOR_ROLE) nonReentrant {
        AuctionRound storage round = auctionRounds[roundId];

        uint64 revealDeadline = roundRevealDeadline[roundId];
        if (revealDeadline != 0 && outstandingCommitments[roundId] > 0 && block.timestamp < revealDeadline) {
            revert RevealWindowOpen(roundId, revealDeadline, block.timestamp);
        }

        if (round.state == AuctionState.CLOSED) {
            round.state = AuctionState.CLEARING;
        }

        if (round.state != AuctionState.CLEARING) {
            revert AuctionNotClosed(roundId, round.state);
        }

        uint256[] storage bids = bidOrderIds[roundId];
        uint256[] storage asks = askOrderIds[roundId];

        uint256 bidLen = bids.length;
        uint256 askLen = asks.length;

        if (bidLen == 0 || askLen == 0) {
            // No matching possible, mark expired and settle
            _markUnmatchedOrdersExpired(roundId);
            _finalizeClearing(roundId);
            return;
        }

        uint256 startIdx = clearingIndex[roundId];
        uint256 endIdx = startIdx + BATCH_SIZE;
        uint256 maxIdx = bidLen < askLen ? bidLen : askLen;

        if (endIdx > maxIdx) {
            endIdx = maxIdx;
        }

        // Find clearing price using McAfee algorithm
        uint128 clearingPrice = _calculateClearingPrice(roundId, bids, asks, maxIdx);

        if (clearingPrice == 0) {
            // No valid clearing price found
            _markUnmatchedOrdersExpired(roundId);
            _finalizeClearing(roundId);
            return;
        }

        round.clearingPrice = clearingPrice;

        // Process matches for this batch
        for (uint256 i = startIdx; i < endIdx; i++) {
            Order storage bid = orders[roundId][bids[i]];
            Order storage ask = orders[roundId][asks[i]];

            // Check if this pair can match at clearing price
            if (bid.status != OrderStatus.ACTIVE || ask.status != OrderStatus.ACTIVE) {
                continue;
            }

            if (bid.price >= clearingPrice && ask.price <= clearingPrice) {
                // Calculate matched quantity (minimum of both)
                uint128 matchedQty = bid.quantity < ask.quantity ? bid.quantity : ask.quantity;

                // Update orders
                bid.status = OrderStatus.MATCHED;
                bid.matchedQuantity = matchedQty;
                bid.matchedPrice = clearingPrice;

                ask.status = OrderStatus.MATCHED;
                ask.matchedQuantity = matchedQty;
                ask.matchedPrice = clearingPrice;

                round.matchedOrders += 2;
                round.totalVolume += matchedQty;

                // Process payment: buyer pays, seller receives
                uint256 payment = (uint256(matchedQty) * uint256(clearingPrice)) / PRICE_PRECISION;

                // Transfer from locked deposit to seller
                lockedDeposits[bid.trader][roundId] -= payment;
                shaktiToken.safeTransfer(ask.trader, payment);

                // Refund excess deposit to buyer
                uint256 originalDeposit = (uint256(bid.quantity) * uint256(bid.price)) / PRICE_PRECISION;
                uint256 refund = originalDeposit - payment;
                if (refund > 0) {
                    lockedDeposits[bid.trader][roundId] -= refund;
                    shaktiToken.safeTransfer(bid.trader, refund);
                }

                emit OrderMatched(roundId, bid.orderId, bid.trader, matchedQty, clearingPrice, true);
                emit OrderMatched(roundId, ask.orderId, ask.trader, matchedQty, clearingPrice, false);
            }
        }

        clearingIndex[roundId] = endIdx;

        // Check if clearing is complete
        if (endIdx >= maxIdx) {
            _markUnmatchedOrdersExpired(roundId);
            _finalizeClearing(roundId);
        }
    }

    /**
     * @notice Applies off-chain computed settlement pairs in a single operator batch
     * @param roundId Auction round ID
     * @param settlementPrice Uniform settlement price per Wh
     * @param matches Bid/ask pairings with matched quantity
     */
    function settleBatch(
        uint256 roundId,
        uint128 settlementPrice,
        SettlementMatch[] calldata matches
    ) external onlyRole(OPERATOR_ROLE) nonReentrant {
        AuctionRound storage round = auctionRounds[roundId];
        if (round.roundId == 0) revert RoundNotFound(roundId);
        if (settlementPrice < minPrice || settlementPrice > maxPrice) {
            revert InvalidPrice(settlementPrice, minPrice, maxPrice);
        }
        if (matches.length > BATCH_SIZE) {
            revert BatchSizeExceeded(matches.length, BATCH_SIZE);
        }

        uint64 revealDeadline = roundRevealDeadline[roundId];
        if (revealDeadline != 0 && outstandingCommitments[roundId] > 0 && block.timestamp < revealDeadline) {
            revert RevealWindowOpen(roundId, revealDeadline, block.timestamp);
        }

        if (round.state == AuctionState.OPEN) {
            if (block.timestamp < round.endTime) {
                revert AuctionNotEnded(roundId, round.endTime, block.timestamp);
            }
            round.state = AuctionState.CLOSED;
            emit AuctionRoundClosed(roundId, round.totalBids, round.totalAsks);
        }
        if (round.state == AuctionState.CLOSED) {
            round.state = AuctionState.CLEARING;
        }
        if (round.state != AuctionState.CLEARING) {
            revert AuctionNotClosed(roundId, round.state);
        }

        round.clearingPrice = settlementPrice;
        uint256 settledVolume;

        for (uint256 i = 0; i < matches.length; i++) {
            SettlementMatch calldata pair = matches[i];
            if (pair.quantity == 0) revert ZeroAmount();

            Order storage bid = orders[roundId][pair.bidOrderId];
            Order storage ask = orders[roundId][pair.askOrderId];
            if (
                bid.trader == address(0) ||
                ask.trader == address(0) ||
                !bid.isBid ||
                ask.isBid ||
                bid.status != OrderStatus.ACTIVE ||
                ask.status != OrderStatus.ACTIVE ||
                bid.price < settlementPrice ||
                ask.price > settlementPrice ||
                pair.quantity > bid.quantity ||
                pair.quantity > ask.quantity
            ) {
                revert InvalidSettlementMatch(pair.bidOrderId, pair.askOrderId);
            }

            bid.status = OrderStatus.MATCHED;
            bid.matchedQuantity = pair.quantity;
            bid.matchedPrice = settlementPrice;

            ask.status = OrderStatus.MATCHED;
            ask.matchedQuantity = pair.quantity;
            ask.matchedPrice = settlementPrice;

            unchecked {
                round.matchedOrders += 2;
                round.totalVolume += pair.quantity;
                settledVolume += pair.quantity;
            }

            uint256 payment = (uint256(pair.quantity) * uint256(settlementPrice)) / PRICE_PRECISION;
            lockedDeposits[bid.trader][roundId] -= payment;
            shaktiToken.safeTransfer(ask.trader, payment);

            uint256 originalDeposit = (uint256(bid.quantity) * uint256(bid.price)) / PRICE_PRECISION;
            uint256 refund = originalDeposit - payment;
            if (refund > 0) {
                lockedDeposits[bid.trader][roundId] -= refund;
                shaktiToken.safeTransfer(bid.trader, refund);
            }

            emit OrderMatched(roundId, bid.orderId, bid.trader, pair.quantity, settlementPrice, true);
            emit OrderMatched(roundId, ask.orderId, ask.trader, pair.quantity, settlementPrice, false);
        }

        _markUnmatchedOrdersExpired(roundId);
        _finalizeClearing(roundId);

        emit BatchSettled(roundId, settlementPrice, matches.length, settledVolume);
    }

    /**
     * @notice Settles remaining refunds for unmatched orders
     * @param roundId The auction round ID
     */
    function settleRefunds(uint256 roundId) external nonReentrant {
        AuctionRound storage round = auctionRounds[roundId];
        if (round.state != AuctionState.SETTLED) {
            revert ClearingNotComplete();
        }

        uint256 refund = lockedDeposits[msg.sender][roundId];
        if (refund > 0) {
            lockedDeposits[msg.sender][roundId] = 0;
            shaktiToken.safeTransfer(msg.sender, refund);
            emit DepositRefunded(msg.sender, refund);
        }
    }

    // ============ View Functions ============

    /**
     * @notice Gets the order book for a round
     * @param roundId The auction round ID
     * @return bidOrders Array of bid orders
     * @return askOrders Array of ask orders
     */
    function getOrderBook(uint256 roundId) external view returns (
        Order[] memory bidOrders,
        Order[] memory askOrders
    ) {
        uint256[] storage bidIds = bidOrderIds[roundId];
        uint256[] storage askIds = askOrderIds[roundId];

        bidOrders = new Order[](bidIds.length);
        askOrders = new Order[](askIds.length);

        for (uint256 i = 0; i < bidIds.length; i++) {
            bidOrders[i] = orders[roundId][bidIds[i]];
        }

        for (uint256 i = 0; i < askIds.length; i++) {
            askOrders[i] = orders[roundId][askIds[i]];
        }
    }

    /**
     * @notice Gets a specific order
     * @param roundId The auction round ID
     * @param orderId The order ID
     */
    function getOrder(uint256 roundId, uint256 orderId) external view returns (Order memory) {
        return orders[roundId][orderId];
    }

    /**
     * @notice Gets auction round info
     * @param roundId The auction round ID
     */
    function getAuctionRound(uint256 roundId) external view returns (AuctionRound memory) {
        return auctionRounds[roundId];
    }

    /**
     * @notice Gets trader's orders for a round
     * @param trader The trader address
     * @param roundId The auction round ID
     */
    function getTraderOrders(
        address trader,
        uint256 roundId
    ) external view returns (uint256[] memory) {
        return traderOrders[trader][roundId];
    }

    /**
     * @notice Gets the current active auction info
     */
    function getCurrentAuction() external view returns (
        uint256 roundId,
        AuctionState state,
        uint256 endTime,
        uint256 totalBids,
        uint256 totalAsks
    ) {
        if (currentRoundId == 0) {
            return (0, AuctionState.SETTLED, 0, 0, 0);
        }

        AuctionRound storage round = auctionRounds[currentRoundId];
        return (
            currentRoundId,
            round.state,
            round.endTime,
            round.totalBids,
            round.totalAsks
        );
    }

    /**
     * @notice Checks if market can clear (has matching bids and asks)
     * @param roundId The auction round ID
     */
    function canClear(uint256 roundId) external view returns (bool, uint256 potentialMatches) {
        uint256[] storage bids = bidOrderIds[roundId];
        uint256[] storage asks = askOrderIds[roundId];

        if (bids.length == 0 || asks.length == 0) {
            return (false, 0);
        }

        uint256 minLen = bids.length < asks.length ? bids.length : asks.length;

        for (uint256 i = 0; i < minLen; i++) {
            Order storage bid = orders[roundId][bids[i]];
            Order storage ask = orders[roundId][asks[i]];

            if (bid.status == OrderStatus.ACTIVE &&
                ask.status == OrderStatus.ACTIVE &&
                bid.price >= ask.price) {
                potentialMatches++;
            } else {
                break;
            }
        }

        return (potentialMatches > 0, potentialMatches);
    }

    // ============ Admin Functions ============

    /**
     * @notice Updates price bounds
     * @param _minPrice New minimum price
     * @param _maxPrice New maximum price
     */
    function setPriceBounds(
        uint128 _minPrice,
        uint128 _maxPrice
    ) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (_minPrice >= _maxPrice) revert InvalidPrice(_minPrice, 0, _maxPrice);

        minPrice = _minPrice;
        maxPrice = _maxPrice;

        emit PriceBoundsUpdated(_minPrice, _maxPrice);
    }

    /**
     * @notice Updates energy registry address
     * @param _energyRegistry New energy registry address
     */
    function setEnergyRegistry(address _energyRegistry) external onlyRole(DEFAULT_ADMIN_ROLE) {
        energyRegistry = _energyRegistry;
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

    // ============ Internal Functions ============

    /**
     * @dev Validates order parameters
     */
    function _validateOrder(uint256 quantity, uint256 price) internal view {
        if (quantity < MIN_QUANTITY || quantity > MAX_QUANTITY) {
            revert InvalidQuantity(quantity, MIN_QUANTITY, MAX_QUANTITY);
        }
        if (price < minPrice || price > maxPrice) {
            revert InvalidPrice(price, minPrice, maxPrice);
        }
    }

    /**
     * @dev Creates an order and inserts into sorted orderbook
     */
    function _createOrder(
        uint256 roundId,
        address trader,
        uint256 quantity,
        uint256 pricePerWh,
        bool isBid
    ) internal returns (uint256 orderId) {
        AuctionRound storage round = auctionRounds[roundId];
        if (round.totalBids + round.totalAsks >= MAX_ORDERS_PER_ROUND) {
            revert MaxOrdersReached(MAX_ORDERS_PER_ROUND);
        }

        if (isBid) {
            uint256 requiredDeposit = (quantity * pricePerWh) / PRICE_PRECISION;
            shaktiToken.safeTransferFrom(trader, address(this), requiredDeposit);
            lockedDeposits[trader][roundId] += requiredDeposit;
        }

        orderId = nextOrderId[roundId]++;
        orders[roundId][orderId] = Order({
            orderId: orderId,
            trader: trader,
            quantity: uint128(quantity),
            price: uint128(pricePerWh),
            isBid: isBid,
            timestamp: uint64(block.timestamp),
            status: OrderStatus.ACTIVE,
            matchedQuantity: 0,
            matchedPrice: 0
        });

        traderOrders[trader][roundId].push(orderId);

        if (isBid) {
            _insertBidSorted(roundId, orderId, pricePerWh);
            unchecked {
                round.totalBids += 1;
            }
            emit BidSubmitted(roundId, orderId, trader, quantity, pricePerWh);
        } else {
            _insertAskSorted(roundId, orderId, pricePerWh);
            unchecked {
                round.totalAsks += 1;
            }
            emit AskSubmitted(roundId, orderId, trader, quantity, pricePerWh);
        }
    }

    /**
     * @dev Inserts bid into sorted list (descending by price)
     */
    function _insertBidSorted(uint256 roundId, uint256 orderId, uint256 price) internal {
        uint256[] storage bids = bidOrderIds[roundId];
        uint256 len = bids.length;

        // Find insertion point
        uint256 insertIdx = len;
        for (uint256 i = 0; i < len; i++) {
            if (price > orders[roundId][bids[i]].price) {
                insertIdx = i;
                break;
            }
        }

        // Insert at position
        bids.push(orderId);
        for (uint256 i = len; i > insertIdx; i--) {
            bids[i] = bids[i - 1];
        }
        bids[insertIdx] = orderId;
    }

    /**
     * @dev Inserts ask into sorted list (ascending by price)
     */
    function _insertAskSorted(uint256 roundId, uint256 orderId, uint256 price) internal {
        uint256[] storage asks = askOrderIds[roundId];
        uint256 len = asks.length;

        // Find insertion point
        uint256 insertIdx = len;
        for (uint256 i = 0; i < len; i++) {
            if (price < orders[roundId][asks[i]].price) {
                insertIdx = i;
                break;
            }
        }

        // Insert at position
        asks.push(orderId);
        for (uint256 i = len; i > insertIdx; i--) {
            asks[i] = asks[i - 1];
        }
        asks[insertIdx] = orderId;
    }

    /**
     * @dev Calculates clearing price using McAfee algorithm
     * McAfee mechanism: Find the largest k where bid[k] >= ask[k]
     * Clearing price = (bid[k] + ask[k+1]) / 2 if k < n-1
     * Otherwise = (bid[k] + ask[k]) / 2
     */
    function _calculateClearingPrice(
        uint256 roundId,
        uint256[] storage bids,
        uint256[] storage asks,
        uint256 maxIdx
    ) internal view returns (uint128) {
        // Find the largest k where bid[k] >= ask[k]
        int256 k = -1;

        for (uint256 i = 0; i < maxIdx; i++) {
            Order storage bid = orders[roundId][bids[i]];
            Order storage ask = orders[roundId][asks[i]];

            if (bid.status != OrderStatus.ACTIVE || ask.status != OrderStatus.ACTIVE) {
                continue;
            }

            if (bid.price >= ask.price) {
                k = int256(i);
            } else {
                break;
            }
        }

        if (k < 0) {
            return 0; // No valid clearing
        }

        uint256 kIdx = uint256(k);
        Order storage bidK = orders[roundId][bids[kIdx]];
        Order storage askK = orders[roundId][asks[kIdx]];

        // McAfee pricing: use (bid[k] + ask[k+1]) / 2 if k+1 exists
        // This ensures individual rationality for all matched traders
        if (kIdx + 1 < maxIdx) {
            Order storage askK1 = orders[roundId][asks[kIdx + 1]];
            if (askK1.status == OrderStatus.ACTIVE) {
                // Standard McAfee: clearing price is average of marginal bid and next ask
                return uint128((uint256(bidK.price) + uint256(askK1.price)) / 2);
            }
        }

        // Fallback: average of last matched pair
        return uint128((uint256(bidK.price) + uint256(askK.price)) / 2);
    }

    /**
     * @dev Marks all unmatched orders as expired
     */
    function _markUnmatchedOrdersExpired(uint256 roundId) internal {
        uint256[] storage bids = bidOrderIds[roundId];
        uint256[] storage asks = askOrderIds[roundId];

        for (uint256 i = 0; i < bids.length; i++) {
            Order storage order = orders[roundId][bids[i]];
            if (order.status == OrderStatus.ACTIVE) {
                order.status = OrderStatus.EXPIRED;
            }
        }

        for (uint256 i = 0; i < asks.length; i++) {
            Order storage order = orders[roundId][asks[i]];
            if (order.status == OrderStatus.ACTIVE) {
                order.status = OrderStatus.EXPIRED;
            }
        }
    }

    /**
     * @dev Finalizes clearing and emits event
     */
    function _finalizeClearing(uint256 roundId) internal {
        AuctionRound storage round = auctionRounds[roundId];
        round.state = AuctionState.SETTLED;

        emit AuctionCleared(
            roundId,
            round.clearingPrice,
            round.matchedOrders,
            round.totalVolume
        );
        emit AuctionSettled(roundId);
    }
}
