// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Governor} from "@openzeppelin/contracts/governance/Governor.sol";
import {GovernorSettings} from "@openzeppelin/contracts/governance/extensions/GovernorSettings.sol";
import {GovernorCountingSimple} from "@openzeppelin/contracts/governance/extensions/GovernorCountingSimple.sol";
import {GovernorVotes} from "@openzeppelin/contracts/governance/extensions/GovernorVotes.sol";
import {GovernorVotesQuorumFraction} from "@openzeppelin/contracts/governance/extensions/GovernorVotesQuorumFraction.sol";
import {GovernorTimelockControl} from "@openzeppelin/contracts/governance/extensions/GovernorTimelockControl.sol";
import {TimelockController} from "@openzeppelin/contracts/governance/TimelockController.sol";
import {IVotes} from "@openzeppelin/contracts/governance/utils/IVotes.sol";
import {IERC165} from "@openzeppelin/contracts/utils/introspection/IERC165.sol";

/**
 * @title ShaktiGovernor
 * @author SHAKTI-CHAIN Team
 * @notice Governance contract for SHAKTI-CHAIN protocol
 * @dev Implements OpenZeppelin Governor with all extensions
 *
 * Governance Parameters:
 * - Proposal Threshold: 100,000 SHAKTI (staked)
 * - Voting Delay: 1 day (7,200 blocks at 12s/block)
 * - Voting Period: 5 days (36,000 blocks)
 * - Quorum: 4% of total staked tokens
 * - Execution: Via Timelock (2 day delay)
 *
 * Proposal Types:
 * - Standard: Normal governance proposals
 * - Emergency: Fast-track for critical fixes (requires higher threshold)
 *
 * Features:
 * - Token-weighted voting (staked SHAKTI)
 * - Timelock-controlled execution
 * - Configurable parameters
 * - Proposal cancellation
 * - Vote delegation
 */
contract ShaktiGovernor is
    Governor,
    GovernorSettings,
    GovernorCountingSimple,
    GovernorVotes,
    GovernorVotesQuorumFraction,
    GovernorTimelockControl
{
    // ============ Custom Errors ============
    error ProposalThresholdNotMet(uint256 required, uint256 actual);
    error EmergencyThresholdNotMet(uint256 required, uint256 actual);
    error InvalidProposalType();
    error NotEmergencyProposal();

    // ============ Enums ============
    enum ProposalType {
        Standard,
        ParameterChange,
        ContractUpgrade,
        TreasurySpend,
        Emergency
    }

    // ============ State Variables ============
    /// @notice Emergency proposal threshold (500,000 SHAKTI)
    uint256 public emergencyThreshold;

    /// @notice Mapping of proposal ID to proposal type
    mapping(uint256 => ProposalType) public proposalTypes;

    /// @notice Mapping of proposal ID to description hash
    mapping(uint256 => bytes32) public proposalDescriptions;

    /// @notice Total proposals created
    uint256 public totalProposals;

    /// @notice Emergency proposals count
    uint256 public emergencyProposalsCount;

    // ============ Events ============
    event ProposalCreatedWithType(
        uint256 indexed proposalId,
        ProposalType indexed proposalType,
        address proposer,
        string description
    );
    event EmergencyProposalCreated(
        uint256 indexed proposalId,
        address proposer,
        string reason
    );
    event EmergencyThresholdUpdated(uint256 oldThreshold, uint256 newThreshold);

    // ============ Constructor ============
    /**
     * @notice Initializes the ShaktiGovernor
     * @param _token Governance token (staked SHAKTI wrapper)
     * @param _timelock Timelock controller address
     * @param _votingDelay Delay before voting starts (in blocks)
     * @param _votingPeriod Duration of voting (in blocks)
     * @param _proposalThreshold Minimum tokens to create proposal
     */
    constructor(
        IVotes _token,
        TimelockController _timelock,
        uint48 _votingDelay,
        uint32 _votingPeriod,
        uint256 _proposalThreshold
    )
        Governor("ShaktiGovernor")
        GovernorSettings(_votingDelay, _votingPeriod, _proposalThreshold)
        GovernorVotes(_token)
        GovernorVotesQuorumFraction(4) // 4% quorum
        GovernorTimelockControl(_timelock)
    {
        emergencyThreshold = 500_000 * 1e18; // 500,000 SHAKTI
    }

    // ============ Proposal Functions ============

    /**
     * @notice Creates a standard proposal
     * @param targets Target contract addresses
     * @param values ETH values to send
     * @param calldatas Function call data
     * @param description Proposal description
     * @return proposalId The created proposal ID
     */
    function propose(
        address[] memory targets,
        uint256[] memory values,
        bytes[] memory calldatas,
        string memory description
    ) public override(Governor) returns (uint256) {
        uint256 proposalId = super.propose(targets, values, calldatas, description);

        proposalTypes[proposalId] = ProposalType.Standard;
        proposalDescriptions[proposalId] = keccak256(bytes(description));
        totalProposals++;

        emit ProposalCreatedWithType(
            proposalId,
            ProposalType.Standard,
            msg.sender,
            description
        );

        return proposalId;
    }

    /**
     * @notice Creates a typed proposal
     * @param targets Target contract addresses
     * @param values ETH values to send
     * @param calldatas Function call data
     * @param description Proposal description
     * @param proposalType Type of proposal
     * @return proposalId The created proposal ID
     */
    function proposeWithType(
        address[] memory targets,
        uint256[] memory values,
        bytes[] memory calldatas,
        string memory description,
        ProposalType proposalType
    ) public returns (uint256) {
        if (proposalType == ProposalType.Emergency) {
            revert InvalidProposalType();
        }

        uint256 proposalId = super.propose(targets, values, calldatas, description);

        proposalTypes[proposalId] = proposalType;
        proposalDescriptions[proposalId] = keccak256(bytes(description));
        totalProposals++;

        emit ProposalCreatedWithType(
            proposalId,
            proposalType,
            msg.sender,
            description
        );

        return proposalId;
    }

    /**
     * @notice Creates an emergency proposal (higher threshold, faster execution)
     * @param targets Target contract addresses
     * @param values ETH values to send
     * @param calldatas Function call data
     * @param description Proposal description with emergency reason
     * @return proposalId The created proposal ID
     */
    function proposeEmergency(
        address[] memory targets,
        uint256[] memory values,
        bytes[] memory calldatas,
        string memory description
    ) public returns (uint256) {
        uint256 proposerVotes = getVotes(msg.sender, clock() - 1);

        if (proposerVotes < emergencyThreshold) {
            revert EmergencyThresholdNotMet(emergencyThreshold, proposerVotes);
        }

        uint256 proposalId = super.propose(targets, values, calldatas, description);

        proposalTypes[proposalId] = ProposalType.Emergency;
        proposalDescriptions[proposalId] = keccak256(bytes(description));
        totalProposals++;
        emergencyProposalsCount++;

        emit ProposalCreatedWithType(
            proposalId,
            ProposalType.Emergency,
            msg.sender,
            description
        );

        emit EmergencyProposalCreated(proposalId, msg.sender, description);

        return proposalId;
    }

    // ============ View Functions ============

    /**
     * @notice Gets the proposal type
     * @param proposalId The proposal ID
     * @return The proposal type
     */
    function getProposalType(uint256 proposalId) external view returns (ProposalType) {
        return proposalTypes[proposalId];
    }

    /**
     * @notice Checks if proposal is an emergency type
     * @param proposalId The proposal ID
     * @return True if emergency proposal
     */
    function isEmergencyProposal(uint256 proposalId) external view returns (bool) {
        return proposalTypes[proposalId] == ProposalType.Emergency;
    }

    /**
     * @notice Gets governance statistics
     * @return total Total proposals
     * @return emergency Emergency proposals count
     * @return threshold Current proposal threshold
     * @return quorumValue Current quorum requirement
     */
    function getGovernanceStats() external view returns (
        uint256 total,
        uint256 emergency,
        uint256 threshold,
        uint256 quorumValue
    ) {
        return (
            totalProposals,
            emergencyProposalsCount,
            proposalThreshold(),
            quorum(clock() - 1)
        );
    }

    // ============ Admin Functions ============

    /**
     * @notice Updates emergency threshold (via governance)
     * @param newThreshold New emergency threshold
     */
    function setEmergencyThreshold(uint256 newThreshold) external onlyGovernance {
        uint256 oldThreshold = emergencyThreshold;
        emergencyThreshold = newThreshold;

        emit EmergencyThresholdUpdated(oldThreshold, newThreshold);
    }

    // ============ Required Overrides ============

    function votingDelay()
        public
        view
        override(Governor, GovernorSettings)
        returns (uint256)
    {
        return super.votingDelay();
    }

    function votingPeriod()
        public
        view
        override(Governor, GovernorSettings)
        returns (uint256)
    {
        return super.votingPeriod();
    }

    function quorum(uint256 blockNumber)
        public
        view
        override(Governor, GovernorVotesQuorumFraction)
        returns (uint256)
    {
        return super.quorum(blockNumber);
    }

    function state(uint256 proposalId)
        public
        view
        override(Governor, GovernorTimelockControl)
        returns (ProposalState)
    {
        return super.state(proposalId);
    }

    function proposalNeedsQueuing(uint256 proposalId)
        public
        view
        override(Governor, GovernorTimelockControl)
        returns (bool)
    {
        return super.proposalNeedsQueuing(proposalId);
    }

    function proposalThreshold()
        public
        view
        override(Governor, GovernorSettings)
        returns (uint256)
    {
        return super.proposalThreshold();
    }

    function _queueOperations(
        uint256 proposalId,
        address[] memory targets,
        uint256[] memory values,
        bytes[] memory calldatas,
        bytes32 descriptionHash
    ) internal override(Governor, GovernorTimelockControl) returns (uint48) {
        return super._queueOperations(proposalId, targets, values, calldatas, descriptionHash);
    }

    function _executeOperations(
        uint256 proposalId,
        address[] memory targets,
        uint256[] memory values,
        bytes[] memory calldatas,
        bytes32 descriptionHash
    ) internal override(Governor, GovernorTimelockControl) {
        super._executeOperations(proposalId, targets, values, calldatas, descriptionHash);
    }

    function _cancel(
        address[] memory targets,
        uint256[] memory values,
        bytes[] memory calldatas,
        bytes32 descriptionHash
    ) internal override(Governor, GovernorTimelockControl) returns (uint256) {
        return super._cancel(targets, values, calldatas, descriptionHash);
    }

    function _executor()
        internal
        view
        override(Governor, GovernorTimelockControl)
        returns (address)
    {
        return super._executor();
    }
}
