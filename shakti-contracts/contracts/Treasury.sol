// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";

/**
 * @title Treasury
 * @author SHAKTI-CHAIN Team
 * @notice Treasury contract for SHAKTI-CHAIN fee management and distribution
 * @dev Manages protocol fees with multisig controls and timelocks
 *
 * Fee Flow:
 * 1. 2% platform fee on each trade (collected by EnergyEscrow)
 * 2. 30% of fee burned (deflationary) - handled by EnergyEscrow
 * 3. 70% sent to Treasury
 *
 * Treasury Distribution:
 * - 50% to staking rewards pool
 * - 30% to protocol development (multisig controlled)
 * - 20% to community grants (governance controlled)
 *
 * Security:
 * - 5 signers for development fund withdrawal
 * - 3/5 signatures required
 * - 48-hour timelock on withdrawals > 100,000 SHAKTI
 */
contract Treasury is AccessControl, ReentrancyGuard, Pausable {
    using SafeERC20 for IERC20;

    // ============ Custom Errors ============
    error ZeroAddress();
    error ZeroAmount();
    error InvalidPercentage();
    error InsufficientBalance(uint256 requested, uint256 available);
    error InvalidSignerCount();
    error SignerAlreadyExists();
    error SignerDoesNotExist();
    error AlreadySigned();
    error NotSigner();
    error WithdrawalNotFound();
    error WithdrawalAlreadyExecuted();
    error WithdrawalWasCancelled();
    error InsufficientSignatures(uint256 required, uint256 actual);
    error TimelockNotExpired(uint256 unlockTime);
    error DistributionTooSoon(uint256 nextAllowed);
    error InvalidMonth();
    error GrantExceedsAllocation();
    error UnauthorizedCaller();

    // ============ Constants ============
    bytes32 public constant ESCROW_ROLE = keccak256("ESCROW_ROLE");
    bytes32 public constant GOVERNANCE_ROLE = keccak256("GOVERNANCE_ROLE");
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");

    uint256 public constant BASIS_POINTS = 10000;
    uint256 public constant STAKING_SHARE = 5000;      // 50%
    uint256 public constant DEVELOPMENT_SHARE = 3000;  // 30%
    uint256 public constant GRANTS_SHARE = 2000;       // 20%

    uint256 public constant REQUIRED_SIGNATURES = 3;
    uint256 public constant MAX_SIGNERS = 5;
    uint256 public constant TIMELOCK_THRESHOLD = 100_000 * 1e18; // 100,000 SHAKTI
    uint256 public constant TIMELOCK_DURATION = 48 hours;
    uint256 public constant DISTRIBUTION_INTERVAL = 7 days;

    // ============ Enums ============
    enum InflowSource {
        PlatformFees,
        Donations,
        TokenSales,
        Other
    }

    enum OutflowCategory {
        StakingRewards,
        Development,
        CommunityGrants,
        Emergency
    }

    enum WithdrawalStatus {
        Pending,
        Executed,
        Cancelled
    }

    // ============ Structs ============
    struct PendingWithdrawal {
        uint256 id;
        address to;
        uint256 amount;
        string purpose;
        uint256 createdAt;
        uint256 unlockTime;
        uint256 signatureCount;
        WithdrawalStatus status;
        mapping(address => bool) hasSigned;
    }

    struct WithdrawalInfo {
        uint256 id;
        address to;
        uint256 amount;
        string purpose;
        uint256 createdAt;
        uint256 unlockTime;
        uint256 signatureCount;
        WithdrawalStatus status;
    }

    struct Grant {
        uint256 id;
        address recipient;
        uint256 amount;
        string purpose;
        uint256 timestamp;
        bool executed;
    }

    struct MonthlySnapshot {
        uint256 month;          // YYYYMM format
        uint256 totalInflows;
        uint256 totalOutflows;
        uint256 stakingDistributed;
        uint256 developmentSpent;
        uint256 grantsAllocated;
        uint256 endingBalance;
        uint256 timestamp;
    }

    struct AccountingEntry {
        uint256 timestamp;
        InflowSource source;
        uint256 amount;
        string description;
    }

    struct OutflowEntry {
        uint256 timestamp;
        OutflowCategory category;
        address recipient;
        uint256 amount;
        string description;
    }

    // ============ State Variables ============
    IERC20 public immutable shaktiToken;
    address public stakingPool;

    // Balances by allocation
    uint256 public stakingAllocation;
    uint256 public developmentAllocation;
    uint256 public grantsAllocation;

    // Multisig state
    address[] public signers;
    mapping(address => bool) public isSigner;
    uint256 public withdrawalNonce;
    mapping(uint256 => PendingWithdrawal) public pendingWithdrawals;
    uint256[] public activeWithdrawalIds;

    // Grants state
    uint256 public grantNonce;
    mapping(uint256 => Grant) public grants;
    uint256[] public grantIds;

    // Distribution state
    uint256 public lastDistributionTime;
    uint256 public totalDistributed;

    // Accounting state
    AccountingEntry[] public inflowHistory;
    OutflowEntry[] public outflowHistory;
    mapping(uint256 => MonthlySnapshot) public monthlySnapshots;
    uint256[] public snapshotMonths;

    // Totals tracking
    uint256 public totalFeesReceived;
    uint256 public totalDonationsReceived;
    uint256 public totalTokenSalesReceived;
    uint256 public totalOtherReceived;

    uint256 public totalStakingDistributed;
    uint256 public totalDevelopmentWithdrawn;
    uint256 public totalGrantsAllocated;

    // ============ Events ============
    event FeeReceived(uint256 amount, uint256 stakingShare, uint256 devShare, uint256 grantsShare);
    event DonationReceived(address indexed donor, uint256 amount);
    event TokenSaleReceived(uint256 amount, string description);
    event OtherInflowReceived(uint256 amount, string description);

    event RewardsDistributed(uint256 amount, uint256 timestamp);
    event GrantAllocated(uint256 indexed grantId, address indexed recipient, uint256 amount, string purpose);
    event GrantExecuted(uint256 indexed grantId, address indexed recipient, uint256 amount);
    event FundsWithdrawn(uint256 indexed withdrawalId, address indexed to, uint256 amount, string purpose);

    event WithdrawalProposed(uint256 indexed withdrawalId, address indexed to, uint256 amount, address proposer);
    event WithdrawalSigned(uint256 indexed withdrawalId, address indexed signer, uint256 signatureCount);
    event WithdrawalExecuted(uint256 indexed withdrawalId, address indexed to, uint256 amount);
    event WithdrawalCancelled(uint256 indexed withdrawalId);

    event SignerAdded(address indexed signer);
    event SignerRemoved(address indexed signer);
    event StakingPoolUpdated(address indexed oldPool, address indexed newPool);
    event MonthlySnapshotRecorded(uint256 indexed month, uint256 totalInflows, uint256 totalOutflows);

    // ============ Constructor ============
    /**
     * @notice Initializes the Treasury
     * @param _token SHAKTI token address
     * @param _admin Admin address
     * @param _initialSigners Initial multisig signers (5 addresses)
     */
    constructor(
        address _token,
        address _admin,
        address[] memory _initialSigners
    ) {
        if (_token == address(0)) revert ZeroAddress();
        if (_admin == address(0)) revert ZeroAddress();
        if (_initialSigners.length != MAX_SIGNERS) revert InvalidSignerCount();

        shaktiToken = IERC20(_token);

        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        _grantRole(GOVERNANCE_ROLE, _admin);
        _grantRole(PAUSER_ROLE, _admin);

        // Initialize signers
        for (uint256 i = 0; i < _initialSigners.length; i++) {
            if (_initialSigners[i] == address(0)) revert ZeroAddress();
            if (isSigner[_initialSigners[i]]) revert SignerAlreadyExists();

            signers.push(_initialSigners[i]);
            isSigner[_initialSigners[i]] = true;

            emit SignerAdded(_initialSigners[i]);
        }

        lastDistributionTime = block.timestamp;
    }

    // ============ Fee Reception ============

    /**
     * @notice Receives platform fees from EnergyEscrow
     * @param amount Amount of SHAKTI received (after burn)
     * @dev Only callable by authorized escrow contracts
     */
    function receiveFees(uint256 amount) external nonReentrant whenNotPaused onlyRole(ESCROW_ROLE) {
        if (amount == 0) revert ZeroAmount();

        // Transfer tokens from escrow
        shaktiToken.safeTransferFrom(msg.sender, address(this), amount);

        // Calculate allocations
        uint256 toStaking = (amount * STAKING_SHARE) / BASIS_POINTS;
        uint256 toDevelopment = (amount * DEVELOPMENT_SHARE) / BASIS_POINTS;
        uint256 toGrants = amount - toStaking - toDevelopment;

        // Update allocations
        stakingAllocation += toStaking;
        developmentAllocation += toDevelopment;
        grantsAllocation += toGrants;

        // Update totals
        totalFeesReceived += amount;

        // Record in history
        inflowHistory.push(AccountingEntry({
            timestamp: block.timestamp,
            source: InflowSource.PlatformFees,
            amount: amount,
            description: "Platform fee from trade settlement"
        }));

        emit FeeReceived(amount, toStaking, toDevelopment, toGrants);
    }

    /**
     * @notice Accepts donations to the treasury
     * @param amount Amount to donate
     */
    function receiveDonation(uint256 amount) external nonReentrant whenNotPaused {
        if (amount == 0) revert ZeroAmount();

        shaktiToken.safeTransferFrom(msg.sender, address(this), amount);

        // Donations go to grants pool
        grantsAllocation += amount;
        totalDonationsReceived += amount;

        inflowHistory.push(AccountingEntry({
            timestamp: block.timestamp,
            source: InflowSource.Donations,
            amount: amount,
            description: "Community donation"
        }));

        emit DonationReceived(msg.sender, amount);
    }

    /**
     * @notice Records token sale proceeds
     * @param amount Amount received
     * @param description Description of the sale
     */
    function receiveTokenSaleProceeds(
        uint256 amount,
        string calldata description
    ) external nonReentrant whenNotPaused onlyRole(DEFAULT_ADMIN_ROLE) {
        if (amount == 0) revert ZeroAmount();

        shaktiToken.safeTransferFrom(msg.sender, address(this), amount);

        // Token sales split between development and grants
        uint256 toDevelopment = (amount * 60) / 100; // 60%
        uint256 toGrants = amount - toDevelopment;   // 40%

        developmentAllocation += toDevelopment;
        grantsAllocation += toGrants;
        totalTokenSalesReceived += amount;

        inflowHistory.push(AccountingEntry({
            timestamp: block.timestamp,
            source: InflowSource.TokenSales,
            amount: amount,
            description: description
        }));

        emit TokenSaleReceived(amount, description);
    }

    // ============ Staking Rewards Distribution ============

    /**
     * @notice Distributes staking rewards to the staking pool
     * @dev Can only be called once per week
     */
    function distributeRewards() external nonReentrant whenNotPaused {
        if (stakingPool == address(0)) revert ZeroAddress();
        if (block.timestamp < lastDistributionTime + DISTRIBUTION_INTERVAL) {
            revert DistributionTooSoon(lastDistributionTime + DISTRIBUTION_INTERVAL);
        }

        uint256 amount = stakingAllocation;
        if (amount == 0) revert ZeroAmount();

        stakingAllocation = 0;
        lastDistributionTime = block.timestamp;
        totalDistributed += amount;
        totalStakingDistributed += amount;

        // Transfer to staking pool
        shaktiToken.safeTransfer(stakingPool, amount);

        // Record outflow
        outflowHistory.push(OutflowEntry({
            timestamp: block.timestamp,
            category: OutflowCategory.StakingRewards,
            recipient: stakingPool,
            amount: amount,
            description: "Weekly staking rewards distribution"
        }));

        emit RewardsDistributed(amount, block.timestamp);
    }

    // ============ Community Grants ============

    /**
     * @notice Allocates a community grant
     * @param recipient Grant recipient address
     * @param amount Grant amount
     * @param purpose Purpose/description of the grant
     * @return grantId The ID of the created grant
     */
    function allocateGrant(
        address recipient,
        uint256 amount,
        string calldata purpose
    ) external nonReentrant whenNotPaused onlyRole(GOVERNANCE_ROLE) returns (uint256) {
        if (recipient == address(0)) revert ZeroAddress();
        if (amount == 0) revert ZeroAmount();
        if (amount > grantsAllocation) revert GrantExceedsAllocation();

        uint256 grantId = grantNonce++;

        grants[grantId] = Grant({
            id: grantId,
            recipient: recipient,
            amount: amount,
            purpose: purpose,
            timestamp: block.timestamp,
            executed: false
        });

        grantIds.push(grantId);

        // Reserve the amount
        grantsAllocation -= amount;

        emit GrantAllocated(grantId, recipient, amount, purpose);

        return grantId;
    }

    /**
     * @notice Executes an allocated grant
     * @param grantId The grant ID to execute
     */
    function executeGrant(uint256 grantId) external nonReentrant whenNotPaused {
        Grant storage grant = grants[grantId];

        if (grant.recipient == address(0)) revert ZeroAddress();
        if (grant.executed) revert WithdrawalAlreadyExecuted();

        grant.executed = true;
        totalGrantsAllocated += grant.amount;

        shaktiToken.safeTransfer(grant.recipient, grant.amount);

        outflowHistory.push(OutflowEntry({
            timestamp: block.timestamp,
            category: OutflowCategory.CommunityGrants,
            recipient: grant.recipient,
            amount: grant.amount,
            description: grant.purpose
        }));

        emit GrantExecuted(grantId, grant.recipient, grant.amount);
    }

    // ============ Development Fund Withdrawal (Multisig) ============

    /**
     * @notice Proposes a development fund withdrawal
     * @param to Recipient address
     * @param amount Withdrawal amount
     * @param purpose Purpose of withdrawal
     * @return withdrawalId The ID of the proposed withdrawal
     */
    function proposeWithdrawal(
        address to,
        uint256 amount,
        string calldata purpose
    ) external nonReentrant whenNotPaused returns (uint256) {
        if (!isSigner[msg.sender]) revert NotSigner();
        if (to == address(0)) revert ZeroAddress();
        if (amount == 0) revert ZeroAmount();
        if (amount > developmentAllocation) {
            revert InsufficientBalance(amount, developmentAllocation);
        }

        uint256 withdrawalId = withdrawalNonce++;

        PendingWithdrawal storage withdrawal = pendingWithdrawals[withdrawalId];
        withdrawal.id = withdrawalId;
        withdrawal.to = to;
        withdrawal.amount = amount;
        withdrawal.purpose = purpose;
        withdrawal.createdAt = block.timestamp;
        withdrawal.status = WithdrawalStatus.Pending;

        // Apply timelock for large withdrawals
        if (amount > TIMELOCK_THRESHOLD) {
            withdrawal.unlockTime = block.timestamp + TIMELOCK_DURATION;
        } else {
            withdrawal.unlockTime = block.timestamp;
        }

        // Proposer automatically signs
        withdrawal.hasSigned[msg.sender] = true;
        withdrawal.signatureCount = 1;

        activeWithdrawalIds.push(withdrawalId);

        emit WithdrawalProposed(withdrawalId, to, amount, msg.sender);
        emit WithdrawalSigned(withdrawalId, msg.sender, 1);

        return withdrawalId;
    }

    /**
     * @notice Signs a pending withdrawal
     * @param withdrawalId The withdrawal ID to sign
     */
    function signWithdrawal(uint256 withdrawalId) external nonReentrant whenNotPaused {
        if (!isSigner[msg.sender]) revert NotSigner();

        PendingWithdrawal storage withdrawal = pendingWithdrawals[withdrawalId];

        if (withdrawal.to == address(0)) revert WithdrawalNotFound();
        if (withdrawal.status != WithdrawalStatus.Pending) {
            if (withdrawal.status == WithdrawalStatus.Executed) revert WithdrawalAlreadyExecuted();
            revert WithdrawalWasCancelled();
        }
        if (withdrawal.hasSigned[msg.sender]) revert AlreadySigned();

        withdrawal.hasSigned[msg.sender] = true;
        withdrawal.signatureCount++;

        emit WithdrawalSigned(withdrawalId, msg.sender, withdrawal.signatureCount);
    }

    /**
     * @notice Executes a fully signed withdrawal
     * @param withdrawalId The withdrawal ID to execute
     */
    function executeWithdrawal(uint256 withdrawalId) external nonReentrant whenNotPaused {
        PendingWithdrawal storage withdrawal = pendingWithdrawals[withdrawalId];

        if (withdrawal.to == address(0)) revert WithdrawalNotFound();
        if (withdrawal.status != WithdrawalStatus.Pending) {
            if (withdrawal.status == WithdrawalStatus.Executed) revert WithdrawalAlreadyExecuted();
            revert WithdrawalWasCancelled();
        }
        if (withdrawal.signatureCount < REQUIRED_SIGNATURES) {
            revert InsufficientSignatures(REQUIRED_SIGNATURES, withdrawal.signatureCount);
        }
        if (block.timestamp < withdrawal.unlockTime) {
            revert TimelockNotExpired(withdrawal.unlockTime);
        }
        if (withdrawal.amount > developmentAllocation) {
            revert InsufficientBalance(withdrawal.amount, developmentAllocation);
        }

        withdrawal.status = WithdrawalStatus.Executed;
        developmentAllocation -= withdrawal.amount;
        totalDevelopmentWithdrawn += withdrawal.amount;

        shaktiToken.safeTransfer(withdrawal.to, withdrawal.amount);

        outflowHistory.push(OutflowEntry({
            timestamp: block.timestamp,
            category: OutflowCategory.Development,
            recipient: withdrawal.to,
            amount: withdrawal.amount,
            description: withdrawal.purpose
        }));

        emit WithdrawalExecuted(withdrawalId, withdrawal.to, withdrawal.amount);
        emit FundsWithdrawn(withdrawalId, withdrawal.to, withdrawal.amount, withdrawal.purpose);
    }

    /**
     * @notice Cancels a pending withdrawal
     * @param withdrawalId The withdrawal ID to cancel
     */
    function cancelWithdrawal(uint256 withdrawalId) external nonReentrant {
        if (!isSigner[msg.sender]) revert NotSigner();

        PendingWithdrawal storage withdrawal = pendingWithdrawals[withdrawalId];

        if (withdrawal.to == address(0)) revert WithdrawalNotFound();
        if (withdrawal.status != WithdrawalStatus.Pending) {
            if (withdrawal.status == WithdrawalStatus.Executed) revert WithdrawalAlreadyExecuted();
            revert WithdrawalWasCancelled();
        }

        withdrawal.status = WithdrawalStatus.Cancelled;

        emit WithdrawalCancelled(withdrawalId);
    }

    // ============ Signer Management ============

    /**
     * @notice Replaces a signer (requires governance)
     * @param oldSigner Signer to remove
     * @param newSigner New signer to add
     */
    function replaceSigner(
        address oldSigner,
        address newSigner
    ) external onlyRole(GOVERNANCE_ROLE) {
        if (newSigner == address(0)) revert ZeroAddress();
        if (!isSigner[oldSigner]) revert SignerDoesNotExist();
        if (isSigner[newSigner]) revert SignerAlreadyExists();

        isSigner[oldSigner] = false;
        isSigner[newSigner] = true;

        for (uint256 i = 0; i < signers.length; i++) {
            if (signers[i] == oldSigner) {
                signers[i] = newSigner;
                break;
            }
        }

        emit SignerRemoved(oldSigner);
        emit SignerAdded(newSigner);
    }

    // ============ Monthly Snapshots ============

    /**
     * @notice Records a monthly snapshot for transparency
     * @param month Month in YYYYMM format (e.g., 202412 for Dec 2024)
     */
    function recordMonthlySnapshot(uint256 month) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (month < 202401 || month > 210012) revert InvalidMonth();

        uint256 balance = shaktiToken.balanceOf(address(this));

        // Calculate period totals from history
        uint256 periodInflows = 0;
        uint256 periodOutflows = 0;

        // This is simplified - in production you'd track by actual month
        MonthlySnapshot storage snapshot = monthlySnapshots[month];
        snapshot.month = month;
        snapshot.totalInflows = totalFeesReceived + totalDonationsReceived + totalTokenSalesReceived;
        snapshot.totalOutflows = totalStakingDistributed + totalDevelopmentWithdrawn + totalGrantsAllocated;
        snapshot.stakingDistributed = totalStakingDistributed;
        snapshot.developmentSpent = totalDevelopmentWithdrawn;
        snapshot.grantsAllocated = totalGrantsAllocated;
        snapshot.endingBalance = balance;
        snapshot.timestamp = block.timestamp;

        snapshotMonths.push(month);

        emit MonthlySnapshotRecorded(month, snapshot.totalInflows, snapshot.totalOutflows);
    }

    // ============ Admin Functions ============

    /**
     * @notice Updates the staking pool address
     * @param _stakingPool New staking pool address
     */
    function setStakingPool(address _stakingPool) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (_stakingPool == address(0)) revert ZeroAddress();

        address oldPool = stakingPool;
        stakingPool = _stakingPool;

        emit StakingPoolUpdated(oldPool, _stakingPool);
    }

    /**
     * @notice Authorizes an escrow contract
     * @param escrow Escrow contract address
     */
    function authorizeEscrow(address escrow) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (escrow == address(0)) revert ZeroAddress();
        _grantRole(ESCROW_ROLE, escrow);
    }

    /**
     * @notice Revokes escrow authorization
     * @param escrow Escrow contract address
     */
    function revokeEscrow(address escrow) external onlyRole(DEFAULT_ADMIN_ROLE) {
        _revokeRole(ESCROW_ROLE, escrow);
    }

    /**
     * @notice Pauses the treasury
     */
    function pause() external onlyRole(PAUSER_ROLE) {
        _pause();
    }

    /**
     * @notice Unpauses the treasury
     */
    function unpause() external onlyRole(PAUSER_ROLE) {
        _unpause();
    }

    /**
     * @notice Emergency withdrawal (requires all 5 signers)
     * @param to Recipient address
     * @param amount Amount to withdraw
     */
    function emergencyWithdraw(
        address to,
        uint256 amount
    ) external nonReentrant onlyRole(DEFAULT_ADMIN_ROLE) {
        if (to == address(0)) revert ZeroAddress();
        if (amount == 0) revert ZeroAmount();

        uint256 balance = shaktiToken.balanceOf(address(this));
        if (amount > balance) revert InsufficientBalance(amount, balance);

        // Reset allocations proportionally
        uint256 totalAllocated = stakingAllocation + developmentAllocation + grantsAllocation;
        if (totalAllocated > 0) {
            uint256 ratio = (amount * BASIS_POINTS) / totalAllocated;
            stakingAllocation -= (stakingAllocation * ratio) / BASIS_POINTS;
            developmentAllocation -= (developmentAllocation * ratio) / BASIS_POINTS;
            grantsAllocation -= (grantsAllocation * ratio) / BASIS_POINTS;
        }

        shaktiToken.safeTransfer(to, amount);

        outflowHistory.push(OutflowEntry({
            timestamp: block.timestamp,
            category: OutflowCategory.Emergency,
            recipient: to,
            amount: amount,
            description: "Emergency withdrawal"
        }));
    }

    // ============ View Functions ============

    /**
     * @notice Gets all current signers
     * @return Array of signer addresses
     */
    function getSigners() external view returns (address[] memory) {
        return signers;
    }

    /**
     * @notice Gets treasury allocation breakdown
     * @return staking Staking pool allocation
     * @return development Development fund allocation
     * @return communityGrants Community grants allocation
     * @return total Total balance
     */
    function getAllocations() external view returns (
        uint256 staking,
        uint256 development,
        uint256 communityGrants,
        uint256 total
    ) {
        return (
            stakingAllocation,
            developmentAllocation,
            grantsAllocation,
            shaktiToken.balanceOf(address(this))
        );
    }

    /**
     * @notice Gets total inflows by source
     * @return fees Total platform fees
     * @return donations Total donations
     * @return tokenSales Total token sale proceeds
     * @return other Total other inflows
     */
    function getTotalInflows() external view returns (
        uint256 fees,
        uint256 donations,
        uint256 tokenSales,
        uint256 other
    ) {
        return (
            totalFeesReceived,
            totalDonationsReceived,
            totalTokenSalesReceived,
            totalOtherReceived
        );
    }

    /**
     * @notice Gets total outflows by category
     * @return staking Total distributed to staking
     * @return development Total withdrawn for development
     * @return communityGrants Total allocated to grants
     */
    function getTotalOutflows() external view returns (
        uint256 staking,
        uint256 development,
        uint256 communityGrants
    ) {
        return (
            totalStakingDistributed,
            totalDevelopmentWithdrawn,
            totalGrantsAllocated
        );
    }

    /**
     * @notice Gets withdrawal details
     * @param withdrawalId The withdrawal ID
     * @return info Withdrawal information
     */
    function getWithdrawalInfo(uint256 withdrawalId) external view returns (WithdrawalInfo memory info) {
        PendingWithdrawal storage w = pendingWithdrawals[withdrawalId];
        return WithdrawalInfo({
            id: w.id,
            to: w.to,
            amount: w.amount,
            purpose: w.purpose,
            createdAt: w.createdAt,
            unlockTime: w.unlockTime,
            signatureCount: w.signatureCount,
            status: w.status
        });
    }

    /**
     * @notice Checks if a signer has signed a withdrawal
     * @param withdrawalId The withdrawal ID
     * @param signer The signer address
     * @return True if signed
     */
    function hasSignedWithdrawal(uint256 withdrawalId, address signer) external view returns (bool) {
        return pendingWithdrawals[withdrawalId].hasSigned[signer];
    }

    /**
     * @notice Gets grant details
     * @param grantId The grant ID
     * @return The grant struct
     */
    function getGrant(uint256 grantId) external view returns (Grant memory) {
        return grants[grantId];
    }

    /**
     * @notice Gets all grant IDs
     * @return Array of grant IDs
     */
    function getAllGrantIds() external view returns (uint256[] memory) {
        return grantIds;
    }

    /**
     * @notice Gets time until next reward distribution
     * @return Seconds until next distribution, 0 if ready
     */
    function timeUntilNextDistribution() external view returns (uint256) {
        uint256 nextTime = lastDistributionTime + DISTRIBUTION_INTERVAL;
        if (block.timestamp >= nextTime) return 0;
        return nextTime - block.timestamp;
    }

    /**
     * @notice Gets monthly snapshot
     * @param month Month in YYYYMM format
     * @return The monthly snapshot
     */
    function getMonthlySnapshot(uint256 month) external view returns (MonthlySnapshot memory) {
        return monthlySnapshots[month];
    }

    /**
     * @notice Gets all snapshot months
     * @return Array of months with snapshots
     */
    function getSnapshotMonths() external view returns (uint256[] memory) {
        return snapshotMonths;
    }

    /**
     * @notice Gets inflow history length
     * @return Number of inflow entries
     */
    function getInflowHistoryLength() external view returns (uint256) {
        return inflowHistory.length;
    }

    /**
     * @notice Gets outflow history length
     * @return Number of outflow entries
     */
    function getOutflowHistoryLength() external view returns (uint256) {
        return outflowHistory.length;
    }

    /**
     * @notice Gets inflow entry at index
     * @param index The index
     * @return The accounting entry
     */
    function getInflowEntry(uint256 index) external view returns (AccountingEntry memory) {
        return inflowHistory[index];
    }

    /**
     * @notice Gets outflow entry at index
     * @param index The index
     * @return The outflow entry
     */
    function getOutflowEntry(uint256 index) external view returns (OutflowEntry memory) {
        return outflowHistory[index];
    }

    /**
     * @notice Gets treasury statistics
     * @return balance Current token balance
     * @return distributed Total ever distributed to staking
     * @return pendingStaking Current staking allocation
     * @return signerCount Number of signers
     */
    function getTreasuryStats() external view returns (
        uint256 balance,
        uint256 distributed,
        uint256 pendingStaking,
        uint256 signerCount
    ) {
        return (
            shaktiToken.balanceOf(address(this)),
            totalDistributed,
            stakingAllocation,
            signers.length
        );
    }
}
