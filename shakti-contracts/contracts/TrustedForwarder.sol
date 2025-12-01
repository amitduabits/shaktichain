// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import {EIP712} from "@openzeppelin/contracts/utils/cryptography/EIP712.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";

/**
 * @title TrustedForwarder
 * @author SHAKTI-CHAIN Team
 * @notice ERC-2771 compliant trusted forwarder for meta-transactions
 * @dev Enables gasless transactions for SHAKTI-CHAIN users
 *
 * Features:
 * - EIP-712 typed structured data signing
 * - Nonce-based replay protection
 * - Deadline-based expiration
 * - Batch execution support
 * - Relayer fee support
 *
 * Gas Savings for Users:
 * - Users sign transactions off-chain
 * - Relayers pay gas and can be reimbursed
 * - Great UX for new users without ETH/MATIC
 */
contract TrustedForwarder is EIP712, ReentrancyGuard, AccessControl {
    using ECDSA for bytes32;

    // ============ Custom Errors ============
    error InvalidSigner(address expected, address actual);
    error InvalidNonce(uint256 expected, uint256 provided);
    error DeadlineExpired(uint256 deadline, uint256 currentTime);
    error ExecutionFailed(bytes returnData);
    error InsufficientValue(uint256 required, uint256 provided);
    error ZeroAddress();

    // ============ Constants ============
    bytes32 public constant RELAYER_ROLE = keccak256("RELAYER_ROLE");

    /// @notice EIP-712 typehash for ForwardRequest
    bytes32 public constant FORWARD_REQUEST_TYPEHASH = keccak256(
        "ForwardRequest(address from,address to,uint256 value,uint256 gas,uint256 nonce,uint256 deadline,bytes data)"
    );

    /// @notice EIP-712 typehash for BatchForwardRequest
    bytes32 public constant BATCH_FORWARD_REQUEST_TYPEHASH = keccak256(
        "BatchForwardRequest(address from,address[] targets,uint256[] values,uint256[] gases,uint256 nonce,uint256 deadline,bytes[] data)"
    );

    // ============ Structs ============
    /// @notice Forward request structure
    struct ForwardRequest {
        address from;       // Original sender
        address to;         // Target contract
        uint256 value;      // ETH value to send
        uint256 gas;        // Gas limit for the call
        uint256 nonce;      // Replay protection
        uint256 deadline;   // Expiration timestamp
        bytes data;         // Call data
    }

    /// @notice Batch forward request structure
    struct BatchForwardRequest {
        address from;           // Original sender
        address[] targets;      // Target contracts
        uint256[] values;       // ETH values
        uint256[] gases;        // Gas limits
        uint256 nonce;          // Replay protection
        uint256 deadline;       // Expiration timestamp
        bytes[] data;           // Call data array
    }

    // ============ State Variables ============
    /// @notice Mapping of address to current nonce
    mapping(address => uint256) public nonces;

    /// @notice Mapping of request hash to execution status
    mapping(bytes32 => bool) public executedRequests;

    /// @notice Total forwarded transactions
    uint256 public totalForwarded;

    /// @notice Total gas sponsored
    uint256 public totalGasSponsored;

    // ============ Events ============
    event ForwardExecuted(
        address indexed from,
        address indexed to,
        uint256 value,
        uint256 gasUsed,
        uint256 nonce,
        bool success
    );
    event BatchForwardExecuted(
        address indexed from,
        uint256 callCount,
        uint256 successCount,
        uint256 nonce
    );
    event NonceInvalidated(address indexed account, uint256 nonce);

    // ============ Constructor ============
    /**
     * @notice Initializes the TrustedForwarder
     * @param _admin Admin address
     */
    constructor(address _admin) EIP712("ShaktiForwarder", "1") {
        if (_admin == address(0)) revert ZeroAddress();

        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        _grantRole(RELAYER_ROLE, _admin);
    }

    // ============ External Functions ============

    /**
     * @notice Verifies a forward request signature
     * @param request The forward request
     * @param signature The EIP-712 signature
     * @return True if signature is valid
     */
    function verify(
        ForwardRequest calldata request,
        bytes calldata signature
    ) public view returns (bool) {
        bytes32 digest = _hashTypedDataV4(
            keccak256(
                abi.encode(
                    FORWARD_REQUEST_TYPEHASH,
                    request.from,
                    request.to,
                    request.value,
                    request.gas,
                    request.nonce,
                    request.deadline,
                    keccak256(request.data)
                )
            )
        );

        address signer = digest.recover(signature);
        return signer == request.from && request.nonce == nonces[request.from];
    }

    /**
     * @notice Executes a meta-transaction
     * @param request The forward request
     * @param signature The EIP-712 signature
     * @return success Whether the call succeeded
     * @return returnData The return data from the call
     */
    function execute(
        ForwardRequest calldata request,
        bytes calldata signature
    ) external payable nonReentrant onlyRole(RELAYER_ROLE) returns (bool success, bytes memory returnData) {
        // Verify deadline
        if (block.timestamp > request.deadline) {
            revert DeadlineExpired(request.deadline, block.timestamp);
        }

        // Verify nonce
        if (request.nonce != nonces[request.from]) {
            revert InvalidNonce(nonces[request.from], request.nonce);
        }

        // Verify signature
        bytes32 digest = _hashTypedDataV4(
            keccak256(
                abi.encode(
                    FORWARD_REQUEST_TYPEHASH,
                    request.from,
                    request.to,
                    request.value,
                    request.gas,
                    request.nonce,
                    request.deadline,
                    keccak256(request.data)
                )
            )
        );

        address signer = digest.recover(signature);
        if (signer != request.from) {
            revert InvalidSigner(request.from, signer);
        }

        // Verify value
        if (msg.value < request.value) {
            revert InsufficientValue(request.value, msg.value);
        }

        // Increment nonce before execution
        nonces[request.from]++;

        // Execute the call with ERC-2771 context (append sender address)
        uint256 gasStart = gasleft();
        (success, returnData) = request.to.call{gas: request.gas, value: request.value}(
            abi.encodePacked(request.data, request.from)
        );
        uint256 gasUsed = gasStart - gasleft();

        // Update stats
        totalForwarded++;
        totalGasSponsored += gasUsed;

        emit ForwardExecuted(request.from, request.to, request.value, gasUsed, request.nonce, success);

        // Refund excess ETH
        if (msg.value > request.value) {
            (bool refundSuccess, ) = msg.sender.call{value: msg.value - request.value}("");
            require(refundSuccess, "Refund failed");
        }
    }

    /**
     * @notice Executes a meta-transaction, reverting on failure
     * @param request The forward request
     * @param signature The EIP-712 signature
     * @return returnData The return data from the call
     */
    function executeStrict(
        ForwardRequest calldata request,
        bytes calldata signature
    ) external payable nonReentrant onlyRole(RELAYER_ROLE) returns (bytes memory returnData) {
        (bool success, bytes memory result) = this.execute{value: msg.value}(request, signature);
        if (!success) {
            revert ExecutionFailed(result);
        }
        return result;
    }

    /**
     * @notice Executes multiple meta-transactions in batch
     * @param request The batch forward request
     * @param signature The EIP-712 signature
     * @return results Array of success flags and return data
     */
    function executeBatch(
        BatchForwardRequest calldata request,
        bytes calldata signature
    ) external payable nonReentrant onlyRole(RELAYER_ROLE) returns (bool[] memory results) {
        // Verify deadline
        if (block.timestamp > request.deadline) {
            revert DeadlineExpired(request.deadline, block.timestamp);
        }

        // Verify nonce
        if (request.nonce != nonces[request.from]) {
            revert InvalidNonce(nonces[request.from], request.nonce);
        }

        // Verify arrays match
        uint256 callCount = request.targets.length;
        require(
            callCount == request.values.length &&
            callCount == request.gases.length &&
            callCount == request.data.length,
            "Array length mismatch"
        );

        // Calculate total value
        uint256 totalValue;
        for (uint256 i = 0; i < callCount;) {
            totalValue += request.values[i];
            unchecked { ++i; }
        }
        if (msg.value < totalValue) {
            revert InsufficientValue(totalValue, msg.value);
        }

        // Verify signature
        bytes32 digest = _hashTypedDataV4(
            keccak256(
                abi.encode(
                    BATCH_FORWARD_REQUEST_TYPEHASH,
                    request.from,
                    keccak256(abi.encodePacked(request.targets)),
                    keccak256(abi.encodePacked(request.values)),
                    keccak256(abi.encodePacked(request.gases)),
                    request.nonce,
                    request.deadline,
                    keccak256(_encodeDataArray(request.data))
                )
            )
        );

        address signer = digest.recover(signature);
        if (signer != request.from) {
            revert InvalidSigner(request.from, signer);
        }

        // Increment nonce
        nonces[request.from]++;

        // Execute calls
        results = new bool[](callCount);
        uint256 successCount;

        for (uint256 i = 0; i < callCount;) {
            (bool success, ) = request.targets[i].call{
                gas: request.gases[i],
                value: request.values[i]
            }(abi.encodePacked(request.data[i], request.from));

            results[i] = success;
            if (success) {
                unchecked { ++successCount; }
            }
            unchecked { ++i; }
        }

        totalForwarded += callCount;
        emit BatchForwardExecuted(request.from, callCount, successCount, request.nonce);

        // Refund excess ETH
        if (msg.value > totalValue) {
            (bool refundSuccess, ) = msg.sender.call{value: msg.value - totalValue}("");
            require(refundSuccess, "Refund failed");
        }
    }

    /**
     * @notice Invalidates the current nonce for the caller
     * @dev Can be used to cancel pending meta-transactions
     */
    function invalidateNonce() external {
        uint256 currentNonce = nonces[msg.sender];
        nonces[msg.sender]++;
        emit NonceInvalidated(msg.sender, currentNonce);
    }

    // ============ View Functions ============

    /**
     * @notice Gets the current nonce for an address
     * @param account The address to query
     * @return Current nonce
     */
    function getNonce(address account) external view returns (uint256) {
        return nonces[account];
    }

    /**
     * @notice Returns the domain separator
     * @return Domain separator hash
     */
    function domainSeparator() external view returns (bytes32) {
        return _domainSeparatorV4();
    }

    /**
     * @notice Gets forwarder statistics
     * @return total Total forwarded transactions
     * @return gasSponsored Total gas sponsored
     */
    function getStats() external view returns (uint256 total, uint256 gasSponsored) {
        return (totalForwarded, totalGasSponsored);
    }

    // ============ Internal Functions ============

    /**
     * @dev Encodes an array of bytes for hashing
     */
    function _encodeDataArray(bytes[] calldata dataArray) internal pure returns (bytes memory) {
        bytes memory encoded;
        for (uint256 i = 0; i < dataArray.length; i++) {
            encoded = abi.encodePacked(encoded, keccak256(dataArray[i]));
        }
        return encoded;
    }

    // ============ Admin Functions ============

    /**
     * @notice Grants relayer role to an address
     * @param relayer Address to grant role to
     */
    function addRelayer(address relayer) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (relayer == address(0)) revert ZeroAddress();
        _grantRole(RELAYER_ROLE, relayer);
    }

    /**
     * @notice Revokes relayer role from an address
     * @param relayer Address to revoke role from
     */
    function removeRelayer(address relayer) external onlyRole(DEFAULT_ADMIN_ROLE) {
        _revokeRole(RELAYER_ROLE, relayer);
    }

    /**
     * @notice Allows contract to receive ETH
     */
    receive() external payable {}
}
