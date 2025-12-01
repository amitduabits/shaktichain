// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title Multicall
 * @author SHAKTI-CHAIN Team
 * @notice Enables calling multiple methods in a single call to the contract
 * @dev Aggregates results from multiple calls into a single transaction
 *
 * Gas Savings:
 * - Reduces multiple transactions to one
 * - Saves ~21000 base gas per aggregated call
 * - Efficient for batch operations across contracts
 *
 * Usage Examples:
 * - Query multiple user balances in one call
 * - Submit multiple orders and check status
 * - Claim rewards from multiple pools
 */
contract Multicall {
    // ============ Custom Errors ============
    error CallFailed(uint256 index, bytes data);
    error EmptyCallData();

    // ============ Structs ============
    /// @notice Call data structure
    struct Call {
        address target;
        bytes callData;
    }

    /// @notice Call result structure
    struct Result {
        bool success;
        bytes returnData;
    }

    // ============ Events ============
    event MulticallExecuted(address indexed caller, uint256 callCount, uint256 successCount);

    // ============ External Functions ============

    /**
     * @notice Executes multiple calls in a single transaction
     * @param calls Array of Call structs with target and callData
     * @return blockNumber Current block number
     * @return results Array of Result structs with success flag and return data
     * @dev Continues execution even if individual calls fail
     */
    function aggregate(
        Call[] calldata calls
    ) external returns (uint256 blockNumber, Result[] memory results) {
        uint256 callCount = calls.length;
        if (callCount == 0) revert EmptyCallData();

        blockNumber = block.number;
        results = new Result[](callCount);
        uint256 successCount;

        for (uint256 i = 0; i < callCount;) {
            (bool success, bytes memory returnData) = calls[i].target.call(calls[i].callData);
            results[i] = Result(success, returnData);
            if (success) {
                unchecked { ++successCount; }
            }
            unchecked { ++i; }
        }

        emit MulticallExecuted(msg.sender, callCount, successCount);
    }

    /**
     * @notice Executes multiple calls, requiring all to succeed
     * @param calls Array of Call structs with target and callData
     * @return blockNumber Current block number
     * @return results Array of bytes return data
     * @dev Reverts if any call fails
     */
    function aggregateStrict(
        Call[] calldata calls
    ) external returns (uint256 blockNumber, bytes[] memory results) {
        uint256 callCount = calls.length;
        if (callCount == 0) revert EmptyCallData();

        blockNumber = block.number;
        results = new bytes[](callCount);

        for (uint256 i = 0; i < callCount;) {
            (bool success, bytes memory returnData) = calls[i].target.call(calls[i].callData);
            if (!success) {
                revert CallFailed(i, returnData);
            }
            results[i] = returnData;
            unchecked { ++i; }
        }

        emit MulticallExecuted(msg.sender, callCount, callCount);
    }

    /**
     * @notice Executes multiple static calls (view/pure functions)
     * @param calls Array of Call structs with target and callData
     * @return blockNumber Current block number
     * @return results Array of Result structs with success flag and return data
     * @dev Does not modify state, suitable for batch queries
     */
    function aggregateStatic(
        Call[] calldata calls
    ) external view returns (uint256 blockNumber, Result[] memory results) {
        uint256 callCount = calls.length;
        if (callCount == 0) revert EmptyCallData();

        blockNumber = block.number;
        results = new Result[](callCount);

        for (uint256 i = 0; i < callCount;) {
            (bool success, bytes memory returnData) = calls[i].target.staticcall(calls[i].callData);
            results[i] = Result(success, returnData);
            unchecked { ++i; }
        }
    }

    /**
     * @notice Executes multiple calls with ETH value
     * @param calls Array of Call structs with target and callData
     * @param values Array of ETH values to send with each call
     * @return blockNumber Current block number
     * @return results Array of Result structs with success flag and return data
     * @dev Total msg.value must equal sum of values array
     */
    function aggregateWithValue(
        Call[] calldata calls,
        uint256[] calldata values
    ) external payable returns (uint256 blockNumber, Result[] memory results) {
        uint256 callCount = calls.length;
        if (callCount == 0) revert EmptyCallData();
        require(callCount == values.length, "Length mismatch");

        blockNumber = block.number;
        results = new Result[](callCount);
        uint256 successCount;

        for (uint256 i = 0; i < callCount;) {
            (bool success, bytes memory returnData) = calls[i].target.call{value: values[i]}(calls[i].callData);
            results[i] = Result(success, returnData);
            if (success) {
                unchecked { ++successCount; }
            }
            unchecked { ++i; }
        }

        emit MulticallExecuted(msg.sender, callCount, successCount);
    }

    // ============ Helper View Functions ============

    /**
     * @notice Returns current block information
     * @return blockNumber Current block number
     * @return blockTimestamp Current block timestamp
     * @return blockHash Hash of previous block
     */
    function getBlockInfo() external view returns (
        uint256 blockNumber,
        uint256 blockTimestamp,
        bytes32 blockHash
    ) {
        blockNumber = block.number;
        blockTimestamp = block.timestamp;
        blockHash = blockhash(block.number - 1);
    }

    /**
     * @notice Returns ETH balance of an address
     * @param addr Address to query
     * @return balance ETH balance in wei
     */
    function getEthBalance(address addr) external view returns (uint256 balance) {
        balance = addr.balance;
    }

    /**
     * @notice Returns current block timestamp
     * @return timestamp Block timestamp
     */
    function getCurrentBlockTimestamp() external view returns (uint256 timestamp) {
        timestamp = block.timestamp;
    }

    /**
     * @notice Returns current block gas limit
     * @return gasLimit Block gas limit
     */
    function getCurrentBlockGasLimit() external view returns (uint256 gasLimit) {
        gasLimit = block.gaslimit;
    }

    /**
     * @notice Returns last block hash
     * @return blockHash Hash of previous block
     */
    function getLastBlockHash() external view returns (bytes32 blockHash) {
        blockHash = blockhash(block.number - 1);
    }

    /**
     * @notice Try to aggregate calls, returning success status for each
     * @param requireSuccess If true, revert on any failure
     * @param calls Array of Call structs
     * @return results Array of Result structs
     */
    function tryAggregate(
        bool requireSuccess,
        Call[] calldata calls
    ) external returns (Result[] memory results) {
        uint256 callCount = calls.length;
        results = new Result[](callCount);

        for (uint256 i = 0; i < callCount;) {
            (bool success, bytes memory returnData) = calls[i].target.call(calls[i].callData);

            if (requireSuccess && !success) {
                revert CallFailed(i, returnData);
            }

            results[i] = Result(success, returnData);
            unchecked { ++i; }
        }
    }

    /**
     * @notice Aggregate calls with block context
     * @param calls Array of Call structs
     * @return blockNumber Current block number
     * @return blockHash Previous block hash
     * @return results Array of Result structs
     */
    function aggregateWithContext(
        Call[] calldata calls
    ) external returns (
        uint256 blockNumber,
        bytes32 blockHash,
        Result[] memory results
    ) {
        blockNumber = block.number;
        blockHash = blockhash(block.number - 1);

        uint256 callCount = calls.length;
        results = new Result[](callCount);

        for (uint256 i = 0; i < callCount;) {
            (bool success, bytes memory returnData) = calls[i].target.call(calls[i].callData);
            results[i] = Result(success, returnData);
            unchecked { ++i; }
        }
    }
}
