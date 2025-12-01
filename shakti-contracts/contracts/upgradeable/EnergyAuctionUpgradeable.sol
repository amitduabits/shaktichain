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
 * @title EnergyAuctionUpgradeable
 * @author SHAKTI-CHAIN Team
 * @notice UUPS Upgradeable McAfee Double Auction for V2G energy trading
 * @dev Implements periodic double auction mechanism with upgrade capability
 *
 * Features:
 * - McAfee double auction algorithm
 * - Batch order submission
 * - UUPS upgradeable pattern
 * - Governance-controlled upgrades
 */
contract EnergyAuctionUpgradeable is
    Initializable,
    ReentrancyGuardUpgradeable,
    AccessControlUpgradeable,
    PausableUpgradeable,
    UUPSUpgradeable
{
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

    // ============ Constants ============
    bytes32 public constant AUCTIONEER_ROLE = keccak256("AUCTIONEER_ROLE");
    bytes32 public constant OPERATOR_ROLE = keccak256("OPERATOR_ROLE");
    bytes32 public constant UPGRADER_ROLE = keccak256("UPGRADER_ROLE");

    uint256 public constant MIN_QUANTITY = 1000;
    uint256 public constant MAX_QUANTITY = 100000;
    uint256 public constant PRICE_PRECISION = 1e18;
    uint256 public constant MIN_DURATION = 5 minutes;
    uint256 public constant MAX_DURATION = 60 minutes;
    uint256 public constant MAX_ORDERS_PER_ROUND = 500;
    uint256 public constant BATCH_SIZE = 50;

    // ============ Enums ============
    enum AuctionState { OPEN, CLOSED, CLEARING, SETTLED }
    enum OrderStatus { ACTIVE, MATCHED, CANCELLED, EXPIRED }

    // ============ Structs ============
    struct Order {
        uint256 orderId;
        address trader;
        uint128 quantity;
        uint128 price;
        bool isBid;
        uint64 timestamp;
        OrderStatus status;
        uint128 matchedQuantity;
        uint128 matchedPrice;
    }

    struct AuctionRound {
        uint256 roundId;
        uint64 startTime;
        uint64 endTime;
        AuctionState state;
        uint128 clearingPrice;
        uint32 totalBids;
        uint32 totalAsks;
        uint32 matchedOrders;
        uint256 totalVolume;
    }

    struct BidOrder {
        uint128 quantity;
        uint128 maxPricePerWh;
    }

    struct AskOrder {
        uint128 quantity;
        uint128 minPricePerWh;
    }

    // ============ State Variables ============
    IERC20 public shaktiToken;
    address public energyRegistry;
    uint256 public currentRoundId;
    uint128 public minPrice;
    uint128 public maxPrice;

    mapping(uint256 => AuctionRound) public auctionRounds;
    mapping(uint256 => mapping(uint256 => Order)) public orders;
    mapping(uint256 => uint256[]) public bidOrderIds;
    mapping(uint256 => uint256[]) public askOrderIds;
    mapping(uint256 => uint256) public nextOrderId;
    mapping(address => mapping(uint256 => uint256[])) public traderOrders;
    mapping(address => mapping(uint256 => uint256)) public lockedDeposits;
    mapping(uint256 => uint256) public clearingIndex;

    // ============ Storage Gap ============
    uint256[40] private __gap;

    // ============ Events ============
    event AuctionRoundCreated(uint256 indexed roundId, uint256 startTime, uint256 endTime, uint256 duration);
    event AuctionRoundClosed(uint256 indexed roundId, uint256 totalBids, uint256 totalAsks);
    event AuctionCleared(uint256 indexed roundId, uint128 clearingPrice, uint256 matchedOrders, uint256 totalVolume);
    event AuctionSettled(uint256 indexed roundId);
    event BidSubmitted(uint256 indexed roundId, uint256 indexed orderId, address indexed trader, uint256 quantity, uint256 maxPrice);
    event AskSubmitted(uint256 indexed roundId, uint256 indexed orderId, address indexed trader, uint256 quantity, uint256 minPrice);
    event OrderCancelled(uint256 indexed roundId, uint256 indexed orderId, address indexed trader);
    event OrderMatched(uint256 indexed roundId, uint256 indexed orderId, address indexed trader, uint256 matchedQuantity, uint256 price, bool isBid);
    event PriceBoundsUpdated(uint128 minPrice, uint128 maxPrice);
    event DepositRefunded(address indexed trader, uint256 amount);
    event BatchBidsSubmitted(uint256 indexed roundId, address indexed trader, uint256 count);
    event BatchAsksSubmitted(uint256 indexed roundId, address indexed trader, uint256 count);

    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }

    /**
     * @notice Initializes the auction contract
     */
    function initialize(
        address _shaktiToken,
        address _energyRegistry,
        address _admin,
        uint128 _minPrice,
        uint128 _maxPrice
    ) public initializer {
        if (_shaktiToken == address(0)) revert ZeroAddress();
        if (_admin == address(0)) revert ZeroAddress();
        if (_minPrice >= _maxPrice) revert InvalidPrice(_minPrice, 0, _maxPrice);

        __ReentrancyGuard_init();
        __AccessControl_init();
        __Pausable_init();
        __UUPSUpgradeable_init();

        shaktiToken = IERC20(_shaktiToken);
        energyRegistry = _energyRegistry;
        minPrice = _minPrice;
        maxPrice = _maxPrice;

        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        _grantRole(AUCTIONEER_ROLE, _admin);
        _grantRole(OPERATOR_ROLE, _admin);
        _grantRole(UPGRADER_ROLE, _admin);
    }

    // ============ Auction Management ============

    function createAuctionRound(
        uint256 duration
    ) external onlyRole(AUCTIONEER_ROLE) whenNotPaused returns (uint256 roundId) {
        if (duration < MIN_DURATION || duration > MAX_DURATION) {
            revert InvalidDuration(duration, MIN_DURATION, MAX_DURATION);
        }

        if (currentRoundId > 0) {
            AuctionRound storage prevRound = auctionRounds[currentRoundId];
            if (prevRound.state != AuctionState.SETTLED && prevRound.state != AuctionState.OPEN) {
                if (block.timestamp < prevRound.endTime) {
                    revert AuctionNotEnded(currentRoundId, prevRound.endTime, block.timestamp);
                }
            }
        }

        unchecked { roundId = ++currentRoundId; }

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

    function submitBid(
        uint256 quantity,
        uint256 maxPricePerWh
    ) external nonReentrant whenNotPaused returns (uint256 orderId) {
        if (currentRoundId == 0) revert NoActiveAuction();

        AuctionRound storage round = auctionRounds[currentRoundId];
        if (round.state != AuctionState.OPEN) revert AuctionNotOpen(currentRoundId, round.state);
        if (block.timestamp >= round.endTime) revert AuctionAlreadyEnded(currentRoundId);

        _validateOrder(quantity, maxPricePerWh);

        if (round.totalBids + round.totalAsks >= MAX_ORDERS_PER_ROUND) {
            revert MaxOrdersReached(MAX_ORDERS_PER_ROUND);
        }

        uint256 requiredDeposit = (quantity * maxPricePerWh) / PRICE_PRECISION;
        shaktiToken.safeTransferFrom(msg.sender, address(this), requiredDeposit);
        lockedDeposits[msg.sender][currentRoundId] += requiredDeposit;

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

        _insertBidSorted(currentRoundId, orderId, maxPricePerWh);
        round.totalBids++;
        traderOrders[msg.sender][currentRoundId].push(orderId);

        emit BidSubmitted(currentRoundId, orderId, msg.sender, quantity, maxPricePerWh);
    }

    function submitAsk(
        uint256 quantity,
        uint256 minPricePerWh
    ) external nonReentrant whenNotPaused returns (uint256 orderId) {
        if (currentRoundId == 0) revert NoActiveAuction();

        AuctionRound storage round = auctionRounds[currentRoundId];
        if (round.state != AuctionState.OPEN) revert AuctionNotOpen(currentRoundId, round.state);
        if (block.timestamp >= round.endTime) revert AuctionAlreadyEnded(currentRoundId);

        _validateOrder(quantity, minPricePerWh);

        if (round.totalBids + round.totalAsks >= MAX_ORDERS_PER_ROUND) {
            revert MaxOrdersReached(MAX_ORDERS_PER_ROUND);
        }

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

        _insertAskSorted(currentRoundId, orderId, minPricePerWh);
        round.totalAsks++;
        traderOrders[msg.sender][currentRoundId].push(orderId);

        emit AskSubmitted(currentRoundId, orderId, msg.sender, quantity, minPricePerWh);
    }

    function submitBids(
        BidOrder[] calldata bids
    ) external nonReentrant whenNotPaused returns (uint256[] memory orderIds) {
        if (currentRoundId == 0) revert NoActiveAuction();
        uint256 bidCount = bids.length;
        if (bidCount == 0) revert ZeroAmount();

        AuctionRound storage round = auctionRounds[currentRoundId];
        if (round.state != AuctionState.OPEN) revert AuctionNotOpen(currentRoundId, round.state);
        if (block.timestamp >= round.endTime) revert AuctionAlreadyEnded(currentRoundId);
        if (round.totalBids + round.totalAsks + bidCount > MAX_ORDERS_PER_ROUND) {
            revert MaxOrdersReached(MAX_ORDERS_PER_ROUND);
        }

        orderIds = new uint256[](bidCount);
        uint256 totalDeposit;

        for (uint256 i = 0; i < bidCount;) {
            _validateOrder(bids[i].quantity, bids[i].maxPricePerWh);
            unchecked {
                totalDeposit += (uint256(bids[i].quantity) * uint256(bids[i].maxPricePerWh)) / PRICE_PRECISION;
                ++i;
            }
        }

        shaktiToken.safeTransferFrom(msg.sender, address(this), totalDeposit);
        lockedDeposits[msg.sender][currentRoundId] += totalDeposit;

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

        unchecked { round.totalBids += uint32(bidCount); }
        emit BatchBidsSubmitted(currentRoundId, msg.sender, bidCount);
    }

    function submitAsks(
        AskOrder[] calldata asks
    ) external nonReentrant whenNotPaused returns (uint256[] memory orderIds) {
        if (currentRoundId == 0) revert NoActiveAuction();
        uint256 askCount = asks.length;
        if (askCount == 0) revert ZeroAmount();

        AuctionRound storage round = auctionRounds[currentRoundId];
        if (round.state != AuctionState.OPEN) revert AuctionNotOpen(currentRoundId, round.state);
        if (block.timestamp >= round.endTime) revert AuctionAlreadyEnded(currentRoundId);
        if (round.totalBids + round.totalAsks + askCount > MAX_ORDERS_PER_ROUND) {
            revert MaxOrdersReached(MAX_ORDERS_PER_ROUND);
        }

        orderIds = new uint256[](askCount);

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

        unchecked { round.totalAsks += uint32(askCount); }
        emit BatchAsksSubmitted(currentRoundId, msg.sender, askCount);
    }

    function cancelOrder(uint256 roundId, uint256 orderId) external nonReentrant whenNotPaused {
        AuctionRound storage round = auctionRounds[roundId];
        if (round.state != AuctionState.OPEN) revert AuctionNotOpen(roundId, round.state);

        Order storage order = orders[roundId][orderId];
        if (order.trader == address(0)) revert OrderNotFound(orderId);
        if (order.trader != msg.sender) revert NotOrderOwner(msg.sender, order.trader);
        if (order.status != OrderStatus.ACTIVE) revert OrderAlreadyMatched(orderId);

        order.status = OrderStatus.CANCELLED;

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

    function closeAuction(uint256 roundId) external onlyRole(AUCTIONEER_ROLE) {
        AuctionRound storage round = auctionRounds[roundId];
        if (round.state != AuctionState.OPEN) revert AuctionNotOpen(roundId, round.state);
        if (block.timestamp < round.endTime) revert AuctionNotEnded(roundId, round.endTime, block.timestamp);

        round.state = AuctionState.CLOSED;
        emit AuctionRoundClosed(roundId, round.totalBids, round.totalAsks);
    }

    function clearMarket(uint256 roundId) external onlyRole(OPERATOR_ROLE) nonReentrant {
        AuctionRound storage round = auctionRounds[roundId];

        if (round.state == AuctionState.CLOSED) {
            round.state = AuctionState.CLEARING;
        }
        if (round.state != AuctionState.CLEARING) revert AuctionNotClosed(roundId, round.state);

        uint256[] storage bids = bidOrderIds[roundId];
        uint256[] storage asks = askOrderIds[roundId];

        if (bids.length == 0 || asks.length == 0) {
            _markUnmatchedOrdersExpired(roundId);
            _finalizeClearing(roundId);
            return;
        }

        uint256 startIdx = clearingIndex[roundId];
        uint256 maxIdx = bids.length < asks.length ? bids.length : asks.length;
        uint256 endIdx = startIdx + BATCH_SIZE > maxIdx ? maxIdx : startIdx + BATCH_SIZE;

        uint128 clearingPrice = _calculateClearingPrice(roundId, bids, asks, maxIdx);

        if (clearingPrice == 0) {
            _markUnmatchedOrdersExpired(roundId);
            _finalizeClearing(roundId);
            return;
        }

        round.clearingPrice = clearingPrice;

        for (uint256 i = startIdx; i < endIdx; i++) {
            Order storage bid = orders[roundId][bids[i]];
            Order storage ask = orders[roundId][asks[i]];

            if (bid.status != OrderStatus.ACTIVE || ask.status != OrderStatus.ACTIVE) continue;

            if (bid.price >= clearingPrice && ask.price <= clearingPrice) {
                uint128 matchedQty = bid.quantity < ask.quantity ? bid.quantity : ask.quantity;

                bid.status = OrderStatus.MATCHED;
                bid.matchedQuantity = matchedQty;
                bid.matchedPrice = clearingPrice;

                ask.status = OrderStatus.MATCHED;
                ask.matchedQuantity = matchedQty;
                ask.matchedPrice = clearingPrice;

                round.matchedOrders += 2;
                round.totalVolume += matchedQty;

                uint256 payment = (uint256(matchedQty) * uint256(clearingPrice)) / PRICE_PRECISION;
                lockedDeposits[bid.trader][roundId] -= payment;
                shaktiToken.safeTransfer(ask.trader, payment);

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

        if (endIdx >= maxIdx) {
            _markUnmatchedOrdersExpired(roundId);
            _finalizeClearing(roundId);
        }
    }

    function settleRefunds(uint256 roundId) external nonReentrant {
        AuctionRound storage round = auctionRounds[roundId];
        if (round.state != AuctionState.SETTLED) revert ClearingNotComplete();

        uint256 refund = lockedDeposits[msg.sender][roundId];
        if (refund > 0) {
            lockedDeposits[msg.sender][roundId] = 0;
            shaktiToken.safeTransfer(msg.sender, refund);
            emit DepositRefunded(msg.sender, refund);
        }
    }

    // ============ View Functions ============

    function getOrder(uint256 roundId, uint256 orderId) external view returns (Order memory) {
        return orders[roundId][orderId];
    }

    function getAuctionRound(uint256 roundId) external view returns (AuctionRound memory) {
        return auctionRounds[roundId];
    }

    function getTraderOrders(address trader, uint256 roundId) external view returns (uint256[] memory) {
        return traderOrders[trader][roundId];
    }

    function getCurrentAuction() external view returns (
        uint256 roundId, AuctionState state, uint256 endTime, uint256 totalBids, uint256 totalAsks
    ) {
        if (currentRoundId == 0) return (0, AuctionState.SETTLED, 0, 0, 0);
        AuctionRound storage round = auctionRounds[currentRoundId];
        return (currentRoundId, round.state, round.endTime, round.totalBids, round.totalAsks);
    }

    function version() external pure returns (string memory) {
        return "1.0.0";
    }

    // ============ Admin Functions ============

    function setPriceBounds(uint128 _minPrice, uint128 _maxPrice) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (_minPrice >= _maxPrice) revert InvalidPrice(_minPrice, 0, _maxPrice);
        minPrice = _minPrice;
        maxPrice = _maxPrice;
        emit PriceBoundsUpdated(_minPrice, _maxPrice);
    }

    function setEnergyRegistry(address _energyRegistry) external onlyRole(DEFAULT_ADMIN_ROLE) {
        energyRegistry = _energyRegistry;
    }

    function pause() external onlyRole(DEFAULT_ADMIN_ROLE) { _pause(); }
    function unpause() external onlyRole(DEFAULT_ADMIN_ROLE) { _unpause(); }

    // ============ Internal Functions ============

    function _validateOrder(uint256 quantity, uint256 price) internal view {
        if (quantity < MIN_QUANTITY || quantity > MAX_QUANTITY) {
            revert InvalidQuantity(quantity, MIN_QUANTITY, MAX_QUANTITY);
        }
        if (price < minPrice || price > maxPrice) {
            revert InvalidPrice(price, minPrice, maxPrice);
        }
    }

    function _insertBidSorted(uint256 roundId, uint256 orderId, uint256 price) internal {
        uint256[] storage bids = bidOrderIds[roundId];
        uint256 len = bids.length;
        uint256 insertIdx = len;

        for (uint256 i = 0; i < len; i++) {
            if (price > orders[roundId][bids[i]].price) {
                insertIdx = i;
                break;
            }
        }

        bids.push(orderId);
        for (uint256 i = len; i > insertIdx; i--) {
            bids[i] = bids[i - 1];
        }
        bids[insertIdx] = orderId;
    }

    function _insertAskSorted(uint256 roundId, uint256 orderId, uint256 price) internal {
        uint256[] storage asks = askOrderIds[roundId];
        uint256 len = asks.length;
        uint256 insertIdx = len;

        for (uint256 i = 0; i < len; i++) {
            if (price < orders[roundId][asks[i]].price) {
                insertIdx = i;
                break;
            }
        }

        asks.push(orderId);
        for (uint256 i = len; i > insertIdx; i--) {
            asks[i] = asks[i - 1];
        }
        asks[insertIdx] = orderId;
    }

    function _calculateClearingPrice(
        uint256 roundId,
        uint256[] storage bids,
        uint256[] storage asks,
        uint256 maxIdx
    ) internal view returns (uint128) {
        int256 k = -1;

        for (uint256 i = 0; i < maxIdx; i++) {
            Order storage bid = orders[roundId][bids[i]];
            Order storage ask = orders[roundId][asks[i]];

            if (bid.status != OrderStatus.ACTIVE || ask.status != OrderStatus.ACTIVE) continue;

            if (bid.price >= ask.price) {
                k = int256(i);
            } else {
                break;
            }
        }

        if (k < 0) return 0;

        uint256 kIdx = uint256(k);
        Order storage bidK = orders[roundId][bids[kIdx]];
        Order storage askK = orders[roundId][asks[kIdx]];

        if (kIdx + 1 < maxIdx) {
            Order storage askK1 = orders[roundId][asks[kIdx + 1]];
            if (askK1.status == OrderStatus.ACTIVE) {
                return uint128((uint256(bidK.price) + uint256(askK1.price)) / 2);
            }
        }

        return uint128((uint256(bidK.price) + uint256(askK.price)) / 2);
    }

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

    function _finalizeClearing(uint256 roundId) internal {
        AuctionRound storage round = auctionRounds[roundId];
        round.state = AuctionState.SETTLED;

        emit AuctionCleared(roundId, round.clearingPrice, round.matchedOrders, round.totalVolume);
        emit AuctionSettled(roundId);
    }

    function _authorizeUpgrade(address newImplementation) internal override onlyRole(UPGRADER_ROLE) {}
}
