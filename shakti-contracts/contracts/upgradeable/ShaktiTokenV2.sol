// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ERC20Upgradeable} from "@openzeppelin/contracts-upgradeable/token/ERC20/ERC20Upgradeable.sol";
import {ERC20BurnableUpgradeable} from "@openzeppelin/contracts-upgradeable/token/ERC20/extensions/ERC20BurnableUpgradeable.sol";
import {ERC20PermitUpgradeable} from "@openzeppelin/contracts-upgradeable/token/ERC20/extensions/ERC20PermitUpgradeable.sol";
import {ERC20VotesUpgradeable} from "@openzeppelin/contracts-upgradeable/token/ERC20/extensions/ERC20VotesUpgradeable.sol";
import {AccessControlUpgradeable} from "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import {PausableUpgradeable} from "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";
import {Initializable} from "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import {UUPSUpgradeable} from "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";
import {NoncesUpgradeable} from "@openzeppelin/contracts-upgradeable/utils/NoncesUpgradeable.sol";

/**
 * @title ShaktiTokenV2
 * @author SHAKTI-CHAIN Team
 * @notice Upgradeable ERC20 token for SHAKTI-CHAIN V2G platform
 * @dev UUPS upgradeable pattern with governance-controlled upgrades
 *
 * V2 Features:
 * - All V1 functionality preserved
 * - Voting capabilities (ERC20Votes)
 * - Upgradeable via UUPS
 * - Storage gaps for future upgrades
 *
 * Upgrade Authorization:
 * - Only UPGRADER_ROLE can authorize upgrades
 * - Typically granted to Governor/Timelock
 */
contract ShaktiTokenV2 is
    Initializable,
    ERC20Upgradeable,
    ERC20BurnableUpgradeable,
    ERC20PermitUpgradeable,
    ERC20VotesUpgradeable,
    AccessControlUpgradeable,
    PausableUpgradeable,
    UUPSUpgradeable
{
    // ============ Custom Errors ============
    error ZeroAddress();
    error ZeroAmount();
    error ExceedsMaxSupply(uint256 newTotalSupply, uint256 maxSupply);
    error InsufficientBalance(uint256 requested, uint256 available);

    // ============ Constants ============
    bytes32 public constant MINTER_ROLE = keccak256("MINTER_ROLE");
    bytes32 public constant BURNER_ROLE = keccak256("BURNER_ROLE");
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");
    bytes32 public constant UPGRADER_ROLE = keccak256("UPGRADER_ROLE");

    uint256 public constant MAX_SUPPLY = 1_000_000_000 * 10**18;
    uint256 public constant INITIAL_SUPPLY = 1_000_000_000 * 10**18;
    uint256 public constant FEE_BURN_PERCENTAGE = 30;

    // ============ State Variables ============
    uint256 public totalFeesBurned;

    // ============ Storage Gap ============
    /// @dev Reserved storage space for future upgrades
    uint256[49] private __gap;

    // ============ Events ============
    event FeesBurned(address indexed from, uint256 feeAmount, uint256 burnedAmount);

    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }

    /**
     * @notice Initializes the token (replaces constructor)
     * @param initialHolder Address to receive initial supply
     * @param admin Address to receive admin roles
     */
    function initialize(
        address initialHolder,
        address admin
    ) public initializer {
        if (initialHolder == address(0)) revert ZeroAddress();
        if (admin == address(0)) revert ZeroAddress();

        __ERC20_init("SHAKTI Token", "SHAKTI");
        __ERC20Burnable_init();
        __ERC20Permit_init("SHAKTI Token");
        __ERC20Votes_init();
        __AccessControl_init();
        __Pausable_init();
        __UUPSUpgradeable_init();

        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(MINTER_ROLE, admin);
        _grantRole(BURNER_ROLE, admin);
        _grantRole(PAUSER_ROLE, admin);
        _grantRole(UPGRADER_ROLE, admin);

        _mint(initialHolder, INITIAL_SUPPLY);
    }

    /**
     * @notice Reinitializer for V2 upgrade (if upgrading from V1)
     * @param governanceTimelock Address of governance timelock for upgrade control
     */
    function initializeV2(address governanceTimelock) public reinitializer(2) {
        if (governanceTimelock == address(0)) revert ZeroAddress();

        // Grant UPGRADER_ROLE to governance
        _grantRole(UPGRADER_ROLE, governanceTimelock);
    }

    // ============ Token Functions ============

    /**
     * @notice Mints new tokens
     * @param to Recipient address
     * @param amount Amount to mint
     */
    function mint(address to, uint256 amount) external onlyRole(MINTER_ROLE) {
        if (to == address(0)) revert ZeroAddress();
        if (amount == 0) revert ZeroAmount();

        uint256 newTotalSupply = totalSupply() + amount;
        if (newTotalSupply > MAX_SUPPLY) {
            revert ExceedsMaxSupply(newTotalSupply, MAX_SUPPLY);
        }

        _mint(to, amount);
    }

    /**
     * @notice Burns fees and returns 30% as burn amount
     * @param from Address to burn from
     * @param feeAmount Total fee amount
     */
    function burnFees(
        address from,
        uint256 feeAmount
    ) external onlyRole(BURNER_ROLE) whenNotPaused {
        if (feeAmount == 0) revert ZeroAmount();

        uint256 burnAmount = (feeAmount * FEE_BURN_PERCENTAGE) / 100;
        if (balanceOf(from) < burnAmount) {
            revert InsufficientBalance(burnAmount, balanceOf(from));
        }

        _burn(from, burnAmount);
        totalFeesBurned += burnAmount;

        emit FeesBurned(from, feeAmount, burnAmount);
    }

    // ============ Pause Functions ============

    function pause() external onlyRole(PAUSER_ROLE) {
        _pause();
    }

    function unpause() external onlyRole(PAUSER_ROLE) {
        _unpause();
    }

    // ============ View Functions ============

    function remainingMintableSupply() external view returns (uint256) {
        uint256 currentSupply = totalSupply();
        if (currentSupply >= MAX_SUPPLY) return 0;
        return MAX_SUPPLY - currentSupply;
    }

    function circulatingSupply() external view returns (uint256) {
        return totalSupply();
    }

    /**
     * @notice Returns the current version
     */
    function version() external pure returns (string memory) {
        return "2.0.0";
    }

    // ============ Required Overrides ============

    function _update(
        address from,
        address to,
        uint256 value
    ) internal override(ERC20Upgradeable, ERC20VotesUpgradeable) whenNotPaused {
        super._update(from, to, value);
    }

    function nonces(
        address owner
    ) public view override(ERC20PermitUpgradeable, NoncesUpgradeable) returns (uint256) {
        return super.nonces(owner);
    }

    /**
     * @notice Authorizes contract upgrades
     * @dev Only accounts with UPGRADER_ROLE can upgrade
     */
    function _authorizeUpgrade(
        address newImplementation
    ) internal override onlyRole(UPGRADER_ROLE) {}
}
