// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {ERC20Burnable} from "@openzeppelin/contracts/token/ERC20/extensions/ERC20Burnable.sol";
import {ERC20Pausable} from "@openzeppelin/contracts/token/ERC20/extensions/ERC20Pausable.sol";
import {ERC20Permit} from "@openzeppelin/contracts/token/ERC20/extensions/ERC20Permit.sol";
import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";

/**
 * @title ShaktiToken
 * @author SHAKTI-CHAIN Team
 * @notice ERC20 token for the SHAKTI-CHAIN V2G (Vehicle-to-Grid) platform
 * @dev Implements ERC20 with permit, burn, pause, and role-based access control
 *
 * Features:
 * - ERC20 with EIP-2612 permit for gasless approvals
 * - Burnable tokens for deflationary mechanics
 * - Pausable for emergency situations
 * - Role-based access control (MINTER, PAUSER, BURNER)
 * - Fee burning mechanism (30% of fees are burned)
 *
 * Gas Optimizations:
 * - Custom errors instead of require strings
 * - Packed storage where possible
 * - Immutable variables for constants
 */
contract ShaktiToken is ERC20, ERC20Burnable, ERC20Pausable, ERC20Permit, AccessControl {
    // ============ Custom Errors ============
    error ZeroAddress();
    error ZeroAmount();
    error InsufficientBalance(uint256 requested, uint256 available);
    error ExceedsMaxSupply(uint256 requested, uint256 maxAllowed);

    // ============ Constants ============
    bytes32 public constant MINTER_ROLE = keccak256("MINTER_ROLE");
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");
    bytes32 public constant BURNER_ROLE = keccak256("BURNER_ROLE");

    /// @notice Initial supply of 1 billion tokens (with 18 decimals)
    uint256 public constant INITIAL_SUPPLY = 1_000_000_000 * 10**18;

    /// @notice Maximum supply cap (can be set equal to initial or higher for minting)
    uint256 public constant MAX_SUPPLY = 1_000_000_000 * 10**18;

    /// @notice Fee burn percentage (30% = 3000 basis points)
    uint256 public constant FEE_BURN_PERCENTAGE = 30;
    uint256 private constant PERCENTAGE_BASE = 100;

    // ============ State Variables ============
    /// @notice Total amount of tokens burned through fee mechanism
    uint256 public totalFeesBurned;

    // ============ Events ============
    event FeesBurned(address indexed burner, uint256 totalAmount, uint256 burnedAmount);
    event TokensMinted(address indexed to, uint256 amount);
    event EmergencyPaused(address indexed pauser);
    event EmergencyUnpaused(address indexed pauser);

    // ============ Constructor ============
    /**
     * @notice Initializes the ShaktiToken contract
     * @param defaultAdmin Address that will receive the DEFAULT_ADMIN_ROLE
     * @param initialHolder Address that will receive the initial token supply
     * @dev Sets up all roles and mints the initial supply
     */
    constructor(
        address defaultAdmin,
        address initialHolder
    ) ERC20("ShaktiToken", "SHAKTI") ERC20Permit("ShaktiToken") {
        if (defaultAdmin == address(0)) revert ZeroAddress();
        if (initialHolder == address(0)) revert ZeroAddress();

        // Setup roles
        _grantRole(DEFAULT_ADMIN_ROLE, defaultAdmin);
        _grantRole(MINTER_ROLE, defaultAdmin);
        _grantRole(PAUSER_ROLE, defaultAdmin);
        _grantRole(BURNER_ROLE, defaultAdmin);

        // Mint initial supply to the initial holder
        _mint(initialHolder, INITIAL_SUPPLY);
    }

    // ============ External Functions ============

    /**
     * @notice Burns a percentage (30%) of the specified fee amount
     * @dev Only callable by accounts with BURNER_ROLE
     * @param amount The total fee amount, of which 30% will be burned
     *
     * Gas Optimization: Uses unchecked math where overflow is impossible
     */
    function burnFees(uint256 amount) external onlyRole(BURNER_ROLE) {
        if (amount == 0) revert ZeroAmount();

        address sender = _msgSender();
        uint256 senderBalance = balanceOf(sender);

        if (senderBalance < amount) {
            revert InsufficientBalance(amount, senderBalance);
        }

        // Calculate 30% to burn
        // Gas optimization: unchecked division (no overflow possible)
        uint256 burnAmount;
        unchecked {
            burnAmount = (amount * FEE_BURN_PERCENTAGE) / PERCENTAGE_BASE;
        }

        // Update tracking
        unchecked {
            totalFeesBurned += burnAmount;
        }

        // Burn the calculated amount
        _burn(sender, burnAmount);

        emit FeesBurned(sender, amount, burnAmount);
    }

    /**
     * @notice Mints new tokens to the specified address
     * @dev Only callable by accounts with MINTER_ROLE
     * @param to The address to mint tokens to
     * @param amount The amount of tokens to mint
     */
    function mint(address to, uint256 amount) external onlyRole(MINTER_ROLE) {
        if (to == address(0)) revert ZeroAddress();
        if (amount == 0) revert ZeroAmount();

        uint256 newTotalSupply = totalSupply() + amount;
        if (newTotalSupply > MAX_SUPPLY) {
            revert ExceedsMaxSupply(newTotalSupply, MAX_SUPPLY);
        }

        _mint(to, amount);
        emit TokensMinted(to, amount);
    }

    /**
     * @notice Pauses all token transfers
     * @dev Only callable by accounts with PAUSER_ROLE
     */
    function pause() external onlyRole(PAUSER_ROLE) {
        _pause();
        emit EmergencyPaused(_msgSender());
    }

    /**
     * @notice Unpauses all token transfers
     * @dev Only callable by accounts with PAUSER_ROLE
     */
    function unpause() external onlyRole(PAUSER_ROLE) {
        _unpause();
        emit EmergencyUnpaused(_msgSender());
    }

    // ============ View Functions ============

    /**
     * @notice Returns the remaining mintable supply
     * @return The amount of tokens that can still be minted
     */
    function remainingMintableSupply() external view returns (uint256) {
        uint256 currentSupply = totalSupply();
        if (currentSupply >= MAX_SUPPLY) return 0;
        unchecked {
            return MAX_SUPPLY - currentSupply;
        }
    }

    /**
     * @notice Returns the circulating supply (total supply minus burned)
     * @return The circulating supply
     */
    function circulatingSupply() external view returns (uint256) {
        return totalSupply();
    }

    // ============ Internal Functions ============

    /**
     * @dev Override required by Solidity for multiple inheritance
     * @param from Address tokens are transferred from
     * @param to Address tokens are transferred to
     * @param value Amount of tokens transferred
     */
    function _update(
        address from,
        address to,
        uint256 value
    ) internal override(ERC20, ERC20Pausable) {
        super._update(from, to, value);
    }
}
