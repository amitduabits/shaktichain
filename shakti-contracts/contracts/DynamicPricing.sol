// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";

/**
 * @title IPriceOracle
 * @notice Interface for PriceOracle contract
 */
interface IPriceOracle {
    function getSpotPrice() external view returns (uint256 priceInPaise, uint256 timestamp);
    function getEffectivePrice(uint256 hour) external view returns (uint256 effectivePrice);
    function getPeakMultiplier(uint256 hour) external view returns (uint256 multiplier);
    function getCurrentISTHour() external view returns (uint256 hour);
}

/**
 * @title IGridStatusOracle
 * @notice Interface for GridStatusOracle contract
 */
interface IGridStatusOracle {
    function getGridFrequency() external view returns (uint256 frequency);
    function isGridStressed() external view returns (bool stressed);
    function getV2GIncentiveMultiplier() external view returns (uint256 multiplier);
}

/**
 * @title IEnergyAuction
 * @notice Interface for EnergyAuction contract
 */
interface IEnergyAuction {
    function getTotalBidQuantity(uint256 roundId) external view returns (uint256);
    function getTotalAskQuantity(uint256 roundId) external view returns (uint256);
    function currentRoundId() external view returns (uint256);
}

/**
 * @title DynamicPricing
 * @author SHAKTI-CHAIN Team
 * @notice Dynamic pricing engine for V2G energy market
 * @dev Calculates optimal prices based on supply/demand, time, grid status, and seasons
 *
 * Pricing Formula:
 * FinalPrice = BasePrice * DemandMultiplier * TimeOfUseModifier * GridStressModifier * SeasonalModifier
 *
 * Features:
 * - Demand-based pricing (surplus/balanced/surge)
 * - Time-of-use modifiers (peak/shoulder/off-peak)
 * - Grid frequency response pricing
 * - Seasonal adjustments for Indian climate
 * - Price floors and ceilings with daily change limits
 *
 * Indian Market Specifics:
 * - Peak hours: 18:00-22:00 IST (+30%)
 * - Shoulder hours: 06:00-10:00, 14:00-18:00 IST (+10%)
 * - Off-peak hours: 22:00-06:00 IST (-20%)
 * - Summer premium: April-June (+15%)
 * - Monsoon discount: July-September (-5%)
 * - Winter premium: October-February (+5%)
 */
contract DynamicPricing is AccessControl, Pausable {
    // ============ Custom Errors ============
    error ZeroAddress();
    error InvalidMultiplier(uint256 multiplier);
    error InvalidBounds(uint256 min, uint256 max);
    error PriceExceedsDailyChangeLimit(uint256 newPrice, uint256 oldPrice, uint256 maxChange);
    error InvalidSeason(uint8 season);
    error InvalidHour(uint256 hour);
    error InvalidDemandRatio();
    error PriceOutOfBounds(uint256 price, uint256 min, uint256 max);

    // ============ Constants ============
    bytes32 public constant OPERATOR_ROLE = keccak256("OPERATOR_ROLE");
    bytes32 public constant GOVERNANCE_ROLE = keccak256("GOVERNANCE_ROLE");

    /// @notice Precision for multipliers (10000 = 1.0x)
    uint256 public constant MULTIPLIER_PRECISION = 10000;

    /// @notice Precision for ratios (1e18)
    uint256 public constant RATIO_PRECISION = 1e18;

    /// @notice Price precision (8 decimals like Chainlink)
    uint256 public constant PRICE_PRECISION = 1e8;

    /// @notice IST offset from UTC (5 hours 30 minutes)
    int256 public constant IST_OFFSET = 19800;

    /// @notice Absolute minimum price: 2 INR/kWh = 200 paise
    uint256 public constant ABSOLUTE_MIN_PRICE = 200 * PRICE_PRECISION;

    /// @notice Absolute maximum price: 15 INR/kWh = 1500 paise
    uint256 public constant ABSOLUTE_MAX_PRICE = 1500 * PRICE_PRECISION;

    /// @notice Grid frequency target (50.000 Hz = 50000 mHz)
    uint256 public constant TARGET_FREQUENCY = 50000;

    /// @notice Under-frequency threshold (49.500 Hz = 49500 mHz)
    uint256 public constant UNDER_FREQ_THRESHOLD = 49500;

    /// @notice Over-frequency threshold (50.500 Hz = 50500 mHz)
    uint256 public constant OVER_FREQ_THRESHOLD = 50500;

    // ============ Enums ============
    enum Season {
        SUMMER,     // April - June
        MONSOON,    // July - September
        AUTUMN,     // (Not used in India, placeholder)
        WINTER      // October - February
    }

    enum TimeOfUse {
        OFF_PEAK,   // 22:00 - 06:00
        SHOULDER,   // 06:00 - 10:00, 14:00 - 18:00
        PEAK        // 18:00 - 22:00
    }

    enum DemandLevel {
        SURPLUS,        // Ratio < 0.5
        LOW_DEMAND,     // Ratio 0.5 - 0.8
        BALANCED,       // Ratio 0.8 - 1.2
        MODERATE_HIGH,  // Ratio 1.2 - 1.5
        HIGH_DEMAND,    // Ratio 1.5 - 2.0
        SURGE           // Ratio > 2.0
    }

    // ============ Structs ============
    struct PriceComponents {
        uint256 basePrice;
        uint256 demandMultiplier;
        uint256 timeOfUseMultiplier;
        uint256 gridStressMultiplier;
        uint256 seasonalMultiplier;
        uint256 finalPrice;
    }

    struct DemandThresholds {
        uint256 surplusThreshold;       // 0.5 = 5000
        uint256 lowDemandThreshold;     // 0.8 = 8000
        uint256 balancedUpperThreshold; // 1.2 = 12000
        uint256 moderateHighThreshold;  // 1.5 = 15000
        uint256 highDemandThreshold;    // 2.0 = 20000
    }

    struct DailyPriceData {
        uint256 openingPrice;
        uint256 highestPrice;
        uint256 lowestPrice;
        uint256 lastPrice;
        uint64 dayStart;
        uint32 updateCount;
    }

    // ============ State Variables ============
    /// @notice Price oracle contract
    IPriceOracle public priceOracle;

    /// @notice Grid status oracle contract
    IGridStatusOracle public gridOracle;

    /// @notice Energy auction contract
    IEnergyAuction public energyAuction;

    /// @notice Demand-based multipliers (DemandLevel => multiplier)
    mapping(DemandLevel => uint256) public demandMultipliers;

    /// @notice Time-of-use multipliers (TimeOfUse => multiplier)
    mapping(TimeOfUse => uint256) public timeOfUseMultipliers;

    /// @notice Seasonal multipliers (Season => multiplier)
    mapping(Season => uint256) public seasonalMultipliers;

    /// @notice Grid stress multipliers
    uint256 public underFrequencyMultiplier;  // When grid needs power
    uint256 public overFrequencyMultiplier;   // When excess power

    /// @notice Demand thresholds
    DemandThresholds public demandThresholds;

    /// @notice Maximum daily price change (in basis points, 2000 = 20%)
    uint256 public maxDailyChange;

    /// @notice Daily price tracking
    DailyPriceData public dailyPrice;

    /// @notice Current active season (can be overridden)
    Season public currentSeason;

    /// @notice Whether to auto-detect season based on date
    bool public autoSeasonDetection;

    /// @notice Cached calculated price
    uint256 public lastCalculatedPrice;

    /// @notice Last calculation timestamp
    uint256 public lastCalculationTime;

    /// @notice Price cache duration (5 minutes)
    uint256 public priceCacheDuration;

    // ============ Events ============
    event DynamicPriceCalculated(
        uint256 indexed roundId,
        uint256 basePrice,
        uint256 finalPrice,
        uint256 demandRatio,
        DemandLevel demandLevel,
        TimeOfUse timeOfUse
    );
    event DemandMultiplierUpdated(DemandLevel indexed level, uint256 oldMultiplier, uint256 newMultiplier);
    event TimeOfUseMultiplierUpdated(TimeOfUse indexed period, uint256 oldMultiplier, uint256 newMultiplier);
    event SeasonalMultiplierUpdated(Season indexed season, uint256 oldMultiplier, uint256 newMultiplier);
    event GridStressMultiplierUpdated(bool isUnderFrequency, uint256 oldMultiplier, uint256 newMultiplier);
    event SeasonChanged(Season oldSeason, Season newSeason);
    event DailyPriceReset(uint256 openingPrice, uint256 timestamp);
    event OracleUpdated(string oracleType, address oldAddress, address newAddress);
    event MaxDailyChangeUpdated(uint256 oldMax, uint256 newMax);

    // ============ Constructor ============
    /**
     * @notice Initializes the DynamicPricing contract
     * @param _priceOracle Price oracle address
     * @param _gridOracle Grid status oracle address
     * @param _admin Admin address
     */
    constructor(
        address _priceOracle,
        address _gridOracle,
        address _admin
    ) {
        if (_priceOracle == address(0)) revert ZeroAddress();
        if (_gridOracle == address(0)) revert ZeroAddress();
        if (_admin == address(0)) revert ZeroAddress();

        priceOracle = IPriceOracle(_priceOracle);
        gridOracle = IGridStatusOracle(_gridOracle);

        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        _grantRole(OPERATOR_ROLE, _admin);
        _grantRole(GOVERNANCE_ROLE, _admin);

        // Initialize default multipliers
        _initializeDefaultMultipliers();

        // Initialize thresholds (in basis points where 10000 = 1.0)
        demandThresholds = DemandThresholds({
            surplusThreshold: 5000,       // 0.5
            lowDemandThreshold: 8000,     // 0.8
            balancedUpperThreshold: 12000, // 1.2
            moderateHighThreshold: 15000,  // 1.5
            highDemandThreshold: 20000     // 2.0
        });

        maxDailyChange = 2000; // 20%
        autoSeasonDetection = true;
        priceCacheDuration = 5 minutes;

        // Detect initial season
        currentSeason = _detectSeason();
    }

    // ============ Main Pricing Functions ============

    /**
     * @notice Calculates the dynamic price based on all factors
     * @param basePrice Base price from oracle (in paise with 8 decimals)
     * @param hour Current hour in IST (0-23)
     * @param demandRatio Ratio of bids to asks (in basis points, 10000 = 1.0)
     * @return finalPrice The calculated dynamic price
     */
    function calculateDynamicPrice(
        uint256 basePrice,
        uint256 hour,
        uint256 demandRatio
    ) external view returns (uint256 finalPrice) {
        if (hour >= 24) revert InvalidHour(hour);

        PriceComponents memory components = _calculatePriceComponents(
            basePrice,
            hour,
            demandRatio
        );

        return components.finalPrice;
    }

    /**
     * @notice Calculates dynamic price using current market state
     * @return finalPrice The calculated dynamic price
     * @return components Full breakdown of price components
     */
    function calculateCurrentDynamicPrice() external view returns (
        uint256 finalPrice,
        PriceComponents memory components
    ) {
        // Get base price from oracle
        (uint256 basePrice,) = priceOracle.getSpotPrice();

        // Get current hour
        uint256 hour = priceOracle.getCurrentISTHour();

        // Get demand ratio from auction if available
        uint256 demandRatio = _getCurrentDemandRatio();

        components = _calculatePriceComponents(basePrice, hour, demandRatio);
        finalPrice = components.finalPrice;
    }

    /**
     * @notice Gets detailed price breakdown
     * @param basePrice Base price
     * @param hour Hour in IST
     * @param demandRatio Demand ratio
     * @return components Full price component breakdown
     */
    function getPriceBreakdown(
        uint256 basePrice,
        uint256 hour,
        uint256 demandRatio
    ) external view returns (PriceComponents memory components) {
        if (hour >= 24) revert InvalidHour(hour);
        return _calculatePriceComponents(basePrice, hour, demandRatio);
    }

    /**
     * @notice Gets the current price bounds
     * @return min Minimum allowed price
     * @return max Maximum allowed price
     * @return dailyMin Minimum based on daily change limit
     * @return dailyMax Maximum based on daily change limit
     */
    function getPriceBounds() external view returns (
        uint256 min,
        uint256 max,
        uint256 dailyMin,
        uint256 dailyMax
    ) {
        min = ABSOLUTE_MIN_PRICE;
        max = ABSOLUTE_MAX_PRICE;

        if (dailyPrice.openingPrice > 0) {
            uint256 changeAmount = (dailyPrice.openingPrice * maxDailyChange) / MULTIPLIER_PRECISION;
            dailyMin = dailyPrice.openingPrice > changeAmount
                ? dailyPrice.openingPrice - changeAmount
                : ABSOLUTE_MIN_PRICE;
            dailyMax = dailyPrice.openingPrice + changeAmount;

            // Clamp to absolute bounds
            if (dailyMin < ABSOLUTE_MIN_PRICE) dailyMin = ABSOLUTE_MIN_PRICE;
            if (dailyMax > ABSOLUTE_MAX_PRICE) dailyMax = ABSOLUTE_MAX_PRICE;
        } else {
            dailyMin = min;
            dailyMax = max;
        }
    }

    /**
     * @notice Validates if a price is within acceptable bounds
     * @param price Price to validate
     * @return valid Whether price is valid
     * @return reason Reason if invalid
     */
    function validatePrice(uint256 price) external view returns (bool valid, string memory reason) {
        if (price < ABSOLUTE_MIN_PRICE) {
            return (false, "Below minimum price");
        }
        if (price > ABSOLUTE_MAX_PRICE) {
            return (false, "Above maximum price");
        }

        if (dailyPrice.openingPrice > 0) {
            uint256 changeAmount = (dailyPrice.openingPrice * maxDailyChange) / MULTIPLIER_PRECISION;
            uint256 dailyMin = dailyPrice.openingPrice > changeAmount
                ? dailyPrice.openingPrice - changeAmount
                : ABSOLUTE_MIN_PRICE;
            uint256 dailyMax = dailyPrice.openingPrice + changeAmount;

            if (price < dailyMin) {
                return (false, "Exceeds daily decrease limit");
            }
            if (price > dailyMax) {
                return (false, "Exceeds daily increase limit");
            }
        }

        return (true, "");
    }

    // ============ Demand Functions ============

    /**
     * @notice Gets the demand level based on bid/ask ratio
     * @param demandRatio Ratio in basis points (10000 = 1.0)
     * @return level The demand level classification
     */
    function getDemandLevel(uint256 demandRatio) external view returns (DemandLevel level) {
        return _getDemandLevel(demandRatio);
    }

    /**
     * @notice Gets the demand multiplier for a given ratio
     * @param demandRatio Ratio in basis points
     * @return multiplier The demand multiplier
     */
    function getDemandMultiplier(uint256 demandRatio) external view returns (uint256 multiplier) {
        DemandLevel level = _getDemandLevel(demandRatio);
        return demandMultipliers[level];
    }

    /**
     * @notice Gets current market demand ratio from auction
     * @return ratio Demand ratio (bids/asks) in basis points
     */
    function getCurrentDemandRatio() external view returns (uint256 ratio) {
        return _getCurrentDemandRatio();
    }

    // ============ Time Functions ============

    /**
     * @notice Gets the time-of-use period for a given hour
     * @param hour Hour in IST (0-23)
     * @return period The time-of-use period
     */
    function getTimeOfUsePeriod(uint256 hour) external pure returns (TimeOfUse period) {
        return _getTimeOfUsePeriod(hour);
    }

    /**
     * @notice Gets the time-of-use multiplier for a given hour
     * @param hour Hour in IST
     * @return multiplier The TOU multiplier
     */
    function getTimeOfUseMultiplier(uint256 hour) external view returns (uint256 multiplier) {
        TimeOfUse period = _getTimeOfUsePeriod(hour);
        return timeOfUseMultipliers[period];
    }

    // ============ Grid Functions ============

    /**
     * @notice Gets grid stress multiplier based on current frequency
     * @return multiplier The grid stress multiplier
     * @return isStressed Whether grid is stressed
     */
    function getGridStressMultiplier() external view returns (
        uint256 multiplier,
        bool isStressed
    ) {
        return _getGridStressMultiplier();
    }

    // ============ Season Functions ============

    /**
     * @notice Gets the current season
     * @return season Current season
     */
    function getCurrentSeason() external view returns (Season season) {
        if (autoSeasonDetection) {
            return _detectSeason();
        }
        return currentSeason;
    }

    /**
     * @notice Gets seasonal multiplier for current or specified season
     * @param season Season to query
     * @return multiplier Seasonal multiplier
     */
    function getSeasonalMultiplier(Season season) external view returns (uint256 multiplier) {
        return seasonalMultipliers[season];
    }

    /**
     * @notice Detects season based on current date
     * @return season Detected season
     */
    function detectSeason() external view returns (Season season) {
        return _detectSeason();
    }

    // ============ Update Functions ============

    /**
     * @notice Updates and caches the current dynamic price
     * @dev Called periodically or by automation
     */
    function updateCachedPrice() external whenNotPaused {
        (uint256 basePrice,) = priceOracle.getSpotPrice();
        uint256 hour = priceOracle.getCurrentISTHour();
        uint256 demandRatio = _getCurrentDemandRatio();

        PriceComponents memory components = _calculatePriceComponents(
            basePrice,
            hour,
            demandRatio
        );

        lastCalculatedPrice = components.finalPrice;
        lastCalculationTime = block.timestamp;

        // Update daily tracking
        _updateDailyPrice(components.finalPrice);

        // Get round ID if auction is set
        uint256 roundId = 0;
        if (address(energyAuction) != address(0)) {
            roundId = energyAuction.currentRoundId();
        }

        emit DynamicPriceCalculated(
            roundId,
            basePrice,
            components.finalPrice,
            demandRatio,
            _getDemandLevel(demandRatio),
            _getTimeOfUsePeriod(hour)
        );
    }

    /**
     * @notice Resets daily price tracking (called at day start)
     */
    function resetDailyPrice() external onlyRole(OPERATOR_ROLE) {
        (uint256 currentPrice,) = priceOracle.getSpotPrice();

        dailyPrice = DailyPriceData({
            openingPrice: currentPrice,
            highestPrice: currentPrice,
            lowestPrice: currentPrice,
            lastPrice: currentPrice,
            dayStart: uint64(block.timestamp),
            updateCount: 1
        });

        emit DailyPriceReset(currentPrice, block.timestamp);
    }

    // ============ Admin Functions ============

    /**
     * @notice Updates demand multiplier for a level
     * @param level Demand level
     * @param multiplier New multiplier (10000 = 1.0x)
     */
    function setDemandMultiplier(
        DemandLevel level,
        uint256 multiplier
    ) external onlyRole(GOVERNANCE_ROLE) {
        if (multiplier < 5000 || multiplier > 20000) revert InvalidMultiplier(multiplier);

        uint256 oldMultiplier = demandMultipliers[level];
        demandMultipliers[level] = multiplier;

        emit DemandMultiplierUpdated(level, oldMultiplier, multiplier);
    }

    /**
     * @notice Updates time-of-use multiplier
     * @param period Time period
     * @param multiplier New multiplier
     */
    function setTimeOfUseMultiplier(
        TimeOfUse period,
        uint256 multiplier
    ) external onlyRole(GOVERNANCE_ROLE) {
        if (multiplier < 5000 || multiplier > 20000) revert InvalidMultiplier(multiplier);

        uint256 oldMultiplier = timeOfUseMultipliers[period];
        timeOfUseMultipliers[period] = multiplier;

        emit TimeOfUseMultiplierUpdated(period, oldMultiplier, multiplier);
    }

    /**
     * @notice Updates seasonal multiplier (Governance only)
     * @param season Season to update
     * @param multiplier New multiplier
     */
    function updateSeasonalMultiplier(
        Season season,
        uint256 multiplier
    ) external onlyRole(GOVERNANCE_ROLE) {
        if (multiplier < 5000 || multiplier > 15000) revert InvalidMultiplier(multiplier);

        uint256 oldMultiplier = seasonalMultipliers[season];
        seasonalMultipliers[season] = multiplier;

        emit SeasonalMultiplierUpdated(season, oldMultiplier, multiplier);
    }

    /**
     * @notice Updates grid stress multipliers
     * @param underFreq Under-frequency multiplier
     * @param overFreq Over-frequency multiplier
     */
    function setGridStressMultipliers(
        uint256 underFreq,
        uint256 overFreq
    ) external onlyRole(GOVERNANCE_ROLE) {
        if (underFreq < 10000 || underFreq > 20000) revert InvalidMultiplier(underFreq);
        if (overFreq < 5000 || overFreq > 10000) revert InvalidMultiplier(overFreq);

        emit GridStressMultiplierUpdated(true, underFrequencyMultiplier, underFreq);
        emit GridStressMultiplierUpdated(false, overFrequencyMultiplier, overFreq);

        underFrequencyMultiplier = underFreq;
        overFrequencyMultiplier = overFreq;
    }

    /**
     * @notice Manually sets the current season
     * @param season New season
     */
    function setCurrentSeason(Season season) external onlyRole(OPERATOR_ROLE) {
        Season oldSeason = currentSeason;
        currentSeason = season;
        autoSeasonDetection = false;

        emit SeasonChanged(oldSeason, season);
    }

    /**
     * @notice Enables auto season detection
     */
    function enableAutoSeasonDetection() external onlyRole(OPERATOR_ROLE) {
        autoSeasonDetection = true;
        currentSeason = _detectSeason();
    }

    /**
     * @notice Updates max daily change limit
     * @param newMax New max change in basis points
     */
    function setMaxDailyChange(uint256 newMax) external onlyRole(GOVERNANCE_ROLE) {
        if (newMax > 5000) revert InvalidMultiplier(newMax); // Max 50%

        emit MaxDailyChangeUpdated(maxDailyChange, newMax);
        maxDailyChange = newMax;
    }

    /**
     * @notice Updates demand thresholds
     */
    function setDemandThresholds(
        uint256 surplus,
        uint256 lowDemand,
        uint256 balancedUpper,
        uint256 moderateHigh,
        uint256 highDemand
    ) external onlyRole(GOVERNANCE_ROLE) {
        if (surplus >= lowDemand || lowDemand >= balancedUpper ||
            balancedUpper >= moderateHigh || moderateHigh >= highDemand) {
            revert InvalidBounds(0, 0);
        }

        demandThresholds = DemandThresholds({
            surplusThreshold: surplus,
            lowDemandThreshold: lowDemand,
            balancedUpperThreshold: balancedUpper,
            moderateHighThreshold: moderateHigh,
            highDemandThreshold: highDemand
        });
    }

    /**
     * @notice Sets price oracle
     */
    function setPriceOracle(address oracle) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (oracle == address(0)) revert ZeroAddress();
        emit OracleUpdated("price", address(priceOracle), oracle);
        priceOracle = IPriceOracle(oracle);
    }

    /**
     * @notice Sets grid oracle
     */
    function setGridOracle(address oracle) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (oracle == address(0)) revert ZeroAddress();
        emit OracleUpdated("grid", address(gridOracle), oracle);
        gridOracle = IGridStatusOracle(oracle);
    }

    /**
     * @notice Sets energy auction contract
     */
    function setEnergyAuction(address auction) external onlyRole(DEFAULT_ADMIN_ROLE) {
        emit OracleUpdated("auction", address(energyAuction), auction);
        energyAuction = IEnergyAuction(auction);
    }

    /**
     * @notice Sets price cache duration
     */
    function setPriceCacheDuration(uint256 duration) external onlyRole(OPERATOR_ROLE) {
        priceCacheDuration = duration;
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
     * @dev Initializes default multipliers based on specifications
     */
    function _initializeDefaultMultipliers() internal {
        // Demand multipliers (10000 = 1.0x)
        demandMultipliers[DemandLevel.SURPLUS] = 7000;        // 0.7x
        demandMultipliers[DemandLevel.LOW_DEMAND] = 8500;     // 0.85x
        demandMultipliers[DemandLevel.BALANCED] = 10000;      // 1.0x
        demandMultipliers[DemandLevel.MODERATE_HIGH] = 11500; // 1.15x
        demandMultipliers[DemandLevel.HIGH_DEMAND] = 13000;   // 1.3x
        demandMultipliers[DemandLevel.SURGE] = 15000;         // 1.5x

        // Time-of-use multipliers
        timeOfUseMultipliers[TimeOfUse.OFF_PEAK] = 8000;  // -20% = 0.8x
        timeOfUseMultipliers[TimeOfUse.SHOULDER] = 11000; // +10% = 1.1x
        timeOfUseMultipliers[TimeOfUse.PEAK] = 13000;     // +30% = 1.3x

        // Seasonal multipliers
        seasonalMultipliers[Season.SUMMER] = 11500;  // +15%
        seasonalMultipliers[Season.MONSOON] = 9500;  // -5%
        seasonalMultipliers[Season.AUTUMN] = 10000;  // Neutral
        seasonalMultipliers[Season.WINTER] = 10500;  // +5%

        // Grid stress multipliers
        underFrequencyMultiplier = 15000; // +50%
        overFrequencyMultiplier = 7000;   // -30%
    }

    /**
     * @dev Calculates all price components
     */
    function _calculatePriceComponents(
        uint256 basePrice,
        uint256 hour,
        uint256 demandRatio
    ) internal view returns (PriceComponents memory components) {
        components.basePrice = basePrice;

        // Get demand multiplier
        DemandLevel level = _getDemandLevel(demandRatio);
        components.demandMultiplier = demandMultipliers[level];

        // Get time-of-use multiplier
        TimeOfUse period = _getTimeOfUsePeriod(hour);
        components.timeOfUseMultiplier = timeOfUseMultipliers[period];

        // Get grid stress multiplier
        (components.gridStressMultiplier,) = _getGridStressMultiplier();

        // Get seasonal multiplier
        Season season = autoSeasonDetection ? _detectSeason() : currentSeason;
        components.seasonalMultiplier = seasonalMultipliers[season];

        // Calculate final price
        // FinalPrice = Base * Demand * TOU * GridStress * Seasonal / (PRECISION^4)
        uint256 price = basePrice;
        price = (price * components.demandMultiplier) / MULTIPLIER_PRECISION;
        price = (price * components.timeOfUseMultiplier) / MULTIPLIER_PRECISION;
        price = (price * components.gridStressMultiplier) / MULTIPLIER_PRECISION;
        price = (price * components.seasonalMultiplier) / MULTIPLIER_PRECISION;

        // Apply bounds
        components.finalPrice = _applyPriceBounds(price);
    }

    /**
     * @dev Gets demand level from ratio
     */
    function _getDemandLevel(uint256 demandRatio) internal view returns (DemandLevel) {
        if (demandRatio < demandThresholds.surplusThreshold) {
            return DemandLevel.SURPLUS;
        } else if (demandRatio < demandThresholds.lowDemandThreshold) {
            return DemandLevel.LOW_DEMAND;
        } else if (demandRatio < demandThresholds.balancedUpperThreshold) {
            return DemandLevel.BALANCED;
        } else if (demandRatio < demandThresholds.moderateHighThreshold) {
            return DemandLevel.MODERATE_HIGH;
        } else if (demandRatio < demandThresholds.highDemandThreshold) {
            return DemandLevel.HIGH_DEMAND;
        } else {
            return DemandLevel.SURGE;
        }
    }

    /**
     * @dev Gets time-of-use period from hour
     */
    function _getTimeOfUsePeriod(uint256 hour) internal pure returns (TimeOfUse) {
        // Peak: 18:00 - 22:00
        if (hour >= 18 && hour < 22) {
            return TimeOfUse.PEAK;
        }
        // Shoulder: 06:00 - 10:00, 14:00 - 18:00
        if ((hour >= 6 && hour < 10) || (hour >= 14 && hour < 18)) {
            return TimeOfUse.SHOULDER;
        }
        // Off-peak: 22:00 - 06:00
        return TimeOfUse.OFF_PEAK;
    }

    /**
     * @dev Gets grid stress multiplier
     */
    function _getGridStressMultiplier() internal view returns (uint256 multiplier, bool isStressed) {
        uint256 frequency = gridOracle.getGridFrequency();

        if (frequency < UNDER_FREQ_THRESHOLD) {
            return (underFrequencyMultiplier, true);
        } else if (frequency > OVER_FREQ_THRESHOLD) {
            return (overFrequencyMultiplier, true);
        }

        return (MULTIPLIER_PRECISION, false);
    }

    /**
     * @dev Detects current season based on month
     */
    function _detectSeason() internal view returns (Season) {
        // Get current month from timestamp
        // Using IST offset
        uint256 istTime = block.timestamp + uint256(IST_OFFSET);
        uint256 daysSinceEpoch = istTime / 1 days;

        // Approximate month calculation
        // This is a simplified calculation; in production, use a proper date library
        uint256 year = 1970 + (daysSinceEpoch / 365);
        uint256 dayOfYear = daysSinceEpoch % 365;

        // Month approximation (30-day months)
        uint256 month = (dayOfYear / 30) + 1;
        if (month > 12) month = 12;

        // Summer: April (4) - June (6)
        if (month >= 4 && month <= 6) {
            return Season.SUMMER;
        }
        // Monsoon: July (7) - September (9)
        if (month >= 7 && month <= 9) {
            return Season.MONSOON;
        }
        // Winter: October (10) - February (2)
        // October, November, December, January, February
        if (month >= 10 || month <= 2) {
            return Season.WINTER;
        }
        // March is transition, use Autumn as neutral
        return Season.AUTUMN;
    }

    /**
     * @dev Gets current demand ratio from auction
     */
    function _getCurrentDemandRatio() internal view returns (uint256) {
        if (address(energyAuction) == address(0)) {
            return MULTIPLIER_PRECISION; // Default to balanced (1.0)
        }

        try energyAuction.currentRoundId() returns (uint256 roundId) {
            if (roundId == 0) return MULTIPLIER_PRECISION;

            uint256 totalBids = energyAuction.getTotalBidQuantity(roundId);
            uint256 totalAsks = energyAuction.getTotalAskQuantity(roundId);

            if (totalAsks == 0) {
                return totalBids > 0 ? 30000 : MULTIPLIER_PRECISION; // Surge if bids but no asks
            }

            return (totalBids * MULTIPLIER_PRECISION) / totalAsks;
        } catch {
            return MULTIPLIER_PRECISION;
        }
    }

    /**
     * @dev Applies price bounds (absolute and daily limits)
     */
    function _applyPriceBounds(uint256 price) internal view returns (uint256) {
        // Apply absolute bounds
        if (price < ABSOLUTE_MIN_PRICE) {
            price = ABSOLUTE_MIN_PRICE;
        }
        if (price > ABSOLUTE_MAX_PRICE) {
            price = ABSOLUTE_MAX_PRICE;
        }

        // Apply daily change limits if we have opening price
        if (dailyPrice.openingPrice > 0) {
            uint256 changeAmount = (dailyPrice.openingPrice * maxDailyChange) / MULTIPLIER_PRECISION;
            uint256 dailyMin = dailyPrice.openingPrice > changeAmount
                ? dailyPrice.openingPrice - changeAmount
                : ABSOLUTE_MIN_PRICE;
            uint256 dailyMax = dailyPrice.openingPrice + changeAmount;

            if (price < dailyMin) {
                price = dailyMin;
            }
            if (price > dailyMax) {
                price = dailyMax;
            }
        }

        return price;
    }

    /**
     * @dev Updates daily price tracking
     */
    function _updateDailyPrice(uint256 price) internal {
        // Check if new day
        if (dailyPrice.dayStart == 0 ||
            block.timestamp - dailyPrice.dayStart > 1 days) {
            dailyPrice = DailyPriceData({
                openingPrice: price,
                highestPrice: price,
                lowestPrice: price,
                lastPrice: price,
                dayStart: uint64(block.timestamp),
                updateCount: 1
            });
        } else {
            if (price > dailyPrice.highestPrice) {
                dailyPrice.highestPrice = price;
            }
            if (price < dailyPrice.lowestPrice) {
                dailyPrice.lowestPrice = price;
            }
            dailyPrice.lastPrice = price;
            dailyPrice.updateCount++;
        }
    }
}
