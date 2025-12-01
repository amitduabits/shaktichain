// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {ERC20Permit} from "@openzeppelin/contracts/token/ERC20/extensions/ERC20Permit.sol";
import {ERC20Votes} from "@openzeppelin/contracts/token/ERC20/extensions/ERC20Votes.sol";
import {Nonces} from "@openzeppelin/contracts/utils/Nonces.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/**
 * @title StakedShaktiVotes
 * @author SHAKTI-CHAIN Team
 * @notice Voting token wrapper for staked SHAKTI
 * @dev Wraps staked SHAKTI positions into an ERC20Votes compatible token
 *
 * Voting Power:
 * - 1 staked SHAKTI = 1 voting power
 * - Voting power can be delegated
 * - Historical checkpoints for governance
 *
 * Integration:
 * - Works with StakingPool to track staked amounts
 * - Mint/burn controlled by authorized staking contracts
 * - ERC20Votes for Governor compatibility
 *
 * Features:
 * - Automatic delegation to self on first mint
 * - Vote delegation to any address
 * - Historical voting power queries
 * - Integration with OpenZeppelin Governor
 */
contract StakedShaktiVotes is ERC20, ERC20Permit, ERC20Votes, Ownable, ReentrancyGuard {
    using SafeERC20 for IERC20;

    // ============ Custom Errors ============
    error UnauthorizedMinter();
    error UnauthorizedBurner();
    error InsufficientVotingPower(uint256 required, uint256 actual);
    error ZeroAddress();
    error ZeroAmount();
    error MinterAlreadyAuthorized();
    error MinterNotAuthorized();
    error SelfDelegationRequired();

    // ============ State Variables ============
    /// @notice Mapping of authorized minters (staking contracts)
    mapping(address => bool) public authorizedMinters;

    /// @notice Total minters count
    uint256 public minterCount;

    /// @notice Total votes ever minted
    uint256 public totalVotesMinted;

    /// @notice Total votes ever burned
    uint256 public totalVotesBurned;

    /// @notice Whether auto-delegation is enabled
    bool public autoDelegateEnabled;

    // ============ Events ============
    event MinterAuthorized(address indexed minter);
    event MinterRevoked(address indexed minter);
    event VotesMinted(address indexed to, uint256 amount, address indexed minter);
    event VotesBurned(address indexed from, uint256 amount, address indexed burner);
    event AutoDelegateToggled(bool enabled);

    // ============ Constructor ============
    /**
     * @notice Initializes the StakedShaktiVotes token
     * @param initialOwner Owner address
     */
    constructor(
        address initialOwner
    ) ERC20("Staked SHAKTI Votes", "stkSHAKTI") ERC20Permit("Staked SHAKTI Votes") Ownable(initialOwner) {
        autoDelegateEnabled = true;
    }

    // ============ Minter Management ============

    /**
     * @notice Authorizes a minter (staking contract)
     * @param minter Address to authorize
     */
    function authorizeMinter(address minter) external onlyOwner {
        if (minter == address(0)) {
            revert ZeroAddress();
        }
        if (authorizedMinters[minter]) {
            revert MinterAlreadyAuthorized();
        }

        authorizedMinters[minter] = true;
        minterCount++;

        emit MinterAuthorized(minter);
    }

    /**
     * @notice Revokes minter authorization
     * @param minter Address to revoke
     */
    function revokeMinter(address minter) external onlyOwner {
        if (!authorizedMinters[minter]) {
            revert MinterNotAuthorized();
        }

        authorizedMinters[minter] = false;
        minterCount--;

        emit MinterRevoked(minter);
    }

    /**
     * @notice Toggles auto-delegation on first mint
     * @param enabled Whether to enable auto-delegation
     */
    function setAutoDelegateEnabled(bool enabled) external onlyOwner {
        autoDelegateEnabled = enabled;
        emit AutoDelegateToggled(enabled);
    }

    // ============ Mint/Burn Functions ============

    /**
     * @notice Mints voting tokens when user stakes
     * @param to Recipient address
     * @param amount Amount to mint
     * @dev Only callable by authorized minters
     */
    function mint(address to, uint256 amount) external nonReentrant {
        if (!authorizedMinters[msg.sender]) {
            revert UnauthorizedMinter();
        }
        if (to == address(0)) {
            revert ZeroAddress();
        }
        if (amount == 0) {
            revert ZeroAmount();
        }

        // Auto-delegate to self on first mint
        bool isFirstMint = balanceOf(to) == 0;

        _mint(to, amount);
        totalVotesMinted += amount;

        // Auto-delegate to self if enabled and first mint
        if (autoDelegateEnabled && isFirstMint && delegates(to) == address(0)) {
            _delegate(to, to);
        }

        emit VotesMinted(to, amount, msg.sender);
    }

    /**
     * @notice Burns voting tokens when user unstakes
     * @param from Address to burn from
     * @param amount Amount to burn
     * @dev Only callable by authorized minters
     */
    function burn(address from, uint256 amount) external nonReentrant {
        if (!authorizedMinters[msg.sender]) {
            revert UnauthorizedBurner();
        }
        if (from == address(0)) {
            revert ZeroAddress();
        }
        if (amount == 0) {
            revert ZeroAmount();
        }

        _burn(from, amount);
        totalVotesBurned += amount;

        emit VotesBurned(from, amount, msg.sender);
    }

    // ============ Delegation Functions ============

    /**
     * @notice Delegates voting power to another address
     * @param delegatee Address to delegate to
     */
    function delegate(address delegatee) public override {
        if (delegatee == address(0)) {
            revert ZeroAddress();
        }
        super.delegate(delegatee);
    }

    /**
     * @notice Delegates voting power using signature
     * @param delegatee Address to delegate to
     * @param nonce Signer nonce
     * @param expiry Signature expiry
     * @param v Signature v
     * @param r Signature r
     * @param s Signature s
     */
    function delegateBySig(
        address delegatee,
        uint256 nonce,
        uint256 expiry,
        uint8 v,
        bytes32 r,
        bytes32 s
    ) public override {
        if (delegatee == address(0)) {
            revert ZeroAddress();
        }
        super.delegateBySig(delegatee, nonce, expiry, v, r, s);
    }

    // ============ View Functions ============

    /**
     * @notice Gets current voting power of an address
     * @param account Address to check
     * @return Current voting power
     */
    function getVotingPower(address account) external view returns (uint256) {
        return getVotes(account);
    }

    /**
     * @notice Gets historical voting power at a timepoint
     * @param account Address to check
     * @param timepoint Block number or timestamp
     * @return Voting power at timepoint
     */
    function getPastVotingPower(address account, uint256 timepoint) external view returns (uint256) {
        return getPastVotes(account, timepoint);
    }

    /**
     * @notice Gets total voting supply at a timepoint
     * @param timepoint Block number or timestamp
     * @return Total voting power at timepoint
     */
    function getPastTotalVotingPower(uint256 timepoint) external view returns (uint256) {
        return getPastTotalSupply(timepoint);
    }

    /**
     * @notice Gets voting token statistics
     * @return supply Total current supply
     * @return minted Total ever minted
     * @return burned Total ever burned
     * @return minters Number of authorized minters
     */
    function getVotingStats() external view returns (
        uint256 supply,
        uint256 minted,
        uint256 burned,
        uint256 minters
    ) {
        return (totalSupply(), totalVotesMinted, totalVotesBurned, minterCount);
    }

    /**
     * @notice Checks if address has sufficient voting power
     * @param account Address to check
     * @param amount Required amount
     * @return True if sufficient
     */
    function hasSufficientVotingPower(address account, uint256 amount) external view returns (bool) {
        return getVotes(account) >= amount;
    }

    // ============ Required Overrides ============

    function _update(
        address from,
        address to,
        uint256 value
    ) internal override(ERC20, ERC20Votes) {
        super._update(from, to, value);
    }

    function nonces(address owner) public view override(ERC20Permit, Nonces) returns (uint256) {
        return super.nonces(owner);
    }
}
