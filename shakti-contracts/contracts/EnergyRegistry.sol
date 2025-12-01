// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";

/**
 * @title EnergyRegistry
 * @author SHAKTI-CHAIN Team
 * @notice Registry for prosumers, EVs, and DISCOMs in the V2G energy marketplace
 * @dev Manages registration and verification of energy market participants
 *
 * Features:
 * - Prosumer registration with KYC verification
 * - EV asset registration linked to prosumers
 * - DISCOM (Distribution Company) management
 * - Role-based access control
 * - Maximum 10 EVs per prosumer
 *
 * Gas Optimizations:
 * - Custom errors
 * - Packed struct storage
 * - Efficient mappings
 */
contract EnergyRegistry is AccessControl, Pausable {
    // ============ Custom Errors ============
    error ZeroAddress();
    error EmptyString();
    error ProsumerAlreadyRegistered(address wallet);
    error ProsumerNotFound(address wallet);
    error EVAlreadyRegistered(bytes32 vinHash);
    error EVNotFound(bytes32 vinHash);
    error MaxEVsReached(address prosumer, uint256 max);
    error NotEVOwner(address caller, bytes32 vinHash);
    error DISCOMAlreadyRegistered(bytes32 discomId);
    error DISCOMNotFound(bytes32 discomId);
    error InvalidKYCStatus();
    error InvalidBatteryCapacity();
    error InvalidDischargeRate();
    error ProsumerNotVerified(address wallet);
    error UnauthorizedCaller();

    // ============ Constants ============
    bytes32 public constant REGISTRAR_ROLE = keccak256("REGISTRAR_ROLE");
    bytes32 public constant VERIFIER_ROLE = keccak256("VERIFIER_ROLE");
    bytes32 public constant DISCOM_MANAGER_ROLE = keccak256("DISCOM_MANAGER_ROLE");

    /// @notice Maximum EVs per prosumer
    uint256 public constant MAX_EVS_PER_PROSUMER = 10;

    // ============ Enums ============
    /// @notice Types of prosumers in the energy market
    enum ProsumerType {
        RESIDENTIAL,    // Home EV owners
        COMMERCIAL,     // Commercial fleet operators
        FLEET,          // Large fleet managers
        DISCOM          // Distribution companies
    }

    /// @notice KYC verification status
    enum KYCStatus {
        PENDING,
        VERIFIED,
        REJECTED
    }

    /// @notice Charger types for EVs
    enum ChargerType {
        LEVEL1,         // Standard 120V
        LEVEL2,         // 240V
        DC_FAST,        // DC Fast Charging
        BIDIRECTIONAL   // V2G capable
    }

    // ============ Structs ============
    /// @notice Prosumer information
    struct Prosumer {
        address wallet;
        bytes32 kycHash;            // Hash of KYC documents
        ProsumerType prosumerType;
        KYCStatus kycStatus;
        bytes32 encryptedLocation;  // Encrypted location data
        bytes32 discomId;           // Associated DISCOM
        uint64 registrationTime;
        uint16 evCount;             // Number of registered EVs
        bool isActive;
    }

    /// @notice EV asset information
    struct EVAsset {
        bytes32 vinHash;            // Hashed VIN for privacy
        address owner;              // Prosumer who owns this EV
        uint128 batteryCapacity;    // In Wh (watt-hours)
        uint128 maxDischargeRate;   // In W (watts)
        ChargerType chargerType;
        bool v2gCapable;            // Can participate in V2G
        uint64 registrationTime;
        bool isActive;
    }

    /// @notice DISCOM information
    struct DISCOM {
        bytes32 discomId;
        bytes32 licenseHash;        // Hash of license documents
        string region;              // Service region
        uint64 registrationTime;
        uint32 prosumerCount;       // Number of prosumers under this DISCOM
        bool isActive;
    }

    // ============ State Variables ============
    /// @notice Mapping of wallet address to prosumer data
    mapping(address => Prosumer) public prosumers;

    /// @notice Mapping of VIN hash to EV asset
    mapping(bytes32 => EVAsset) public evAssets;

    /// @notice Mapping of prosumer to their EV VIN hashes
    mapping(address => bytes32[]) public prosumerEVs;

    /// @notice Mapping of DISCOM ID to DISCOM data
    mapping(bytes32 => DISCOM) public discoms;

    /// @notice Array of all registered prosumer addresses
    address[] public prosumerList;

    /// @notice Array of all registered DISCOM IDs
    bytes32[] public discomList;

    /// @notice Total counts
    uint256 public totalProsumers;
    uint256 public totalEVs;
    uint256 public totalDISCOMs;

    // ============ Events ============
    event ProsumerRegistered(
        address indexed wallet,
        ProsumerType prosumerType,
        bytes32 discomId,
        uint256 timestamp
    );
    event ProsumerUpdated(
        address indexed wallet,
        bytes32 encryptedLocation,
        uint256 timestamp
    );
    event ProsumerDeactivated(address indexed wallet, uint256 timestamp);
    event ProsumerReactivated(address indexed wallet, uint256 timestamp);

    event KYCStatusUpdated(
        address indexed wallet,
        KYCStatus oldStatus,
        KYCStatus newStatus,
        address indexed verifier
    );

    event EVRegistered(
        bytes32 indexed vinHash,
        address indexed owner,
        uint256 batteryCapacity,
        bool v2gCapable,
        uint256 timestamp
    );
    event EVUpdated(
        bytes32 indexed vinHash,
        uint256 batteryCapacity,
        uint256 maxDischargeRate,
        ChargerType chargerType
    );
    event EVDeactivated(bytes32 indexed vinHash, address indexed owner);
    event EVReactivated(bytes32 indexed vinHash, address indexed owner);
    event EVTransferred(
        bytes32 indexed vinHash,
        address indexed from,
        address indexed to
    );

    event DISCOMRegistered(
        bytes32 indexed discomId,
        string region,
        uint256 timestamp
    );
    event DISCOMUpdated(bytes32 indexed discomId, string region);
    event DISCOMDeactivated(bytes32 indexed discomId);
    event DISCOMReactivated(bytes32 indexed discomId);

    event ProsumerAssignedToDISCOM(
        address indexed prosumer,
        bytes32 indexed discomId
    );

    // ============ Constructor ============
    /**
     * @notice Initializes the EnergyRegistry contract
     * @param admin Address that receives admin and initial roles
     */
    constructor(address admin) {
        if (admin == address(0)) revert ZeroAddress();

        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(REGISTRAR_ROLE, admin);
        _grantRole(VERIFIER_ROLE, admin);
        _grantRole(DISCOM_MANAGER_ROLE, admin);
    }

    // ============ Prosumer Functions ============

    /**
     * @notice Registers a new prosumer
     * @param wallet Prosumer's wallet address
     * @param kycHash Hash of KYC documents
     * @param ptype Type of prosumer
     * @param encryptedLocation Encrypted location data
     * @param discomId Associated DISCOM ID
     */
    function registerProsumer(
        address wallet,
        bytes32 kycHash,
        ProsumerType ptype,
        bytes32 encryptedLocation,
        bytes32 discomId
    ) external onlyRole(REGISTRAR_ROLE) whenNotPaused {
        if (wallet == address(0)) revert ZeroAddress();
        if (prosumers[wallet].wallet != address(0)) {
            revert ProsumerAlreadyRegistered(wallet);
        }

        // Validate DISCOM exists if provided
        if (discomId != bytes32(0) && !discoms[discomId].isActive) {
            revert DISCOMNotFound(discomId);
        }

        prosumers[wallet] = Prosumer({
            wallet: wallet,
            kycHash: kycHash,
            prosumerType: ptype,
            kycStatus: KYCStatus.PENDING,
            encryptedLocation: encryptedLocation,
            discomId: discomId,
            registrationTime: uint64(block.timestamp),
            evCount: 0,
            isActive: true
        });

        prosumerList.push(wallet);
        unchecked {
            totalProsumers++;
        }

        // Update DISCOM prosumer count
        if (discomId != bytes32(0)) {
            unchecked {
                discoms[discomId].prosumerCount++;
            }
        }

        emit ProsumerRegistered(wallet, ptype, discomId, block.timestamp);
    }

    /**
     * @notice Updates KYC status for a prosumer
     * @param wallet Prosumer's wallet address
     * @param newStatus New KYC status
     */
    function updateKYCStatus(
        address wallet,
        KYCStatus newStatus
    ) external onlyRole(VERIFIER_ROLE) whenNotPaused {
        Prosumer storage prosumer = prosumers[wallet];
        if (prosumer.wallet == address(0)) revert ProsumerNotFound(wallet);

        KYCStatus oldStatus = prosumer.kycStatus;
        prosumer.kycStatus = newStatus;

        emit KYCStatusUpdated(wallet, oldStatus, newStatus, msg.sender);
    }

    /**
     * @notice Updates prosumer's encrypted location
     * @param newEncryptedLocation New encrypted location data
     */
    function updateProsumerLocation(
        bytes32 newEncryptedLocation
    ) external whenNotPaused {
        Prosumer storage prosumer = prosumers[msg.sender];
        if (prosumer.wallet == address(0)) revert ProsumerNotFound(msg.sender);

        prosumer.encryptedLocation = newEncryptedLocation;

        emit ProsumerUpdated(msg.sender, newEncryptedLocation, block.timestamp);
    }

    /**
     * @notice Assigns prosumer to a DISCOM
     * @param wallet Prosumer's wallet address
     * @param discomId DISCOM ID to assign
     */
    function assignProsumerToDISCOM(
        address wallet,
        bytes32 discomId
    ) external onlyRole(REGISTRAR_ROLE) whenNotPaused {
        Prosumer storage prosumer = prosumers[wallet];
        if (prosumer.wallet == address(0)) revert ProsumerNotFound(wallet);
        if (!discoms[discomId].isActive) revert DISCOMNotFound(discomId);

        // Decrement old DISCOM count
        if (prosumer.discomId != bytes32(0)) {
            unchecked {
                discoms[prosumer.discomId].prosumerCount--;
            }
        }

        // Update prosumer's DISCOM
        prosumer.discomId = discomId;

        // Increment new DISCOM count
        unchecked {
            discoms[discomId].prosumerCount++;
        }

        emit ProsumerAssignedToDISCOM(wallet, discomId);
    }

    /**
     * @notice Deactivates a prosumer
     * @param wallet Prosumer's wallet address
     */
    function deactivateProsumer(
        address wallet
    ) external onlyRole(REGISTRAR_ROLE) {
        Prosumer storage prosumer = prosumers[wallet];
        if (prosumer.wallet == address(0)) revert ProsumerNotFound(wallet);

        prosumer.isActive = false;

        emit ProsumerDeactivated(wallet, block.timestamp);
    }

    /**
     * @notice Reactivates a prosumer
     * @param wallet Prosumer's wallet address
     */
    function reactivateProsumer(
        address wallet
    ) external onlyRole(REGISTRAR_ROLE) {
        Prosumer storage prosumer = prosumers[wallet];
        if (prosumer.wallet == address(0)) revert ProsumerNotFound(wallet);

        prosumer.isActive = true;

        emit ProsumerReactivated(wallet, block.timestamp);
    }

    // ============ EV Registration Functions ============

    /**
     * @notice Registers a new EV asset
     * @param vin Vehicle Identification Number (will be hashed)
     * @param batteryCapacity Battery capacity in Wh
     * @param maxDischargeRate Maximum discharge rate in W
     * @param chargerType Type of charger
     * @param v2gCapable Whether EV supports V2G
     */
    function registerEV(
        string calldata vin,
        uint256 batteryCapacity,
        uint256 maxDischargeRate,
        ChargerType chargerType,
        bool v2gCapable
    ) external whenNotPaused {
        if (bytes(vin).length == 0) revert EmptyString();
        if (batteryCapacity == 0) revert InvalidBatteryCapacity();
        if (maxDischargeRate == 0) revert InvalidDischargeRate();

        Prosumer storage prosumer = prosumers[msg.sender];
        if (prosumer.wallet == address(0)) revert ProsumerNotFound(msg.sender);
        if (prosumer.kycStatus != KYCStatus.VERIFIED) {
            revert ProsumerNotVerified(msg.sender);
        }
        if (prosumer.evCount >= MAX_EVS_PER_PROSUMER) {
            revert MaxEVsReached(msg.sender, MAX_EVS_PER_PROSUMER);
        }

        bytes32 vinHash = keccak256(abi.encodePacked(vin));
        if (evAssets[vinHash].owner != address(0)) {
            revert EVAlreadyRegistered(vinHash);
        }

        evAssets[vinHash] = EVAsset({
            vinHash: vinHash,
            owner: msg.sender,
            batteryCapacity: uint128(batteryCapacity),
            maxDischargeRate: uint128(maxDischargeRate),
            chargerType: chargerType,
            v2gCapable: v2gCapable,
            registrationTime: uint64(block.timestamp),
            isActive: true
        });

        prosumerEVs[msg.sender].push(vinHash);

        unchecked {
            prosumer.evCount++;
            totalEVs++;
        }

        emit EVRegistered(vinHash, msg.sender, batteryCapacity, v2gCapable, block.timestamp);
    }

    /**
     * @notice Updates EV specifications (owner only)
     * @param vinHash Hash of the VIN
     * @param batteryCapacity New battery capacity
     * @param maxDischargeRate New max discharge rate
     * @param chargerType New charger type
     */
    function updateEV(
        bytes32 vinHash,
        uint256 batteryCapacity,
        uint256 maxDischargeRate,
        ChargerType chargerType
    ) external whenNotPaused {
        EVAsset storage ev = evAssets[vinHash];
        if (ev.owner == address(0)) revert EVNotFound(vinHash);
        if (ev.owner != msg.sender) revert NotEVOwner(msg.sender, vinHash);
        if (batteryCapacity == 0) revert InvalidBatteryCapacity();
        if (maxDischargeRate == 0) revert InvalidDischargeRate();

        ev.batteryCapacity = uint128(batteryCapacity);
        ev.maxDischargeRate = uint128(maxDischargeRate);
        ev.chargerType = chargerType;

        emit EVUpdated(vinHash, batteryCapacity, maxDischargeRate, chargerType);
    }

    /**
     * @notice Updates EV V2G capability (owner only)
     * @param vinHash Hash of the VIN
     * @param v2gCapable New V2G capability status
     */
    function updateEVV2GCapability(
        bytes32 vinHash,
        bool v2gCapable
    ) external whenNotPaused {
        EVAsset storage ev = evAssets[vinHash];
        if (ev.owner == address(0)) revert EVNotFound(vinHash);
        if (ev.owner != msg.sender) revert NotEVOwner(msg.sender, vinHash);

        ev.v2gCapable = v2gCapable;
    }

    /**
     * @notice Deactivates an EV (owner only)
     * @param vinHash Hash of the VIN
     */
    function deactivateEV(bytes32 vinHash) external {
        EVAsset storage ev = evAssets[vinHash];
        if (ev.owner == address(0)) revert EVNotFound(vinHash);
        if (ev.owner != msg.sender) revert NotEVOwner(msg.sender, vinHash);

        ev.isActive = false;

        emit EVDeactivated(vinHash, msg.sender);
    }

    /**
     * @notice Reactivates an EV (owner only)
     * @param vinHash Hash of the VIN
     */
    function reactivateEV(bytes32 vinHash) external {
        EVAsset storage ev = evAssets[vinHash];
        if (ev.owner == address(0)) revert EVNotFound(vinHash);
        if (ev.owner != msg.sender) revert NotEVOwner(msg.sender, vinHash);

        ev.isActive = true;

        emit EVReactivated(vinHash, msg.sender);
    }

    /**
     * @notice Transfers EV ownership to another verified prosumer
     * @param vinHash Hash of the VIN
     * @param newOwner New owner's address
     */
    function transferEV(
        bytes32 vinHash,
        address newOwner
    ) external whenNotPaused {
        EVAsset storage ev = evAssets[vinHash];
        if (ev.owner == address(0)) revert EVNotFound(vinHash);
        if (ev.owner != msg.sender) revert NotEVOwner(msg.sender, vinHash);

        Prosumer storage newProsumer = prosumers[newOwner];
        if (newProsumer.wallet == address(0)) revert ProsumerNotFound(newOwner);
        if (newProsumer.kycStatus != KYCStatus.VERIFIED) {
            revert ProsumerNotVerified(newOwner);
        }
        if (newProsumer.evCount >= MAX_EVS_PER_PROSUMER) {
            revert MaxEVsReached(newOwner, MAX_EVS_PER_PROSUMER);
        }

        address oldOwner = ev.owner;

        // Update EV ownership
        ev.owner = newOwner;

        // Update prosumer EV counts
        unchecked {
            prosumers[oldOwner].evCount--;
            newProsumer.evCount++;
        }

        // Add to new owner's EV list
        prosumerEVs[newOwner].push(vinHash);

        // Remove from old owner's EV list
        _removeEVFromProsumer(oldOwner, vinHash);

        emit EVTransferred(vinHash, oldOwner, newOwner);
    }

    // ============ DISCOM Functions ============

    /**
     * @notice Registers a new DISCOM
     * @param licenseHash Hash of license documents
     * @param region Service region
     */
    function registerDISCOM(
        bytes32 licenseHash,
        string calldata region
    ) external onlyRole(DISCOM_MANAGER_ROLE) whenNotPaused {
        if (licenseHash == bytes32(0)) revert EmptyString();
        if (bytes(region).length == 0) revert EmptyString();

        bytes32 discomId = keccak256(abi.encodePacked(licenseHash, region, block.timestamp));

        if (discoms[discomId].discomId != bytes32(0)) {
            revert DISCOMAlreadyRegistered(discomId);
        }

        discoms[discomId] = DISCOM({
            discomId: discomId,
            licenseHash: licenseHash,
            region: region,
            registrationTime: uint64(block.timestamp),
            prosumerCount: 0,
            isActive: true
        });

        discomList.push(discomId);

        unchecked {
            totalDISCOMs++;
        }

        emit DISCOMRegistered(discomId, region, block.timestamp);
    }

    /**
     * @notice Updates DISCOM region
     * @param discomId DISCOM ID
     * @param region New region
     */
    function updateDISCOM(
        bytes32 discomId,
        string calldata region
    ) external onlyRole(DISCOM_MANAGER_ROLE) {
        if (!discoms[discomId].isActive) revert DISCOMNotFound(discomId);
        if (bytes(region).length == 0) revert EmptyString();

        discoms[discomId].region = region;

        emit DISCOMUpdated(discomId, region);
    }

    /**
     * @notice Deactivates a DISCOM
     * @param discomId DISCOM ID
     */
    function deactivateDISCOM(
        bytes32 discomId
    ) external onlyRole(DISCOM_MANAGER_ROLE) {
        if (discoms[discomId].discomId == bytes32(0)) revert DISCOMNotFound(discomId);

        discoms[discomId].isActive = false;

        emit DISCOMDeactivated(discomId);
    }

    /**
     * @notice Reactivates a DISCOM
     * @param discomId DISCOM ID
     */
    function reactivateDISCOM(
        bytes32 discomId
    ) external onlyRole(DISCOM_MANAGER_ROLE) {
        if (discoms[discomId].discomId == bytes32(0)) revert DISCOMNotFound(discomId);

        discoms[discomId].isActive = true;

        emit DISCOMReactivated(discomId);
    }

    // ============ View Functions ============

    /**
     * @notice Gets full prosumer information
     * @param wallet Prosumer's wallet address
     */
    function getProsumer(address wallet) external view returns (
        address walletAddr,
        bytes32 kycHash,
        ProsumerType prosumerType,
        KYCStatus kycStatus,
        bytes32 encryptedLocation,
        bytes32 discomId,
        uint256 registrationTime,
        uint256 evCount,
        bool isActive
    ) {
        Prosumer storage p = prosumers[wallet];
        return (
            p.wallet,
            p.kycHash,
            p.prosumerType,
            p.kycStatus,
            p.encryptedLocation,
            p.discomId,
            p.registrationTime,
            p.evCount,
            p.isActive
        );
    }

    /**
     * @notice Gets all EVs owned by a prosumer
     * @param owner Prosumer's address
     */
    function getProsumerEVs(address owner) external view returns (bytes32[] memory) {
        return prosumerEVs[owner];
    }

    /**
     * @notice Gets full EV information
     * @param vinHash Hash of the VIN
     */
    function getEV(bytes32 vinHash) external view returns (
        bytes32 hash,
        address owner,
        uint256 batteryCapacity,
        uint256 maxDischargeRate,
        ChargerType chargerType,
        bool v2gCapable,
        uint256 registrationTime,
        bool isActive
    ) {
        EVAsset storage ev = evAssets[vinHash];
        return (
            ev.vinHash,
            ev.owner,
            ev.batteryCapacity,
            ev.maxDischargeRate,
            ev.chargerType,
            ev.v2gCapable,
            ev.registrationTime,
            ev.isActive
        );
    }

    /**
     * @notice Gets full DISCOM information
     * @param discomId DISCOM ID
     */
    function getDISCOM(bytes32 discomId) external view returns (
        bytes32 id,
        bytes32 licenseHash,
        string memory region,
        uint256 registrationTime,
        uint256 prosumerCount,
        bool isActive
    ) {
        DISCOM storage d = discoms[discomId];
        return (
            d.discomId,
            d.licenseHash,
            d.region,
            d.registrationTime,
            d.prosumerCount,
            d.isActive
        );
    }

    /**
     * @notice Gets all registered prosumer addresses
     */
    function getAllProsumers() external view returns (address[] memory) {
        return prosumerList;
    }

    /**
     * @notice Gets all registered DISCOM IDs
     */
    function getAllDISCOMs() external view returns (bytes32[] memory) {
        return discomList;
    }

    /**
     * @notice Checks if a prosumer is verified
     * @param wallet Prosumer's wallet address
     */
    function isVerifiedProsumer(address wallet) external view returns (bool) {
        return prosumers[wallet].kycStatus == KYCStatus.VERIFIED &&
               prosumers[wallet].isActive;
    }

    /**
     * @notice Gets prosumers by type
     * @param ptype Prosumer type to filter
     */
    function getProsumersByType(ProsumerType ptype) external view returns (address[] memory) {
        uint256 count = 0;
        for (uint256 i = 0; i < prosumerList.length; i++) {
            if (prosumers[prosumerList[i]].prosumerType == ptype) {
                count++;
            }
        }

        address[] memory result = new address[](count);
        uint256 index = 0;
        for (uint256 i = 0; i < prosumerList.length; i++) {
            if (prosumers[prosumerList[i]].prosumerType == ptype) {
                result[index] = prosumerList[i];
                index++;
            }
        }

        return result;
    }

    /**
     * @notice Gets V2G capable EVs
     */
    function getV2GCapableEVCount() external view returns (uint256) {
        uint256 count = 0;
        for (uint256 i = 0; i < prosumerList.length; i++) {
            bytes32[] storage evs = prosumerEVs[prosumerList[i]];
            for (uint256 j = 0; j < evs.length; j++) {
                if (evAssets[evs[j]].v2gCapable && evAssets[evs[j]].isActive) {
                    count++;
                }
            }
        }
        return count;
    }

    // ============ Admin Functions ============

    /**
     * @notice Pauses the contract
     */
    function pause() external onlyRole(DEFAULT_ADMIN_ROLE) {
        _pause();
    }

    /**
     * @notice Unpauses the contract
     */
    function unpause() external onlyRole(DEFAULT_ADMIN_ROLE) {
        _unpause();
    }

    // ============ Internal Functions ============

    /**
     * @dev Removes an EV from prosumer's EV list
     */
    function _removeEVFromProsumer(address prosumer, bytes32 vinHash) internal {
        bytes32[] storage evs = prosumerEVs[prosumer];
        for (uint256 i = 0; i < evs.length; i++) {
            if (evs[i] == vinHash) {
                evs[i] = evs[evs.length - 1];
                evs.pop();
                break;
            }
        }
    }
}
