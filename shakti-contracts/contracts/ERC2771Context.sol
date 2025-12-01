// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title ERC2771Context
 * @author SHAKTI-CHAIN Team
 * @notice Context contract for ERC-2771 meta-transaction support
 * @dev Provides _msgSender() and _msgData() that work with trusted forwarders
 *
 * Integration Guide:
 * 1. Inherit this contract
 * 2. Set trustedForwarder in constructor
 * 3. Use _msgSender() instead of msg.sender
 * 4. Use _msgData() instead of msg.data
 *
 * Example:
 * ```solidity
 * contract MyContract is ERC2771Context {
 *     constructor(address forwarder) ERC2771Context(forwarder) {}
 *
 *     function myFunction() external {
 *         address sender = _msgSender(); // Works with meta-txs
 *     }
 * }
 * ```
 */
abstract contract ERC2771Context {
    // ============ State Variables ============
    /// @notice The trusted forwarder address
    address public immutable trustedForwarder;

    // ============ Events ============
    event TrustedForwarderSet(address indexed forwarder);

    // ============ Constructor ============
    /**
     * @notice Initializes the ERC2771Context
     * @param _trustedForwarder Address of the trusted forwarder
     */
    constructor(address _trustedForwarder) {
        trustedForwarder = _trustedForwarder;
        emit TrustedForwarderSet(_trustedForwarder);
    }

    // ============ Public Functions ============

    /**
     * @notice Checks if an address is the trusted forwarder
     * @param forwarder Address to check
     * @return True if the address is the trusted forwarder
     */
    function isTrustedForwarder(address forwarder) public view virtual returns (bool) {
        return forwarder == trustedForwarder;
    }

    // ============ Internal Functions ============

    /**
     * @notice Returns the sender of the transaction
     * @dev If called via trusted forwarder, extracts original sender from calldata
     * @return sender The actual transaction sender
     */
    function _msgSender() internal view virtual returns (address sender) {
        if (isTrustedForwarder(msg.sender) && msg.data.length >= 20) {
            // The assembly code is more direct than the Solidity version using abi.decode.
            // Extract the last 20 bytes of msg.data which is the original sender
            assembly {
                sender := shr(96, calldataload(sub(calldatasize(), 20)))
            }
        } else {
            sender = msg.sender;
        }
    }

    /**
     * @notice Returns the calldata of the transaction
     * @dev If called via trusted forwarder, removes appended sender address
     * @return data The actual calldata
     */
    function _msgData() internal view virtual returns (bytes calldata data) {
        if (isTrustedForwarder(msg.sender) && msg.data.length >= 20) {
            return msg.data[:msg.data.length - 20];
        } else {
            return msg.data;
        }
    }

    /**
     * @notice Returns the context suffix length
     * @dev Used by OpenZeppelin's Context for compatibility
     * @return Length of the context suffix (20 bytes for address)
     */
    function _contextSuffixLength() internal view virtual returns (uint256) {
        return isTrustedForwarder(msg.sender) ? 20 : 0;
    }
}
