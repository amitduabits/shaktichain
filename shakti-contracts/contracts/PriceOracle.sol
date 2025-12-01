// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";

/**
 * @title AggregatorV3Interface
 * @notice Chainlink Price Feed interface
 */
interface AggregatorV3Interface {
    function decimals() external view returns (uint8);
    function description() external view returns (string memory);
    function version() external view returns (uint256);
    function getRoundData(uint80 _roundId) external view returns (
        uint80 roundId,
        int256 answer,
        uint256 startedAt,
        uint256 updatedAt,
        uint80 answeredInRound
    );
    function latestRoundData() external view returns (
        uint80 roundId,
        int256 answer,
        uint256 startedAt,
        uint256 updatedAt,
        uint80 answeredInRound
    );
}

/**
 * @title PriceOracle
 * @author SHAKTI-CHAIN Team
 * @notice Oracle contract for electricity spot prices using Chainlink
 * @dev Integrates with IEX (Indian Energy Exchange) via Chainlink Functions
 *
 * Features:
 * - Chainlink price feed integration
 * - Time-weighted average price (TWAP) fallback
 * - Price bounds validation (outlier rejection)
 * - Peak/off-peak hour multipliers for Indian market
 * - Historical price storage (last 24 hours)
 *
 * Indian Market Specifics:
 * - Peak hours: 18:00-22:00 IST (1.5x multiplier)
 * - Off-peak hours: 00:00-06:00 IST (0.7x multiplier)
 * - Standard hours: All other times (1.0x multiplier)
 */
contract PriceOracle is AccessControl, Pausable {
    // ============ Custom Errors ============
    error ZeroAddress();
    error InvalidPrice(int256 price);
    error StalePrice(uint256 updatedAt, uint256 currentTime);
    error PriceOutOfBounds(uint256 price, uint256 minPrice, uint256 maxPrice);
    error InvalidBounds(uint256 minPrice, uint256 maxPrice);
    error InvalidMultiplier(uint256 multiplier);
    error InvalidHour(uint256 hour);
    error ArrayLengthMismatch();

    // ============ Constants ============
    bytes32 public constant OPERATOR_ROLE = keccak256("OPERATOR_ROLE");
    bytes32 public constant PRICE_UPDATER_ROLE = keccak256("PRICE_UPDATER_ROLE");

    /// @notice Price precision (1e8 for 8 decimals like Chainlink)
    uint256 public constant PRICE_PRECISION = 1e8;

    /// @notice Multiplier precision (10000 = 1.0x)
    uint256 public constant MULTIPLIER_PRECISION = 10000;

    /// @notice Maximum staleness for price feeds (5 minutes)
    uint256 public constant MAX_STALENESS = 5 minutes;

    /// @notice Number of hours in a day for historical storage
    uint256 public constant HOURS_IN_DAY = 24;

    /// @notice IST offset from UTC (5 hours 30 minutes = 19800 seconds)
    int256 public constant IST_OFFSET = 19800;

    // ============ Structs ============
    struct PriceData {
        uint128 price;          // Price in paise (1/100 INR)
        uint64 timestamp;       // Timestamp of price update
        uint64 roundId;         // Chainlink round ID
    }

    struct HourlyPrice {
        uint128 price;          // Average price for the hour
        uint64 timestamp;       // Hour start timestamp
        uint32 sampleCount;     // Number of samples in this hour
    }

    // ============ State Variables ============
    /// @notice Primary Chainlink price feed
    AggregatorV3Interface public primaryPriceFeed;

    /// @notice Backup Chainlink price feed
    AggregatorV3Interface public backupPriceFeed;

    /// @notice Minimum valid price (in paise, 8 decimals) - 1 INR/kWh = 100 paise
    uint256 public minPrice;

    /// @notice Maximum valid price (in paise, 8 decimals) - 20 INR/kWh = 2000 paise
    uint256 public maxPrice;

    /// @notice Deviation threshold for outlier rejection (in basis points, 1000 = 10%)
    uint256 public deviationThreshold;

    /// @notice Latest validated price data
    PriceData public latestPrice;

    /// @notice Time-weighted average price (fallback)
    uint256 public twapPrice;

    /// @notice Historical prices by hour (0-23)
    mapping(uint256 => HourlyPrice) public hourlyPrices;

    /// @notice Peak hour multipliers (hour => multiplier)
    mapping(uint256 => uint256) public hourMultipliers;

    /// @notice Manual price override (for emergencies)
    uint256 public manualPriceOverride;

    /// @notice Whether manual override is active
    bool public manualOverrideActive;

    /// @notice Last TWAP calculation timestamp
    uint256 public lastTwapUpdate;

    /// @notice TWAP window size
    uint256 public twapWindow;

    // ============ Events ============
    event PriceUpdated(
        uint256 indexed price,
        uint256 timestamp,
        uint256 roundId,
        address indexed source
    );
    event TWAPUpdated(uint256 oldTwap, uint256 newTwap, uint256 timestamp);
    event PriceBoundsUpdated(uint256 oldMin, uint256 oldMax, uint256 newMin, uint256 newMax);
    event DeviationThresholdUpdated(uint256 oldThreshold, uint256 newThreshold);
    event MultiplierUpdated(uint256 indexed hour, uint256 oldMultiplier, uint256 newMultiplier);
    event ManualOverrideSet(uint256 price, bool active);
    event PriceFeedUpdated(address indexed oldFeed, address indexed newFeed, bool isPrimary);
    event HourlyPriceRecorded(uint256 indexed hour, uint256 price, uint256 sampleCount);

    // ============ Constructor ============
    /**
     * @notice Initializes the PriceOracle
     * @param _primaryFeed Primary Chainlink price feed address
     * @param _backupFeed Backup Chainlink price feed address (can be zero)
     * @param _admin Admin address
     * @param _minPrice Minimum valid price in paise (8 decimals)
     * @param _maxPrice Maximum valid price in paise (8 decimals)
     */
    constructor(
        address _primaryFeed,
        address _backupFeed,
        address _admin,
        uint256 _minPrice,
        uint256 _maxPrice
    ) {
        if (_primaryFeed == address(0)) revert ZeroAddress();
        if (_admin == address(0)) revert ZeroAddress();
        if (_minPrice >= _maxPrice) revert InvalidBounds(_minPrice, _maxPrice);

        primaryPriceFeed = AggregatorV3Interface(_primaryFeed);
        if (_backupFeed != address(0)) {
            backupPriceFeed = AggregatorV3Interface(_backupFeed);
        }

        minPrice = _minPrice;
        maxPrice = _maxPrice;
        deviationThreshold = 1000; // 10% default
        twapWindow = 1 hours;

        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        _grantRole(OPERATOR_ROLE, _admin);
        _grantRole(PRICE_UPDATER_ROLE, _admin);

        // Initialize Indian market hour multipliers
        _initializeDefaultMultipliers();
    }

    // ============ External Functions ============

    /**
     * @notice Gets the current spot price in paise
     * @return priceInPaise Current electricity price
     * @return timestamp When the price was last updated
     */
    function getSpotPrice() external view returns (uint256 priceInPaise, uint256 timestamp) {
        // Check manual override first
        if (manualOverrideActive && manualPriceOverride > 0) {
            return (manualPriceOverride, block.timestamp);
        }

        // Try primary feed
        (bool success, uint256 price, uint256 updatedAt) = _tryGetPrice(primaryPriceFeed);

        if (success) {
            return (price, updatedAt);
        }

        // Try backup feed
        if (address(backupPriceFeed) != address(0)) {
            (success, price, updatedAt) = _tryGetPrice(backupPriceFeed);
            if (success) {
                return (price, updatedAt);
            }
        }

        // Fall back to TWAP
        if (twapPrice > 0) {
            return (twapPrice, lastTwapUpdate);
        }

        // Last resort: use latest stored price
        return (uint256(latestPrice.price), uint256(latestPrice.timestamp));
    }

    /**
     * @notice Gets the effective price including peak/off-peak multiplier
     * @param hour Hour in IST (0-23)
     * @return effectivePrice Price adjusted by time-of-use multiplier
     */
    function getEffectivePrice(uint256 hour) external view returns (uint256 effectivePrice) {
        if (hour >= 24) revert InvalidHour(hour);

        (uint256 spotPrice,) = this.getSpotPrice();
        uint256 multiplier = hourMultipliers[hour];

        if (multiplier == 0) {
            multiplier = MULTIPLIER_PRECISION; // Default 1.0x
        }

        return (spotPrice * multiplier) / MULTIPLIER_PRECISION;
    }

    /**
     * @notice Gets the peak/off-peak multiplier for a given hour
     * @param hour Hour in IST (0-23)
     * @return multiplier The multiplier (10000 = 1.0x)
     */
    function getPeakMultiplier(uint256 hour) external view returns (uint256 multiplier) {
        if (hour >= 24) revert InvalidHour(hour);

        multiplier = hourMultipliers[hour];
        if (multiplier == 0) {
            multiplier = MULTIPLIER_PRECISION;
        }
    }

    /**
     * @notice Gets historical price for a specific hour
     * @param hour Hour index (0-23)
     * @return price Average price for that hour
     * @return timestamp When this hour's data was recorded
     * @return sampleCount Number of samples
     */
    function getHistoricalPrice(uint256 hour) external view returns (
        uint256 price,
        uint256 timestamp,
        uint256 sampleCount
    ) {
        if (hour >= 24) revert InvalidHour(hour);

        HourlyPrice storage hourlyData = hourlyPrices[hour];
        return (
            uint256(hourlyData.price),
            uint256(hourlyData.timestamp),
            uint256(hourlyData.sampleCount)
        );
    }

    /**
     * @notice Gets the current IST hour
     * @return hour Current hour in IST (0-23)
     */
    function getCurrentISTHour() external view returns (uint256 hour) {
        return _getISTHour(block.timestamp);
    }

    /**
     * @notice Checks if current time is peak hours
     * @return isPeak True if current IST hour is peak (18-22)
     */
    function isPeakHour() external view returns (bool isPeak) {
        uint256 hour = _getISTHour(block.timestamp);
        return hour >= 18 && hour < 22;
    }

    /**
     * @notice Checks if current time is off-peak hours
     * @return isOffPeak True if current IST hour is off-peak (0-6)
     */
    function isOffPeakHour() external view returns (bool isOffPeak) {
        uint256 hour = _getISTHour(block.timestamp);
        return hour < 6;
    }

    /**
     * @notice Gets the 24-hour price history
     * @return prices Array of hourly prices
     * @return timestamps Array of timestamps
     */
    function get24HourHistory() external view returns (
        uint256[] memory prices,
        uint256[] memory timestamps
    ) {
        prices = new uint256[](24);
        timestamps = new uint256[](24);

        for (uint256 i = 0; i < 24; i++) {
            prices[i] = uint256(hourlyPrices[i].price);
            timestamps[i] = uint256(hourlyPrices[i].timestamp);
        }
    }

    // ============ Price Update Functions ============

    /**
     * @notice Updates price from Chainlink feed
     * @dev Called by automation or manually
     */
    function updatePrice() external whenNotPaused {
        (bool success, uint256 price, uint256 updatedAt, uint80 roundId) = _fetchAndValidatePrice();

        if (!success) {
            return; // Silently fail, keep using existing price
        }

        _updatePriceInternal(price, updatedAt, roundId);
    }

    /**
     * @notice Manually sets price (for Chainlink Functions callback or emergency)
     * @param price Price in paise (8 decimals)
     */
    function setPrice(uint256 price) external onlyRole(PRICE_UPDATER_ROLE) whenNotPaused {
        if (price < minPrice || price > maxPrice) {
            revert PriceOutOfBounds(price, minPrice, maxPrice);
        }

        _updatePriceInternal(price, block.timestamp, 0);
    }

    /**
     * @notice Updates TWAP based on recent prices
     */
    function updateTWAP() external whenNotPaused {
        uint256 newTwap = _calculateTWAP();

        if (newTwap > 0) {
            uint256 oldTwap = twapPrice;
            twapPrice = newTwap;
            lastTwapUpdate = block.timestamp;

            emit TWAPUpdated(oldTwap, newTwap, block.timestamp);
        }
    }

    /**
     * @notice Records current price to hourly history
     */
    function recordHourlyPrice() external whenNotPaused {
        uint256 currentHour = _getISTHour(block.timestamp);
        (uint256 currentPrice,) = this.getSpotPrice();

        if (currentPrice == 0) return;

        HourlyPrice storage hourlyData = hourlyPrices[currentHour];

        // If new hour, reset
        if (hourlyData.timestamp == 0 ||
            block.timestamp - hourlyData.timestamp > 1 hours) {
            hourlyData.price = uint128(currentPrice);
            hourlyData.timestamp = uint64(block.timestamp);
            hourlyData.sampleCount = 1;
        } else {
            // Update running average
            uint256 totalSamples = hourlyData.sampleCount + 1;
            uint256 newAvg = (uint256(hourlyData.price) * hourlyData.sampleCount + currentPrice) / totalSamples;
            hourlyData.price = uint128(newAvg);
            hourlyData.sampleCount = uint32(totalSamples);
        }

        emit HourlyPriceRecorded(currentHour, hourlyData.price, hourlyData.sampleCount);
    }

    // ============ Admin Functions ============

    /**
     * @notice Updates price bounds
     * @param _minPrice New minimum price
     * @param _maxPrice New maximum price
     */
    function setPriceBounds(
        uint256 _minPrice,
        uint256 _maxPrice
    ) external onlyRole(OPERATOR_ROLE) {
        if (_minPrice >= _maxPrice) revert InvalidBounds(_minPrice, _maxPrice);

        emit PriceBoundsUpdated(minPrice, maxPrice, _minPrice, _maxPrice);

        minPrice = _minPrice;
        maxPrice = _maxPrice;
    }

    /**
     * @notice Updates deviation threshold
     * @param _threshold New threshold in basis points
     */
    function setDeviationThreshold(uint256 _threshold) external onlyRole(OPERATOR_ROLE) {
        emit DeviationThresholdUpdated(deviationThreshold, _threshold);
        deviationThreshold = _threshold;
    }

    /**
     * @notice Sets hour multiplier
     * @param hour Hour (0-23)
     * @param multiplier Multiplier (10000 = 1.0x)
     */
    function setHourMultiplier(
        uint256 hour,
        uint256 multiplier
    ) external onlyRole(OPERATOR_ROLE) {
        if (hour >= 24) revert InvalidHour(hour);
        if (multiplier == 0 || multiplier > 50000) revert InvalidMultiplier(multiplier); // Max 5x

        uint256 oldMultiplier = hourMultipliers[hour];
        hourMultipliers[hour] = multiplier;

        emit MultiplierUpdated(hour, oldMultiplier, multiplier);
    }

    /**
     * @notice Batch sets hour multipliers
     * @param hourIndices Array of hour indices (0-23)
     * @param multipliers Array of multipliers
     */
    function setBatchMultipliers(
        uint256[] calldata hourIndices,
        uint256[] calldata multipliers
    ) external onlyRole(OPERATOR_ROLE) {
        if (hourIndices.length != multipliers.length) revert ArrayLengthMismatch();

        for (uint256 i = 0; i < hourIndices.length; i++) {
            if (hourIndices[i] >= 24) revert InvalidHour(hourIndices[i]);
            if (multipliers[i] == 0 || multipliers[i] > 50000) revert InvalidMultiplier(multipliers[i]);

            uint256 oldMultiplier = hourMultipliers[hourIndices[i]];
            hourMultipliers[hourIndices[i]] = multipliers[i];

            emit MultiplierUpdated(hourIndices[i], oldMultiplier, multipliers[i]);
        }
    }

    /**
     * @notice Sets manual price override
     * @param price Override price (0 to disable)
     * @param active Whether override is active
     */
    function setManualOverride(
        uint256 price,
        bool active
    ) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (active && (price < minPrice || price > maxPrice)) {
            revert PriceOutOfBounds(price, minPrice, maxPrice);
        }

        manualPriceOverride = price;
        manualOverrideActive = active;

        emit ManualOverrideSet(price, active);
    }

    /**
     * @notice Updates primary price feed
     * @param newFeed New price feed address
     */
    function setPrimaryPriceFeed(address newFeed) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (newFeed == address(0)) revert ZeroAddress();

        address oldFeed = address(primaryPriceFeed);
        primaryPriceFeed = AggregatorV3Interface(newFeed);

        emit PriceFeedUpdated(oldFeed, newFeed, true);
    }

    /**
     * @notice Updates backup price feed
     * @param newFeed New price feed address
     */
    function setBackupPriceFeed(address newFeed) external onlyRole(DEFAULT_ADMIN_ROLE) {
        address oldFeed = address(backupPriceFeed);
        backupPriceFeed = AggregatorV3Interface(newFeed);

        emit PriceFeedUpdated(oldFeed, newFeed, false);
    }

    /**
     * @notice Sets TWAP window
     * @param window New TWAP window in seconds
     */
    function setTwapWindow(uint256 window) external onlyRole(OPERATOR_ROLE) {
        twapWindow = window;
    }

    /**
     * @notice Pauses the oracle
     */
    function pause() external onlyRole(DEFAULT_ADMIN_ROLE) {
        _pause();
    }

    /**
     * @notice Unpauses the oracle
     */
    function unpause() external onlyRole(DEFAULT_ADMIN_ROLE) {
        _unpause();
    }

    // ============ Internal Functions ============

    /**
     * @dev Initializes default multipliers for Indian market
     */
    function _initializeDefaultMultipliers() internal {
        // Off-peak hours: 00:00-06:00 IST (0.7x = 7000)
        for (uint256 i = 0; i < 6; i++) {
            hourMultipliers[i] = 7000;
        }

        // Standard hours: 06:00-18:00 IST (1.0x = 10000)
        for (uint256 i = 6; i < 18; i++) {
            hourMultipliers[i] = 10000;
        }

        // Peak hours: 18:00-22:00 IST (1.5x = 15000)
        for (uint256 i = 18; i < 22; i++) {
            hourMultipliers[i] = 15000;
        }

        // Evening standard: 22:00-24:00 IST (1.0x = 10000)
        for (uint256 i = 22; i < 24; i++) {
            hourMultipliers[i] = 10000;
        }
    }

    /**
     * @dev Tries to get price from a Chainlink feed
     */
    function _tryGetPrice(
        AggregatorV3Interface feed
    ) internal view returns (bool success, uint256 price, uint256 updatedAt) {
        try feed.latestRoundData() returns (
            uint80,
            int256 answer,
            uint256,
            uint256 _updatedAt,
            uint80
        ) {
            // Validate price
            if (answer <= 0) return (false, 0, 0);

            // Check staleness
            if (block.timestamp - _updatedAt > MAX_STALENESS) return (false, 0, 0);

            uint256 priceValue = uint256(answer);

            // Validate bounds
            if (priceValue < minPrice || priceValue > maxPrice) return (false, 0, 0);

            // Check deviation from TWAP if available
            if (twapPrice > 0 && deviationThreshold > 0) {
                uint256 deviation = priceValue > twapPrice
                    ? ((priceValue - twapPrice) * 10000) / twapPrice
                    : ((twapPrice - priceValue) * 10000) / twapPrice;

                if (deviation > deviationThreshold) return (false, 0, 0);
            }

            return (true, priceValue, _updatedAt);
        } catch {
            return (false, 0, 0);
        }
    }

    /**
     * @dev Fetches and validates price from primary feed
     */
    function _fetchAndValidatePrice() internal view returns (
        bool success,
        uint256 price,
        uint256 updatedAt,
        uint80 roundId
    ) {
        try primaryPriceFeed.latestRoundData() returns (
            uint80 _roundId,
            int256 answer,
            uint256,
            uint256 _updatedAt,
            uint80
        ) {
            if (answer <= 0) return (false, 0, 0, 0);
            if (block.timestamp - _updatedAt > MAX_STALENESS) return (false, 0, 0, 0);

            uint256 priceValue = uint256(answer);
            if (priceValue < minPrice || priceValue > maxPrice) return (false, 0, 0, 0);

            return (true, priceValue, _updatedAt, _roundId);
        } catch {
            return (false, 0, 0, 0);
        }
    }

    /**
     * @dev Updates price internally
     */
    function _updatePriceInternal(
        uint256 price,
        uint256 timestamp,
        uint80 roundId
    ) internal {
        latestPrice = PriceData({
            price: uint128(price),
            timestamp: uint64(timestamp),
            roundId: uint64(roundId)
        });

        emit PriceUpdated(price, timestamp, roundId, msg.sender);
    }

    /**
     * @dev Calculates TWAP from hourly prices
     */
    function _calculateTWAP() internal view returns (uint256) {
        uint256 sum = 0;
        uint256 count = 0;
        uint256 currentTime = block.timestamp;

        for (uint256 i = 0; i < 24; i++) {
            HourlyPrice storage hourlyData = hourlyPrices[i];

            // Only include prices within TWAP window
            if (hourlyData.timestamp > 0 &&
                currentTime - hourlyData.timestamp <= twapWindow) {
                sum += uint256(hourlyData.price);
                count++;
            }
        }

        return count > 0 ? sum / count : 0;
    }

    /**
     * @dev Converts UTC timestamp to IST hour
     */
    function _getISTHour(uint256 timestamp) internal pure returns (uint256) {
        // Add IST offset (5:30 ahead of UTC)
        uint256 istTime = timestamp + uint256(IST_OFFSET);
        // Get hour of day
        return (istTime / 1 hours) % 24;
    }
}
