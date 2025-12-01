// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title MockAggregatorV3
 * @author SHAKTI-CHAIN Team
 * @notice Mock Chainlink AggregatorV3Interface for testing
 * @dev Simulates Chainlink price feeds for local testing
 */
contract MockAggregatorV3 {
    uint8 private _decimals;
    string private _description;
    uint256 private _version;

    int256 private _answer;
    uint256 private _updatedAt;
    uint80 private _roundId;

    bool private _shouldRevert;
    bool private _stalePrice;
    uint256 private _stalenessDelay;

    address public owner;

    event AnswerUpdated(int256 indexed answer, uint256 indexed roundId, uint256 timestamp);

    modifier onlyOwner() {
        require(msg.sender == owner, "Not owner");
        _;
    }

    /**
     * @notice Creates a new mock aggregator
     * @param decimals_ Number of decimals
     * @param description_ Description of the feed
     * @param initialAnswer Initial price value
     */
    constructor(
        uint8 decimals_,
        string memory description_,
        int256 initialAnswer
    ) {
        _decimals = decimals_;
        _description = description_;
        _version = 1;
        _answer = initialAnswer;
        _updatedAt = block.timestamp;
        _roundId = 1;
        owner = msg.sender;
    }

    /**
     * @notice Returns the number of decimals
     */
    function decimals() external view returns (uint8) {
        return _decimals;
    }

    /**
     * @notice Returns the description
     */
    function description() external view returns (string memory) {
        return _description;
    }

    /**
     * @notice Returns the version
     */
    function version() external view returns (uint256) {
        return _version;
    }

    /**
     * @notice Gets data from a specific round
     * @param roundId_ The round ID to query
     */
    function getRoundData(uint80 roundId_) external view returns (
        uint80 roundId,
        int256 answer,
        uint256 startedAt,
        uint256 updatedAt,
        uint80 answeredInRound
    ) {
        require(!_shouldRevert, "Feed reverted");
        require(roundId_ <= _roundId, "No data for round");

        uint256 timestamp = _stalePrice ? block.timestamp - _stalenessDelay : _updatedAt;

        return (
            roundId_,
            _answer,
            timestamp,
            timestamp,
            roundId_
        );
    }

    /**
     * @notice Gets the latest round data
     */
    function latestRoundData() external view returns (
        uint80 roundId,
        int256 answer,
        uint256 startedAt,
        uint256 updatedAt,
        uint80 answeredInRound
    ) {
        require(!_shouldRevert, "Feed reverted");

        uint256 timestamp = _stalePrice ? block.timestamp - _stalenessDelay : _updatedAt;

        return (
            _roundId,
            _answer,
            timestamp,
            timestamp,
            _roundId
        );
    }

    // ============ Mock Control Functions ============

    /**
     * @notice Updates the answer value
     * @param answer New price value
     */
    function updateAnswer(int256 answer) external onlyOwner {
        _answer = answer;
        _updatedAt = block.timestamp;
        _roundId++;

        emit AnswerUpdated(answer, _roundId, block.timestamp);
    }

    /**
     * @notice Updates answer and timestamp manually
     * @param answer New price value
     * @param timestamp Custom timestamp
     */
    function updateAnswerWithTimestamp(int256 answer, uint256 timestamp) external onlyOwner {
        _answer = answer;
        _updatedAt = timestamp;
        _roundId++;

        emit AnswerUpdated(answer, _roundId, timestamp);
    }

    /**
     * @notice Sets multiple values at once
     * @param answer New price value
     * @param roundId New round ID
     * @param timestamp New timestamp
     */
    function setRoundData(
        int256 answer,
        uint80 roundId,
        uint256 timestamp
    ) external onlyOwner {
        _answer = answer;
        _roundId = roundId;
        _updatedAt = timestamp;
    }

    /**
     * @notice Makes the feed revert on calls
     * @param shouldRevert Whether calls should revert
     */
    function setShouldRevert(bool shouldRevert) external onlyOwner {
        _shouldRevert = shouldRevert;
    }

    /**
     * @notice Simulates stale price
     * @param stale Whether price should be stale
     * @param delay How old the price should appear (in seconds)
     */
    function setStalePrice(bool stale, uint256 delay) external onlyOwner {
        _stalePrice = stale;
        _stalenessDelay = delay;
    }

    /**
     * @notice Gets current answer
     */
    function getAnswer() external view returns (int256) {
        return _answer;
    }

    /**
     * @notice Gets current round ID
     */
    function getRoundId() external view returns (uint80) {
        return _roundId;
    }

    /**
     * @notice Gets updated at timestamp
     */
    function getUpdatedAt() external view returns (uint256) {
        return _updatedAt;
    }

    /**
     * @notice Transfers ownership
     * @param newOwner New owner address
     */
    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "Zero address");
        owner = newOwner;
    }
}

/**
 * @title MockPriceFeed
 * @notice Convenience wrapper for electricity price simulation
 */
contract MockPriceFeed is MockAggregatorV3 {
    // Price in paise with 8 decimals
    // Example: 500_00000000 = 500 paise = 5 INR/kWh

    constructor(int256 initialPriceInPaise)
        MockAggregatorV3(8, "IEX/INR Electricity Price", initialPriceInPaise)
    {}

    /**
     * @notice Sets price in INR/kWh for convenience
     * @param priceInINR Price in INR (e.g., 5 for 5 INR/kWh)
     */
    function setPriceINR(uint256 priceInINR) external {
        // Convert INR to paise with 8 decimals
        // 1 INR = 100 paise, so multiply by 100 * 10^8 = 10^10? No...
        // Actually: store as paise with 8 decimals
        // 5 INR = 500 paise = 500_00000000 in 8 decimal format
        int256 priceInPaise = int256(priceInINR * 100 * 1e8);
        MockAggregatorV3(this).updateAnswer(priceInPaise);
    }

    /**
     * @notice Sets price in paise/kWh
     * @param priceInPaise Price in paise (e.g., 500 for 5 INR/kWh)
     */
    function setPricePaise(uint256 priceInPaise) external {
        int256 price = int256(priceInPaise * 1e8);
        MockAggregatorV3(this).updateAnswer(price);
    }
}

/**
 * @title MockFrequencyFeed
 * @notice Convenience wrapper for grid frequency simulation
 */
contract MockFrequencyFeed is MockAggregatorV3 {
    // Frequency in mHz (50000 = 50.000 Hz)

    constructor()
        MockAggregatorV3(3, "Grid Frequency mHz", 50000)
    {}

    /**
     * @notice Sets frequency in Hz for convenience
     * @param frequencyHz Frequency in Hz with 3 decimals (e.g., 50000 for 50.000 Hz)
     */
    function setFrequency(uint256 frequencyHz) external {
        MockAggregatorV3(this).updateAnswer(int256(frequencyHz));
    }

    /**
     * @notice Simulates under-frequency event
     * @param deviation Deviation below 50 Hz in mHz
     */
    function simulateUnderFrequency(uint256 deviation) external {
        uint256 freq = 50000 - deviation;
        MockAggregatorV3(this).updateAnswer(int256(freq));
    }

    /**
     * @notice Simulates over-frequency event
     * @param deviation Deviation above 50 Hz in mHz
     */
    function simulateOverFrequency(uint256 deviation) external {
        uint256 freq = 50000 + deviation;
        MockAggregatorV3(this).updateAnswer(int256(freq));
    }

    /**
     * @notice Simulates normal frequency
     */
    function simulateNormal() external {
        MockAggregatorV3(this).updateAnswer(50000);
    }
}
