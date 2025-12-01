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
 * @title GridStatusOracle
 * @author SHAKTI-CHAIN Team
 * @notice Oracle contract for real-time grid status monitoring
 * @dev Monitors grid frequency, demand levels, and renewable mix
 *
 * Features:
 * - Grid frequency monitoring (target: 50.00 Hz)
 * - Demand level classification (LOW, NORMAL, HIGH, CRITICAL)
 * - Renewable energy mix percentage
 * - Grid stress detection for V2G dispatch optimization
 * - Historical status storage
 *
 * Indian Grid Specifics:
 * - Target frequency: 50.00 Hz
 * - Normal range: 49.90 - 50.05 Hz
 * - Under-frequency: < 49.90 Hz (needs V2G injection)
 * - Over-frequency: > 50.05 Hz (can absorb from grid)
 *
 * Heartbeat: 1 minute for grid status
 * Deviation threshold: 0.1 Hz triggers alert
 */
contract GridStatusOracle is AccessControl, Pausable {
    // ============ Custom Errors ============
    error ZeroAddress();
    error InvalidFrequency(uint256 frequency);
    error InvalidRenewableMix(uint256 mix);
    error StaleData(uint256 updatedAt, uint256 currentTime);
    error InvalidThreshold(uint256 threshold);
    error InvalidDemandLevel();

    // ============ Constants ============
    bytes32 public constant OPERATOR_ROLE = keccak256("OPERATOR_ROLE");
    bytes32 public constant GRID_UPDATER_ROLE = keccak256("GRID_UPDATER_ROLE");

    /// @notice Frequency precision (1e3 for mHz, so 50000 = 50.000 Hz)
    uint256 public constant FREQUENCY_PRECISION = 1000;

    /// @notice Target grid frequency (50.000 Hz = 50000 mHz)
    uint256 public constant TARGET_FREQUENCY = 50000;

    /// @notice Percentage precision (10000 = 100%)
    uint256 public constant PERCENTAGE_PRECISION = 10000;

    /// @notice Maximum staleness for grid data (1 minute)
    uint256 public constant MAX_STALENESS = 1 minutes;

    /// @notice Minimum valid frequency (47.000 Hz)
    uint256 public constant MIN_FREQUENCY = 47000;

    /// @notice Maximum valid frequency (53.000 Hz)
    uint256 public constant MAX_FREQUENCY = 53000;

    // ============ Enums ============
    enum DemandLevel {
        LOW,        // Below 60% of peak demand
        NORMAL,     // 60-80% of peak demand
        HIGH,       // 80-95% of peak demand
        CRITICAL    // Above 95% of peak demand
    }

    enum GridCondition {
        STABLE,         // Normal operation
        UNDER_FREQUENCY,// Needs more generation (V2G injection)
        OVER_FREQUENCY, // Excess generation (can charge)
        STRESSED,       // High demand + frequency deviation
        EMERGENCY       // Critical - restrict non-essential loads
    }

    // ============ Structs ============
    struct GridStatus {
        uint64 frequency;           // Grid frequency in mHz
        uint64 timestamp;           // Timestamp of update
        DemandLevel demandLevel;    // Current demand level
        GridCondition condition;    // Overall grid condition
        uint16 renewableMix;        // Renewable percentage (0-10000 = 0-100%)
        uint16 loadFactor;          // Current load as % of capacity
        bool v2gRecommended;        // Whether V2G discharge is recommended
        bool chargingRecommended;   // Whether EV charging is recommended
    }

    struct FrequencyThresholds {
        uint64 underFrequencyAlert;  // Alert threshold (e.g., 49900 = 49.90 Hz)
        uint64 underFrequencyCritical; // Critical threshold (e.g., 49500 = 49.50 Hz)
        uint64 overFrequencyAlert;   // Over-frequency alert (e.g., 50100 = 50.10 Hz)
        uint64 overFrequencyCritical; // Over-frequency critical (e.g., 50500 = 50.50 Hz)
    }

    struct DemandThresholds {
        uint16 lowThreshold;      // Below this = LOW demand (6000 = 60%)
        uint16 highThreshold;     // Above this = HIGH demand (8000 = 80%)
        uint16 criticalThreshold; // Above this = CRITICAL (9500 = 95%)
    }

    struct HistoricalEntry {
        uint64 frequency;
        uint64 timestamp;
        DemandLevel demandLevel;
        uint16 renewableMix;
    }

    // ============ State Variables ============
    /// @notice Chainlink frequency feed (if available)
    AggregatorV3Interface public frequencyFeed;

    /// @notice Chainlink demand feed (if available)
    AggregatorV3Interface public demandFeed;

    /// @notice Current grid status
    GridStatus public currentStatus;

    /// @notice Frequency thresholds
    FrequencyThresholds public freqThresholds;

    /// @notice Demand thresholds
    DemandThresholds public demandThresholds;

    /// @notice Historical entries (circular buffer of last 60 entries = 1 hour at 1 min intervals)
    HistoricalEntry[60] public history;

    /// @notice Current history index
    uint256 public historyIndex;

    /// @notice Peak demand capacity (in MW, for reference)
    uint256 public peakCapacity;

    /// @notice Current demand (in MW)
    uint256 public currentDemand;

    /// @notice Grid stress events counter
    uint256 public stressEventCount;

    /// @notice Last V2G dispatch recommendation timestamp
    uint256 public lastV2GDispatch;

    // ============ Events ============
    event GridStatusUpdated(
        uint256 frequency,
        DemandLevel demandLevel,
        GridCondition condition,
        uint256 renewableMix,
        uint256 timestamp
    );
    event FrequencyAlert(
        uint256 frequency,
        bool isUnderFrequency,
        uint256 timestamp
    );
    event DemandLevelChanged(
        DemandLevel oldLevel,
        DemandLevel newLevel,
        uint256 timestamp
    );
    event GridStressDetected(
        uint256 frequency,
        DemandLevel demandLevel,
        uint256 timestamp
    );
    event V2GDispatchRecommended(
        bool recommended,
        uint256 frequency,
        DemandLevel demandLevel,
        uint256 timestamp
    );
    event ThresholdsUpdated(string thresholdType);
    event FeedUpdated(address indexed oldFeed, address indexed newFeed, string feedType);

    // ============ Constructor ============
    /**
     * @notice Initializes the GridStatusOracle
     * @param _frequencyFeed Chainlink frequency feed (can be zero for manual updates)
     * @param _admin Admin address
     * @param _peakCapacity Peak grid capacity in MW
     */
    constructor(
        address _frequencyFeed,
        address _admin,
        uint256 _peakCapacity
    ) {
        if (_admin == address(0)) revert ZeroAddress();

        if (_frequencyFeed != address(0)) {
            frequencyFeed = AggregatorV3Interface(_frequencyFeed);
        }

        peakCapacity = _peakCapacity;

        // Initialize default thresholds for Indian grid
        freqThresholds = FrequencyThresholds({
            underFrequencyAlert: 49900,    // 49.90 Hz
            underFrequencyCritical: 49500, // 49.50 Hz
            overFrequencyAlert: 50100,     // 50.10 Hz
            overFrequencyCritical: 50500   // 50.50 Hz
        });

        demandThresholds = DemandThresholds({
            lowThreshold: 6000,      // 60%
            highThreshold: 8000,     // 80%
            criticalThreshold: 9500  // 95%
        });

        // Initialize with normal status
        currentStatus = GridStatus({
            frequency: uint64(TARGET_FREQUENCY),
            timestamp: uint64(block.timestamp),
            demandLevel: DemandLevel.NORMAL,
            condition: GridCondition.STABLE,
            renewableMix: 2000, // 20% default
            loadFactor: 7000,   // 70% default
            v2gRecommended: false,
            chargingRecommended: true
        });

        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        _grantRole(OPERATOR_ROLE, _admin);
        _grantRole(GRID_UPDATER_ROLE, _admin);
    }

    // ============ View Functions ============

    /**
     * @notice Gets current grid frequency in mHz
     * @return frequency Current frequency (50000 = 50.000 Hz)
     */
    function getGridFrequency() external view returns (uint256 frequency) {
        // Try Chainlink feed first
        if (address(frequencyFeed) != address(0)) {
            try frequencyFeed.latestRoundData() returns (
                uint80,
                int256 answer,
                uint256,
                uint256 updatedAt,
                uint80
            ) {
                if (answer > 0 && block.timestamp - updatedAt <= MAX_STALENESS) {
                    return uint256(answer);
                }
            } catch {}
        }

        // Fall back to stored value
        return uint256(currentStatus.frequency);
    }

    /**
     * @notice Gets current demand level
     * @return level Current DemandLevel enum value
     */
    function getDemandLevel() external view returns (DemandLevel level) {
        return currentStatus.demandLevel;
    }

    /**
     * @notice Checks if grid is under stress
     * @return stressed True if grid is in stressed or emergency condition
     */
    function isGridStressed() external view returns (bool stressed) {
        return currentStatus.condition == GridCondition.STRESSED ||
               currentStatus.condition == GridCondition.EMERGENCY;
    }

    /**
     * @notice Gets current renewable energy mix percentage
     * @return mix Renewable percentage (0-10000 = 0-100%)
     */
    function getRenewableMix() external view returns (uint256 mix) {
        return uint256(currentStatus.renewableMix);
    }

    /**
     * @notice Gets full grid status
     * @return status Current GridStatus struct
     */
    function getFullStatus() external view returns (GridStatus memory status) {
        return currentStatus;
    }

    /**
     * @notice Checks if V2G discharge is currently recommended
     * @return recommended True if EVs should discharge to grid
     */
    function isV2GRecommended() external view returns (bool recommended) {
        return currentStatus.v2gRecommended;
    }

    /**
     * @notice Checks if EV charging is currently recommended
     * @return recommended True if EVs should charge
     */
    function isChargingRecommended() external view returns (bool recommended) {
        return currentStatus.chargingRecommended;
    }

    /**
     * @notice Gets grid condition
     * @return condition Current GridCondition enum value
     */
    function getGridCondition() external view returns (GridCondition condition) {
        return currentStatus.condition;
    }

    /**
     * @notice Gets frequency deviation from target
     * @return deviation Absolute deviation in mHz
     * @return isUnder True if under target frequency
     */
    function getFrequencyDeviation() external view returns (
        uint256 deviation,
        bool isUnder
    ) {
        uint256 freq = uint256(currentStatus.frequency);

        if (freq >= TARGET_FREQUENCY) {
            return (freq - TARGET_FREQUENCY, false);
        } else {
            return (TARGET_FREQUENCY - freq, true);
        }
    }

    /**
     * @notice Gets historical data for the last hour
     * @return frequencies Array of frequency values
     * @return timestamps Array of timestamps
     * @return demandLevels Array of demand levels
     */
    function getHourlyHistory() external view returns (
        uint256[] memory frequencies,
        uint256[] memory timestamps,
        DemandLevel[] memory demandLevels
    ) {
        frequencies = new uint256[](60);
        timestamps = new uint256[](60);
        demandLevels = new DemandLevel[](60);

        for (uint256 i = 0; i < 60; i++) {
            frequencies[i] = uint256(history[i].frequency);
            timestamps[i] = uint256(history[i].timestamp);
            demandLevels[i] = history[i].demandLevel;
        }
    }

    /**
     * @notice Calculates V2G incentive multiplier based on grid status
     * @return multiplier Incentive multiplier (10000 = 1.0x, 20000 = 2.0x)
     */
    function getV2GIncentiveMultiplier() external view returns (uint256 multiplier) {
        GridCondition condition = currentStatus.condition;
        DemandLevel demand = currentStatus.demandLevel;

        // Base multiplier
        multiplier = 10000; // 1.0x

        // Increase based on grid condition
        if (condition == GridCondition.UNDER_FREQUENCY) {
            multiplier = 15000; // 1.5x
        } else if (condition == GridCondition.STRESSED) {
            multiplier = 20000; // 2.0x
        } else if (condition == GridCondition.EMERGENCY) {
            multiplier = 30000; // 3.0x
        }

        // Additional increase based on demand
        if (demand == DemandLevel.HIGH) {
            multiplier = multiplier * 12 / 10; // +20%
        } else if (demand == DemandLevel.CRITICAL) {
            multiplier = multiplier * 15 / 10; // +50%
        }

        return multiplier;
    }

    // ============ Update Functions ============

    /**
     * @notice Updates grid status (called by Chainlink Automation or manually)
     * @param frequency Grid frequency in mHz
     * @param loadFactor Current load as percentage of capacity (0-10000)
     * @param renewableMix Renewable energy percentage (0-10000)
     */
    function updateGridStatus(
        uint256 frequency,
        uint256 loadFactor,
        uint256 renewableMix
    ) external onlyRole(GRID_UPDATER_ROLE) whenNotPaused {
        if (frequency < MIN_FREQUENCY || frequency > MAX_FREQUENCY) {
            revert InvalidFrequency(frequency);
        }
        if (renewableMix > PERCENTAGE_PRECISION) {
            revert InvalidRenewableMix(renewableMix);
        }

        DemandLevel oldDemand = currentStatus.demandLevel;

        // Determine demand level
        DemandLevel newDemand = _calculateDemandLevel(loadFactor);

        // Determine grid condition
        GridCondition condition = _calculateGridCondition(frequency, newDemand);

        // Determine V2G and charging recommendations
        (bool v2gRec, bool chargeRec) = _calculateRecommendations(frequency, newDemand, condition);

        // Update status
        currentStatus = GridStatus({
            frequency: uint64(frequency),
            timestamp: uint64(block.timestamp),
            demandLevel: newDemand,
            condition: condition,
            renewableMix: uint16(renewableMix),
            loadFactor: uint16(loadFactor),
            v2gRecommended: v2gRec,
            chargingRecommended: chargeRec
        });

        // Record to history
        _recordHistory(frequency, newDemand, renewableMix);

        // Emit events
        emit GridStatusUpdated(frequency, newDemand, condition, renewableMix, block.timestamp);

        if (newDemand != oldDemand) {
            emit DemandLevelChanged(oldDemand, newDemand, block.timestamp);
        }

        // Check for alerts
        _checkAlerts(frequency, newDemand, condition);
    }

    /**
     * @notice Quick frequency update (for high-frequency monitoring)
     * @param frequency Grid frequency in mHz
     */
    function updateFrequency(uint256 frequency) external onlyRole(GRID_UPDATER_ROLE) whenNotPaused {
        if (frequency < MIN_FREQUENCY || frequency > MAX_FREQUENCY) {
            revert InvalidFrequency(frequency);
        }

        currentStatus.frequency = uint64(frequency);
        currentStatus.timestamp = uint64(block.timestamp);

        // Recalculate condition based on new frequency
        GridCondition condition = _calculateGridCondition(
            frequency,
            currentStatus.demandLevel
        );
        currentStatus.condition = condition;

        // Update recommendations
        (bool v2gRec, bool chargeRec) = _calculateRecommendations(
            frequency,
            currentStatus.demandLevel,
            condition
        );
        currentStatus.v2gRecommended = v2gRec;
        currentStatus.chargingRecommended = chargeRec;

        // Check alerts
        _checkAlerts(frequency, currentStatus.demandLevel, condition);
    }

    /**
     * @notice Updates demand level directly
     * @param level New demand level
     */
    function updateDemandLevel(DemandLevel level) external onlyRole(GRID_UPDATER_ROLE) whenNotPaused {
        DemandLevel oldLevel = currentStatus.demandLevel;
        currentStatus.demandLevel = level;
        currentStatus.timestamp = uint64(block.timestamp);

        // Recalculate condition
        GridCondition condition = _calculateGridCondition(
            uint256(currentStatus.frequency),
            level
        );
        currentStatus.condition = condition;

        if (level != oldLevel) {
            emit DemandLevelChanged(oldLevel, level, block.timestamp);
        }
    }

    /**
     * @notice Updates renewable mix percentage
     * @param mix New renewable percentage (0-10000)
     */
    function updateRenewableMix(uint256 mix) external onlyRole(GRID_UPDATER_ROLE) whenNotPaused {
        if (mix > PERCENTAGE_PRECISION) revert InvalidRenewableMix(mix);

        currentStatus.renewableMix = uint16(mix);
        currentStatus.timestamp = uint64(block.timestamp);
    }

    // ============ Admin Functions ============

    /**
     * @notice Sets frequency thresholds
     * @param underAlert Under-frequency alert threshold
     * @param underCritical Under-frequency critical threshold
     * @param overAlert Over-frequency alert threshold
     * @param overCritical Over-frequency critical threshold
     */
    function setFrequencyThresholds(
        uint256 underAlert,
        uint256 underCritical,
        uint256 overAlert,
        uint256 overCritical
    ) external onlyRole(OPERATOR_ROLE) {
        if (underCritical >= underAlert ||
            overAlert >= overCritical ||
            underAlert >= TARGET_FREQUENCY ||
            overAlert <= TARGET_FREQUENCY) {
            revert InvalidThreshold(0);
        }

        freqThresholds = FrequencyThresholds({
            underFrequencyAlert: uint64(underAlert),
            underFrequencyCritical: uint64(underCritical),
            overFrequencyAlert: uint64(overAlert),
            overFrequencyCritical: uint64(overCritical)
        });

        emit ThresholdsUpdated("frequency");
    }

    /**
     * @notice Sets demand thresholds
     * @param low Low demand threshold
     * @param high High demand threshold
     * @param critical Critical demand threshold
     */
    function setDemandThresholds(
        uint256 low,
        uint256 high,
        uint256 critical
    ) external onlyRole(OPERATOR_ROLE) {
        if (low >= high || high >= critical || critical > PERCENTAGE_PRECISION) {
            revert InvalidThreshold(0);
        }

        demandThresholds = DemandThresholds({
            lowThreshold: uint16(low),
            highThreshold: uint16(high),
            criticalThreshold: uint16(critical)
        });

        emit ThresholdsUpdated("demand");
    }

    /**
     * @notice Sets peak capacity
     * @param capacity New peak capacity in MW
     */
    function setPeakCapacity(uint256 capacity) external onlyRole(OPERATOR_ROLE) {
        peakCapacity = capacity;
    }

    /**
     * @notice Sets frequency feed
     * @param feed New Chainlink feed address
     */
    function setFrequencyFeed(address feed) external onlyRole(DEFAULT_ADMIN_ROLE) {
        address oldFeed = address(frequencyFeed);
        frequencyFeed = AggregatorV3Interface(feed);
        emit FeedUpdated(oldFeed, feed, "frequency");
    }

    /**
     * @notice Sets demand feed
     * @param feed New Chainlink feed address
     */
    function setDemandFeed(address feed) external onlyRole(DEFAULT_ADMIN_ROLE) {
        address oldFeed = address(demandFeed);
        demandFeed = AggregatorV3Interface(feed);
        emit FeedUpdated(oldFeed, feed, "demand");
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
     * @dev Calculates demand level from load factor
     */
    function _calculateDemandLevel(uint256 loadFactor) internal view returns (DemandLevel) {
        if (loadFactor < demandThresholds.lowThreshold) {
            return DemandLevel.LOW;
        } else if (loadFactor < demandThresholds.highThreshold) {
            return DemandLevel.NORMAL;
        } else if (loadFactor < demandThresholds.criticalThreshold) {
            return DemandLevel.HIGH;
        } else {
            return DemandLevel.CRITICAL;
        }
    }

    /**
     * @dev Calculates grid condition from frequency and demand
     */
    function _calculateGridCondition(
        uint256 frequency,
        DemandLevel demand
    ) internal view returns (GridCondition) {
        // Check for emergency first
        if (frequency <= freqThresholds.underFrequencyCritical ||
            frequency >= freqThresholds.overFrequencyCritical) {
            return GridCondition.EMERGENCY;
        }

        // Check for stressed condition
        if (demand == DemandLevel.CRITICAL ||
            (demand == DemandLevel.HIGH &&
             (frequency <= freqThresholds.underFrequencyAlert ||
              frequency >= freqThresholds.overFrequencyAlert))) {
            return GridCondition.STRESSED;
        }

        // Check for under-frequency
        if (frequency <= freqThresholds.underFrequencyAlert) {
            return GridCondition.UNDER_FREQUENCY;
        }

        // Check for over-frequency
        if (frequency >= freqThresholds.overFrequencyAlert) {
            return GridCondition.OVER_FREQUENCY;
        }

        return GridCondition.STABLE;
    }

    /**
     * @dev Calculates V2G and charging recommendations
     */
    function _calculateRecommendations(
        uint256 frequency,
        DemandLevel demand,
        GridCondition condition
    ) internal view returns (bool v2gRecommended, bool chargingRecommended) {
        // V2G recommended when:
        // - Grid is under-frequency (needs power injection)
        // - Grid is stressed or emergency
        // - Demand is HIGH or CRITICAL
        v2gRecommended = condition == GridCondition.UNDER_FREQUENCY ||
                         condition == GridCondition.STRESSED ||
                         condition == GridCondition.EMERGENCY ||
                         demand == DemandLevel.CRITICAL;

        // Charging recommended when:
        // - Grid is over-frequency (excess generation)
        // - Demand is LOW
        // - Grid is stable and demand is NORMAL
        chargingRecommended = condition == GridCondition.OVER_FREQUENCY ||
                              demand == DemandLevel.LOW ||
                              (condition == GridCondition.STABLE && demand == DemandLevel.NORMAL);

        // Never recommend both
        if (v2gRecommended && chargingRecommended) {
            // Prioritize based on frequency
            if (frequency < TARGET_FREQUENCY) {
                chargingRecommended = false;
            } else {
                v2gRecommended = false;
            }
        }

        return (v2gRecommended, chargingRecommended);
    }

    /**
     * @dev Records entry to circular history buffer
     */
    function _recordHistory(
        uint256 frequency,
        DemandLevel demand,
        uint256 renewableMix
    ) internal {
        history[historyIndex] = HistoricalEntry({
            frequency: uint64(frequency),
            timestamp: uint64(block.timestamp),
            demandLevel: demand,
            renewableMix: uint16(renewableMix)
        });

        historyIndex = (historyIndex + 1) % 60;
    }

    /**
     * @dev Checks and emits alerts
     */
    function _checkAlerts(
        uint256 frequency,
        DemandLevel demand,
        GridCondition condition
    ) internal {
        // Frequency alerts
        if (frequency <= freqThresholds.underFrequencyAlert) {
            emit FrequencyAlert(frequency, true, block.timestamp);
        } else if (frequency >= freqThresholds.overFrequencyAlert) {
            emit FrequencyAlert(frequency, false, block.timestamp);
        }

        // Grid stress detection
        if (condition == GridCondition.STRESSED || condition == GridCondition.EMERGENCY) {
            stressEventCount++;
            emit GridStressDetected(frequency, demand, block.timestamp);
        }

        // V2G dispatch recommendation
        bool v2gRec = currentStatus.v2gRecommended;
        if (v2gRec && block.timestamp - lastV2GDispatch > 5 minutes) {
            lastV2GDispatch = block.timestamp;
            emit V2GDispatchRecommended(true, frequency, demand, block.timestamp);
        }
    }
}
