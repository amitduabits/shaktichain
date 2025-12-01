// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {TimelockController} from "@openzeppelin/contracts/governance/TimelockController.sol";

/**
 * @title ShaktiTimelock
 * @author SHAKTI-CHAIN Team
 * @notice Timelock controller for SHAKTI-CHAIN governance
 * @dev Extends OpenZeppelin TimelockController with additional features
 *
 * Timelock Parameters:
 * - Minimum delay: 2 days (172,800 seconds)
 * - Maximum delay: 30 days (2,592,000 seconds)
 * - Emergency delay: 6 hours (21,600 seconds)
 *
 * Features:
 * - Configurable execution delays
 * - Emergency fast-track for critical operations
 * - Role-based access control
 * - Operation scheduling and execution
 * - Batch operations support
 */
contract ShaktiTimelock is TimelockController {
    // ============ Custom Errors ============
    error DelayBelowMinimum(uint256 delay, uint256 minimum);
    error DelayAboveMaximum(uint256 delay, uint256 maximum);
    error EmergencyDelayTooLong(uint256 delay, uint256 maximum);
    error NotEmergencyOperation();
    error EmergencyAlreadyActive();
    error EmergencyNotActive();

    // ============ Constants ============
    /// @notice Minimum allowed delay (2 days)
    uint256 public constant MIN_DELAY = 2 days;

    /// @notice Maximum allowed delay (30 days)
    uint256 public constant MAX_DELAY = 30 days;

    /// @notice Emergency delay (6 hours)
    uint256 public constant EMERGENCY_DELAY = 6 hours;

    /// @notice Emergency executor role
    bytes32 public constant EMERGENCY_ROLE = keccak256("EMERGENCY_ROLE");

    // ============ State Variables ============
    /// @notice Current standard delay
    uint256 public standardDelay;

    /// @notice Whether emergency mode is active
    bool public emergencyModeActive;

    /// @notice Timestamp when emergency mode was activated
    uint256 public emergencyModeActivatedAt;

    /// @notice Duration of emergency mode (default 7 days)
    uint256 public emergencyModeDuration;

    /// @notice Mapping of operation ID to whether it's an emergency operation
    mapping(bytes32 => bool) public isEmergencyOperation;

    /// @notice Total operations executed
    uint256 public totalOperationsExecuted;

    /// @notice Emergency operations executed
    uint256 public emergencyOperationsExecuted;

    // ============ Events ============
    event StandardDelayUpdated(uint256 oldDelay, uint256 newDelay);
    event EmergencyModeActivated(address indexed activator, uint256 duration);
    event EmergencyModeDeactivated(address indexed deactivator);
    event EmergencyOperationScheduled(bytes32 indexed operationId, address indexed scheduler);
    event EmergencyModeDurationUpdated(uint256 oldDuration, uint256 newDuration);
    event OperationExecutedWithType(bytes32 indexed operationId, bool isEmergency);

    // ============ Constructor ============
    /**
     * @notice Initializes the ShaktiTimelock
     * @param minDelay Initial minimum delay (must be >= MIN_DELAY)
     * @param proposers Addresses that can schedule operations
     * @param executors Addresses that can execute operations
     * @param admin Admin address (can be zero for no admin)
     */
    constructor(
        uint256 minDelay,
        address[] memory proposers,
        address[] memory executors,
        address admin
    ) TimelockController(minDelay, proposers, executors, admin) {
        if (minDelay < MIN_DELAY) {
            revert DelayBelowMinimum(minDelay, MIN_DELAY);
        }
        if (minDelay > MAX_DELAY) {
            revert DelayAboveMaximum(minDelay, MAX_DELAY);
        }

        standardDelay = minDelay;
        emergencyModeDuration = 7 days;

        // Setup emergency role
        _setRoleAdmin(EMERGENCY_ROLE, DEFAULT_ADMIN_ROLE);
    }

    // ============ Delay Management ============

    /**
     * @notice Updates the standard delay
     * @param newDelay New delay value
     * @dev Can only be called through governance (self-call via timelock)
     */
    function updateStandardDelay(uint256 newDelay) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (newDelay < MIN_DELAY) {
            revert DelayBelowMinimum(newDelay, MIN_DELAY);
        }
        if (newDelay > MAX_DELAY) {
            revert DelayAboveMaximum(newDelay, MAX_DELAY);
        }

        uint256 oldDelay = standardDelay;
        standardDelay = newDelay;

        // Update the actual timelock delay
        // Note: This requires the timelock to call updateDelay on itself

        emit StandardDelayUpdated(oldDelay, newDelay);
    }

    /**
     * @notice Updates emergency mode duration
     * @param newDuration New duration in seconds
     */
    function updateEmergencyModeDuration(uint256 newDuration) external onlyRole(DEFAULT_ADMIN_ROLE) {
        uint256 oldDuration = emergencyModeDuration;
        emergencyModeDuration = newDuration;

        emit EmergencyModeDurationUpdated(oldDuration, newDuration);
    }

    // ============ Emergency Mode ============

    /**
     * @notice Activates emergency mode for faster execution
     * @dev Can only be called by addresses with EMERGENCY_ROLE
     */
    function activateEmergencyMode() external onlyRole(EMERGENCY_ROLE) {
        if (emergencyModeActive) {
            revert EmergencyAlreadyActive();
        }

        emergencyModeActive = true;
        emergencyModeActivatedAt = block.timestamp;

        emit EmergencyModeActivated(msg.sender, emergencyModeDuration);
    }

    /**
     * @notice Deactivates emergency mode
     * @dev Can be called by EMERGENCY_ROLE or automatically expires
     */
    function deactivateEmergencyMode() external onlyRole(EMERGENCY_ROLE) {
        if (!emergencyModeActive) {
            revert EmergencyNotActive();
        }

        emergencyModeActive = false;
        emergencyModeActivatedAt = 0;

        emit EmergencyModeDeactivated(msg.sender);
    }

    /**
     * @notice Checks if emergency mode has expired
     * @return True if emergency mode is active and not expired
     */
    function isEmergencyModeActive() public view returns (bool) {
        if (!emergencyModeActive) {
            return false;
        }
        return block.timestamp < emergencyModeActivatedAt + emergencyModeDuration;
    }

    // ============ Emergency Scheduling ============

    /**
     * @notice Schedules an emergency operation with reduced delay
     * @param target Target contract address
     * @param value ETH value
     * @param data Call data
     * @param predecessor Predecessor operation (0 for none)
     * @param salt Unique salt for operation ID
     * @return operationId The scheduled operation ID
     */
    function scheduleEmergency(
        address target,
        uint256 value,
        bytes calldata data,
        bytes32 predecessor,
        bytes32 salt
    ) external onlyRole(EMERGENCY_ROLE) returns (bytes32) {
        if (!isEmergencyModeActive()) {
            revert EmergencyNotActive();
        }

        bytes32 operationId = hashOperation(target, value, data, predecessor, salt);
        isEmergencyOperation[operationId] = true;

        // Schedule with emergency delay
        schedule(target, value, data, predecessor, salt, EMERGENCY_DELAY);

        emit EmergencyOperationScheduled(operationId, msg.sender);

        return operationId;
    }

    /**
     * @notice Schedules a batch emergency operation
     * @param targets Target contract addresses
     * @param values ETH values
     * @param payloads Call data array
     * @param predecessor Predecessor operation
     * @param salt Unique salt
     * @return operationId The scheduled operation ID
     */
    function scheduleBatchEmergency(
        address[] calldata targets,
        uint256[] calldata values,
        bytes[] calldata payloads,
        bytes32 predecessor,
        bytes32 salt
    ) external onlyRole(EMERGENCY_ROLE) returns (bytes32) {
        if (!isEmergencyModeActive()) {
            revert EmergencyNotActive();
        }

        bytes32 operationId = hashOperationBatch(targets, values, payloads, predecessor, salt);
        isEmergencyOperation[operationId] = true;

        // Schedule batch with emergency delay
        scheduleBatch(targets, values, payloads, predecessor, salt, EMERGENCY_DELAY);

        emit EmergencyOperationScheduled(operationId, msg.sender);

        return operationId;
    }

    // ============ Execution Tracking ============

    /**
     * @notice Tracks operation execution (call after execute)
     * @param operationId Operation ID to track
     * @dev Should be called after successful execution to update statistics
     */
    function trackExecution(bytes32 operationId) external {
        // Only track if operation was executed (status must be Done)
        require(isOperationDone(operationId), "Operation not done");

        totalOperationsExecuted++;

        if (isEmergencyOperation[operationId]) {
            emergencyOperationsExecuted++;
            emit OperationExecutedWithType(operationId, true);
        } else {
            emit OperationExecutedWithType(operationId, false);
        }
    }

    // ============ View Functions ============

    /**
     * @notice Gets the current effective delay
     * @return The current minimum delay
     */
    function getEffectiveDelay() external view returns (uint256) {
        if (isEmergencyModeActive()) {
            return EMERGENCY_DELAY;
        }
        return standardDelay;
    }

    /**
     * @notice Gets timelock statistics
     * @return total Total operations executed
     * @return emergency Emergency operations executed
     * @return currentDelay Current standard delay
     * @return emergencyActive Whether emergency mode is active
     */
    function getTimelockStats() external view returns (
        uint256 total,
        uint256 emergency,
        uint256 currentDelay,
        bool emergencyActive
    ) {
        return (
            totalOperationsExecuted,
            emergencyOperationsExecuted,
            standardDelay,
            isEmergencyModeActive()
        );
    }

    /**
     * @notice Gets time remaining in emergency mode
     * @return Seconds remaining, 0 if not active
     */
    function emergencyModeTimeRemaining() external view returns (uint256) {
        if (!isEmergencyModeActive()) {
            return 0;
        }
        uint256 endTime = emergencyModeActivatedAt + emergencyModeDuration;
        if (block.timestamp >= endTime) {
            return 0;
        }
        return endTime - block.timestamp;
    }

    /**
     * @notice Checks if an address has emergency role
     * @param account Address to check
     * @return True if has emergency role
     */
    function hasEmergencyRole(address account) external view returns (bool) {
        return hasRole(EMERGENCY_ROLE, account);
    }

    // ============ Role Management Helpers ============

    /**
     * @notice Grants emergency role to an address
     * @param account Address to grant role
     */
    function grantEmergencyRole(address account) external onlyRole(DEFAULT_ADMIN_ROLE) {
        grantRole(EMERGENCY_ROLE, account);
    }

    /**
     * @notice Revokes emergency role from an address
     * @param account Address to revoke role
     */
    function revokeEmergencyRole(address account) external onlyRole(DEFAULT_ADMIN_ROLE) {
        revokeRole(EMERGENCY_ROLE, account);
    }
}
