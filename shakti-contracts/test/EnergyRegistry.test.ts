import { expect } from "chai";
import { ethers } from "hardhat";
import { loadFixture } from "@nomicfoundation/hardhat-network-helpers";
import { EnergyRegistry } from "../typechain-types";

describe("EnergyRegistry", function () {
  // Constants
  const MAX_EVS_PER_PROSUMER = 10;

  // Roles
  const REGISTRAR_ROLE = ethers.keccak256(ethers.toUtf8Bytes("REGISTRAR_ROLE"));
  const VERIFIER_ROLE = ethers.keccak256(ethers.toUtf8Bytes("VERIFIER_ROLE"));
  const DISCOM_MANAGER_ROLE = ethers.keccak256(ethers.toUtf8Bytes("DISCOM_MANAGER_ROLE"));
  const DEFAULT_ADMIN_ROLE = ethers.ZeroHash;

  // Enums
  enum ProsumerType { RESIDENTIAL, COMMERCIAL, FLEET, DISCOM }
  enum KYCStatus { PENDING, VERIFIED, REJECTED }
  enum ChargerType { LEVEL1, LEVEL2, DC_FAST, BIDIRECTIONAL }

  // Sample data
  const sampleKYCHash = ethers.keccak256(ethers.toUtf8Bytes("KYC_DOCUMENTS"));
  const sampleLocation = ethers.keccak256(ethers.toUtf8Bytes("ENCRYPTED_LOCATION"));
  const sampleLicenseHash = ethers.keccak256(ethers.toUtf8Bytes("DISCOM_LICENSE"));
  const sampleVIN = "1HGBH41JXMN109186";
  const sampleBatteryCapacity = 75000n; // 75 kWh in Wh
  const sampleMaxDischargeRate = 11000n; // 11 kW in W

  async function deployFixture() {
    const [admin, registrar, verifier, discomManager, prosumer1, prosumer2, prosumer3, unauthorized] =
      await ethers.getSigners();

    const EnergyRegistryFactory = await ethers.getContractFactory("EnergyRegistry");
    const registry = await EnergyRegistryFactory.deploy(admin.address);
    await registry.waitForDeployment();

    // Grant roles
    await registry.connect(admin).grantRole(REGISTRAR_ROLE, registrar.address);
    await registry.connect(admin).grantRole(VERIFIER_ROLE, verifier.address);
    await registry.connect(admin).grantRole(DISCOM_MANAGER_ROLE, discomManager.address);

    return {
      registry,
      admin,
      registrar,
      verifier,
      discomManager,
      prosumer1,
      prosumer2,
      prosumer3,
      unauthorized
    };
  }

  async function deployWithDISCOMFixture() {
    const fixture = await loadFixture(deployFixture);
    const { registry, discomManager } = fixture;

    // Register a DISCOM
    const tx = await registry.connect(discomManager).registerDISCOM(sampleLicenseHash, "Maharashtra");
    const receipt = await tx.wait();

    // Get DISCOM ID from event
    const event = receipt?.logs.find(
      (log: any) => log.fragment?.name === "DISCOMRegistered"
    );
    const discomId = (event as any)?.args?.[0] || ethers.ZeroHash;

    return { ...fixture, discomId };
  }

  async function deployWithProsumerFixture() {
    const fixture = await loadFixture(deployWithDISCOMFixture);
    const { registry, registrar, verifier, prosumer1, discomId } = fixture;

    // Register prosumer
    await registry.connect(registrar).registerProsumer(
      prosumer1.address,
      sampleKYCHash,
      ProsumerType.RESIDENTIAL,
      sampleLocation,
      discomId
    );

    // Verify prosumer
    await registry.connect(verifier).updateKYCStatus(prosumer1.address, KYCStatus.VERIFIED);

    return fixture;
  }

  // ============ Deployment Tests ============
  describe("Deployment", function () {
    it("should deploy with correct admin roles", async function () {
      const { registry, admin } = await loadFixture(deployFixture);

      expect(await registry.hasRole(DEFAULT_ADMIN_ROLE, admin.address)).to.be.true;
      expect(await registry.hasRole(REGISTRAR_ROLE, admin.address)).to.be.true;
      expect(await registry.hasRole(VERIFIER_ROLE, admin.address)).to.be.true;
      expect(await registry.hasRole(DISCOM_MANAGER_ROLE, admin.address)).to.be.true;
    });

    it("should revert if admin is zero address", async function () {
      const EnergyRegistryFactory = await ethers.getContractFactory("EnergyRegistry");

      await expect(EnergyRegistryFactory.deploy(ethers.ZeroAddress))
        .to.be.revertedWithCustomError(EnergyRegistryFactory, "ZeroAddress");
    });

    it("should initialize with zero counts", async function () {
      const { registry } = await loadFixture(deployFixture);

      expect(await registry.totalProsumers()).to.equal(0);
      expect(await registry.totalEVs()).to.equal(0);
      expect(await registry.totalDISCOMs()).to.equal(0);
    });
  });

  // ============ DISCOM Registration Tests ============
  describe("DISCOM Registration", function () {
    it("should register a new DISCOM", async function () {
      const { registry, discomManager } = await loadFixture(deployFixture);

      await expect(registry.connect(discomManager).registerDISCOM(sampleLicenseHash, "Maharashtra"))
        .to.emit(registry, "DISCOMRegistered");

      expect(await registry.totalDISCOMs()).to.equal(1);
    });

    it("should store correct DISCOM information", async function () {
      const { registry, discomId } = await loadFixture(deployWithDISCOMFixture);

      const [id, licenseHash, region, , , isActive] = await registry.getDISCOM(discomId);

      expect(id).to.equal(discomId);
      expect(licenseHash).to.equal(sampleLicenseHash);
      expect(region).to.equal("Maharashtra");
      expect(isActive).to.be.true;
    });

    it("should revert if non-manager tries to register DISCOM", async function () {
      const { registry, unauthorized } = await loadFixture(deployFixture);

      await expect(
        registry.connect(unauthorized).registerDISCOM(sampleLicenseHash, "Maharashtra")
      ).to.be.revertedWithCustomError(registry, "AccessControlUnauthorizedAccount");
    });

    it("should revert if license hash is empty", async function () {
      const { registry, discomManager } = await loadFixture(deployFixture);

      await expect(
        registry.connect(discomManager).registerDISCOM(ethers.ZeroHash, "Maharashtra")
      ).to.be.revertedWithCustomError(registry, "EmptyString");
    });

    it("should revert if region is empty", async function () {
      const { registry, discomManager } = await loadFixture(deployFixture);

      await expect(
        registry.connect(discomManager).registerDISCOM(sampleLicenseHash, "")
      ).to.be.revertedWithCustomError(registry, "EmptyString");
    });

    it("should allow updating DISCOM region", async function () {
      const { registry, discomManager, discomId } = await loadFixture(deployWithDISCOMFixture);

      await expect(registry.connect(discomManager).updateDISCOM(discomId, "Gujarat"))
        .to.emit(registry, "DISCOMUpdated")
        .withArgs(discomId, "Gujarat");

      const [, , region] = await registry.getDISCOM(discomId);
      expect(region).to.equal("Gujarat");
    });

    it("should allow deactivating and reactivating DISCOM", async function () {
      const { registry, discomManager, discomId } = await loadFixture(deployWithDISCOMFixture);

      await expect(registry.connect(discomManager).deactivateDISCOM(discomId))
        .to.emit(registry, "DISCOMDeactivated")
        .withArgs(discomId);

      let [, , , , , isActive] = await registry.getDISCOM(discomId);
      expect(isActive).to.be.false;

      await expect(registry.connect(discomManager).reactivateDISCOM(discomId))
        .to.emit(registry, "DISCOMReactivated")
        .withArgs(discomId);

      [, , , , , isActive] = await registry.getDISCOM(discomId);
      expect(isActive).to.be.true;
    });
  });

  // ============ Prosumer Registration Tests ============
  describe("Prosumer Registration", function () {
    it("should register a new prosumer", async function () {
      const { registry, registrar, prosumer1, discomId } = await loadFixture(deployWithDISCOMFixture);

      await expect(
        registry.connect(registrar).registerProsumer(
          prosumer1.address,
          sampleKYCHash,
          ProsumerType.RESIDENTIAL,
          sampleLocation,
          discomId
        )
      ).to.emit(registry, "ProsumerRegistered");

      expect(await registry.totalProsumers()).to.equal(1);
    });

    it("should store correct prosumer information", async function () {
      const { registry, prosumer1 } = await loadFixture(deployWithProsumerFixture);

      const [wallet, kycHash, prosumerType, kycStatus, , , , evCount, isActive] =
        await registry.getProsumer(prosumer1.address);

      expect(wallet).to.equal(prosumer1.address);
      expect(kycHash).to.equal(sampleKYCHash);
      expect(prosumerType).to.equal(ProsumerType.RESIDENTIAL);
      expect(kycStatus).to.equal(KYCStatus.VERIFIED);
      expect(evCount).to.equal(0);
      expect(isActive).to.be.true;
    });

    it("should revert if prosumer already registered", async function () {
      const { registry, registrar, prosumer1, discomId } = await loadFixture(deployWithProsumerFixture);

      await expect(
        registry.connect(registrar).registerProsumer(
          prosumer1.address,
          sampleKYCHash,
          ProsumerType.COMMERCIAL,
          sampleLocation,
          discomId
        )
      ).to.be.revertedWithCustomError(registry, "ProsumerAlreadyRegistered")
        .withArgs(prosumer1.address);
    });

    it("should revert if non-registrar tries to register prosumer", async function () {
      const { registry, unauthorized, prosumer2, discomId } = await loadFixture(deployWithDISCOMFixture);

      await expect(
        registry.connect(unauthorized).registerProsumer(
          prosumer2.address,
          sampleKYCHash,
          ProsumerType.RESIDENTIAL,
          sampleLocation,
          discomId
        )
      ).to.be.revertedWithCustomError(registry, "AccessControlUnauthorizedAccount");
    });

    it("should revert if wallet is zero address", async function () {
      const { registry, registrar, discomId } = await loadFixture(deployWithDISCOMFixture);

      await expect(
        registry.connect(registrar).registerProsumer(
          ethers.ZeroAddress,
          sampleKYCHash,
          ProsumerType.RESIDENTIAL,
          sampleLocation,
          discomId
        )
      ).to.be.revertedWithCustomError(registry, "ZeroAddress");
    });

    it("should allow registering without DISCOM", async function () {
      const { registry, registrar, prosumer1 } = await loadFixture(deployFixture);

      await expect(
        registry.connect(registrar).registerProsumer(
          prosumer1.address,
          sampleKYCHash,
          ProsumerType.RESIDENTIAL,
          sampleLocation,
          ethers.ZeroHash // No DISCOM
        )
      ).to.emit(registry, "ProsumerRegistered");
    });

    it("should increment DISCOM prosumer count", async function () {
      const { registry, discomId } = await loadFixture(deployWithProsumerFixture);

      const [, , , , prosumerCount] = await registry.getDISCOM(discomId);
      expect(prosumerCount).to.equal(1);
    });

    it("should register all prosumer types", async function () {
      const { registry, registrar, prosumer1, prosumer2, prosumer3, unauthorized, discomId } =
        await loadFixture(deployWithDISCOMFixture);

      await registry.connect(registrar).registerProsumer(
        prosumer1.address, sampleKYCHash, ProsumerType.RESIDENTIAL, sampleLocation, discomId
      );
      await registry.connect(registrar).registerProsumer(
        prosumer2.address, sampleKYCHash, ProsumerType.COMMERCIAL, sampleLocation, discomId
      );
      await registry.connect(registrar).registerProsumer(
        prosumer3.address, sampleKYCHash, ProsumerType.FLEET, sampleLocation, discomId
      );
      await registry.connect(registrar).registerProsumer(
        unauthorized.address, sampleKYCHash, ProsumerType.DISCOM, sampleLocation, discomId
      );

      expect(await registry.totalProsumers()).to.equal(4);
    });
  });

  // ============ KYC Status Tests ============
  describe("KYC Status", function () {
    it("should start with PENDING status", async function () {
      const { registry, registrar, prosumer1, discomId } = await loadFixture(deployWithDISCOMFixture);

      await registry.connect(registrar).registerProsumer(
        prosumer1.address,
        sampleKYCHash,
        ProsumerType.RESIDENTIAL,
        sampleLocation,
        discomId
      );

      const [, , , kycStatus] = await registry.getProsumer(prosumer1.address);
      expect(kycStatus).to.equal(KYCStatus.PENDING);
    });

    it("should update KYC status to VERIFIED", async function () {
      const { registry, registrar, verifier, prosumer1, discomId } = await loadFixture(deployWithDISCOMFixture);

      await registry.connect(registrar).registerProsumer(
        prosumer1.address, sampleKYCHash, ProsumerType.RESIDENTIAL, sampleLocation, discomId
      );

      await expect(registry.connect(verifier).updateKYCStatus(prosumer1.address, KYCStatus.VERIFIED))
        .to.emit(registry, "KYCStatusUpdated")
        .withArgs(prosumer1.address, KYCStatus.PENDING, KYCStatus.VERIFIED, verifier.address);

      const [, , , kycStatus] = await registry.getProsumer(prosumer1.address);
      expect(kycStatus).to.equal(KYCStatus.VERIFIED);
    });

    it("should update KYC status to REJECTED", async function () {
      const { registry, registrar, verifier, prosumer1, discomId } = await loadFixture(deployWithDISCOMFixture);

      await registry.connect(registrar).registerProsumer(
        prosumer1.address, sampleKYCHash, ProsumerType.RESIDENTIAL, sampleLocation, discomId
      );

      await registry.connect(verifier).updateKYCStatus(prosumer1.address, KYCStatus.REJECTED);

      const [, , , kycStatus] = await registry.getProsumer(prosumer1.address);
      expect(kycStatus).to.equal(KYCStatus.REJECTED);
    });

    it("should revert if non-verifier tries to update KYC", async function () {
      const { registry, prosumer1 } = await loadFixture(deployWithProsumerFixture);

      await expect(
        registry.connect(prosumer1).updateKYCStatus(prosumer1.address, KYCStatus.VERIFIED)
      ).to.be.revertedWithCustomError(registry, "AccessControlUnauthorizedAccount");
    });

    it("should revert if prosumer not found", async function () {
      const { registry, verifier, unauthorized } = await loadFixture(deployFixture);

      await expect(
        registry.connect(verifier).updateKYCStatus(unauthorized.address, KYCStatus.VERIFIED)
      ).to.be.revertedWithCustomError(registry, "ProsumerNotFound");
    });
  });

  // ============ EV Registration Tests ============
  describe("EV Registration", function () {
    it("should register a new EV for verified prosumer", async function () {
      const { registry, prosumer1 } = await loadFixture(deployWithProsumerFixture);

      const vinHash = ethers.keccak256(ethers.toUtf8Bytes(sampleVIN));

      await expect(
        registry.connect(prosumer1).registerEV(
          sampleVIN,
          sampleBatteryCapacity,
          sampleMaxDischargeRate,
          ChargerType.BIDIRECTIONAL,
          true
        )
      ).to.emit(registry, "EVRegistered");

      expect(await registry.totalEVs()).to.equal(1);
    });

    it("should store correct EV information", async function () {
      const { registry, prosumer1 } = await loadFixture(deployWithProsumerFixture);

      await registry.connect(prosumer1).registerEV(
        sampleVIN, sampleBatteryCapacity, sampleMaxDischargeRate, ChargerType.BIDIRECTIONAL, true
      );

      const vinHash = ethers.keccak256(ethers.toUtf8Bytes(sampleVIN));
      const [hash, owner, batteryCapacity, maxDischargeRate, chargerType, v2gCapable, , isActive] =
        await registry.getEV(vinHash);

      expect(hash).to.equal(vinHash);
      expect(owner).to.equal(prosumer1.address);
      expect(batteryCapacity).to.equal(sampleBatteryCapacity);
      expect(maxDischargeRate).to.equal(sampleMaxDischargeRate);
      expect(chargerType).to.equal(ChargerType.BIDIRECTIONAL);
      expect(v2gCapable).to.be.true;
      expect(isActive).to.be.true;
    });

    it("should revert if prosumer not verified", async function () {
      const { registry, registrar, prosumer2, discomId } = await loadFixture(deployWithDISCOMFixture);

      // Register but don't verify
      await registry.connect(registrar).registerProsumer(
        prosumer2.address, sampleKYCHash, ProsumerType.RESIDENTIAL, sampleLocation, discomId
      );

      await expect(
        registry.connect(prosumer2).registerEV(
          sampleVIN, sampleBatteryCapacity, sampleMaxDischargeRate, ChargerType.LEVEL2, false
        )
      ).to.be.revertedWithCustomError(registry, "ProsumerNotVerified");
    });

    it("should revert if EV already registered", async function () {
      const { registry, prosumer1 } = await loadFixture(deployWithProsumerFixture);

      await registry.connect(prosumer1).registerEV(
        sampleVIN, sampleBatteryCapacity, sampleMaxDischargeRate, ChargerType.LEVEL2, false
      );

      await expect(
        registry.connect(prosumer1).registerEV(
          sampleVIN, sampleBatteryCapacity, sampleMaxDischargeRate, ChargerType.LEVEL2, false
        )
      ).to.be.revertedWithCustomError(registry, "EVAlreadyRegistered");
    });

    it("should revert if VIN is empty", async function () {
      const { registry, prosumer1 } = await loadFixture(deployWithProsumerFixture);

      await expect(
        registry.connect(prosumer1).registerEV(
          "", sampleBatteryCapacity, sampleMaxDischargeRate, ChargerType.LEVEL2, false
        )
      ).to.be.revertedWithCustomError(registry, "EmptyString");
    });

    it("should revert if battery capacity is zero", async function () {
      const { registry, prosumer1 } = await loadFixture(deployWithProsumerFixture);

      await expect(
        registry.connect(prosumer1).registerEV(
          sampleVIN, 0, sampleMaxDischargeRate, ChargerType.LEVEL2, false
        )
      ).to.be.revertedWithCustomError(registry, "InvalidBatteryCapacity");
    });

    it("should revert if max discharge rate is zero", async function () {
      const { registry, prosumer1 } = await loadFixture(deployWithProsumerFixture);

      await expect(
        registry.connect(prosumer1).registerEV(
          sampleVIN, sampleBatteryCapacity, 0, ChargerType.LEVEL2, false
        )
      ).to.be.revertedWithCustomError(registry, "InvalidDischargeRate");
    });

    it("should enforce maximum EVs per prosumer", async function () {
      const { registry, prosumer1 } = await loadFixture(deployWithProsumerFixture);

      // Register maximum EVs
      for (let i = 0; i < MAX_EVS_PER_PROSUMER; i++) {
        await registry.connect(prosumer1).registerEV(
          `VIN${i}`, sampleBatteryCapacity, sampleMaxDischargeRate, ChargerType.LEVEL2, false
        );
      }

      // Try to register one more
      await expect(
        registry.connect(prosumer1).registerEV(
          "VIN_OVERFLOW", sampleBatteryCapacity, sampleMaxDischargeRate, ChargerType.LEVEL2, false
        )
      ).to.be.revertedWithCustomError(registry, "MaxEVsReached")
        .withArgs(prosumer1.address, MAX_EVS_PER_PROSUMER);
    });

    it("should track prosumer EV count correctly", async function () {
      const { registry, prosumer1 } = await loadFixture(deployWithProsumerFixture);

      await registry.connect(prosumer1).registerEV(
        "VIN1", sampleBatteryCapacity, sampleMaxDischargeRate, ChargerType.LEVEL2, false
      );
      await registry.connect(prosumer1).registerEV(
        "VIN2", sampleBatteryCapacity, sampleMaxDischargeRate, ChargerType.LEVEL2, false
      );

      const [, , , , , , , evCount] = await registry.getProsumer(prosumer1.address);
      expect(evCount).to.equal(2);
    });

    it("should return prosumer EVs", async function () {
      const { registry, prosumer1 } = await loadFixture(deployWithProsumerFixture);

      await registry.connect(prosumer1).registerEV(
        "VIN1", sampleBatteryCapacity, sampleMaxDischargeRate, ChargerType.LEVEL2, false
      );
      await registry.connect(prosumer1).registerEV(
        "VIN2", sampleBatteryCapacity, sampleMaxDischargeRate, ChargerType.BIDIRECTIONAL, true
      );

      const evs = await registry.getProsumerEVs(prosumer1.address);
      expect(evs.length).to.equal(2);
    });
  });

  // ============ EV Update Tests ============
  describe("EV Updates", function () {
    it("should allow owner to update EV specs", async function () {
      const { registry, prosumer1 } = await loadFixture(deployWithProsumerFixture);

      await registry.connect(prosumer1).registerEV(
        sampleVIN, sampleBatteryCapacity, sampleMaxDischargeRate, ChargerType.LEVEL2, false
      );

      const vinHash = ethers.keccak256(ethers.toUtf8Bytes(sampleVIN));
      const newCapacity = 100000n;
      const newDischargeRate = 22000n;

      await expect(
        registry.connect(prosumer1).updateEV(vinHash, newCapacity, newDischargeRate, ChargerType.DC_FAST)
      ).to.emit(registry, "EVUpdated")
        .withArgs(vinHash, newCapacity, newDischargeRate, ChargerType.DC_FAST);

      const [, , batteryCapacity, maxDischargeRate, chargerType] = await registry.getEV(vinHash);
      expect(batteryCapacity).to.equal(newCapacity);
      expect(maxDischargeRate).to.equal(newDischargeRate);
      expect(chargerType).to.equal(ChargerType.DC_FAST);
    });

    it("should revert if non-owner tries to update EV", async function () {
      const { registry, prosumer1, prosumer2, registrar, verifier, discomId } =
        await loadFixture(deployWithProsumerFixture);

      await registry.connect(prosumer1).registerEV(
        sampleVIN, sampleBatteryCapacity, sampleMaxDischargeRate, ChargerType.LEVEL2, false
      );

      // Register and verify prosumer2
      await registry.connect(registrar).registerProsumer(
        prosumer2.address, sampleKYCHash, ProsumerType.COMMERCIAL, sampleLocation, discomId
      );
      await registry.connect(verifier).updateKYCStatus(prosumer2.address, KYCStatus.VERIFIED);

      const vinHash = ethers.keccak256(ethers.toUtf8Bytes(sampleVIN));

      await expect(
        registry.connect(prosumer2).updateEV(vinHash, 100000n, 22000n, ChargerType.DC_FAST)
      ).to.be.revertedWithCustomError(registry, "NotEVOwner");
    });

    it("should allow owner to update V2G capability", async function () {
      const { registry, prosumer1 } = await loadFixture(deployWithProsumerFixture);

      await registry.connect(prosumer1).registerEV(
        sampleVIN, sampleBatteryCapacity, sampleMaxDischargeRate, ChargerType.BIDIRECTIONAL, false
      );

      const vinHash = ethers.keccak256(ethers.toUtf8Bytes(sampleVIN));

      await registry.connect(prosumer1).updateEVV2GCapability(vinHash, true);

      const [, , , , , v2gCapable] = await registry.getEV(vinHash);
      expect(v2gCapable).to.be.true;
    });

    it("should allow deactivating and reactivating EV", async function () {
      const { registry, prosumer1 } = await loadFixture(deployWithProsumerFixture);

      await registry.connect(prosumer1).registerEV(
        sampleVIN, sampleBatteryCapacity, sampleMaxDischargeRate, ChargerType.LEVEL2, false
      );

      const vinHash = ethers.keccak256(ethers.toUtf8Bytes(sampleVIN));

      await expect(registry.connect(prosumer1).deactivateEV(vinHash))
        .to.emit(registry, "EVDeactivated")
        .withArgs(vinHash, prosumer1.address);

      let [, , , , , , , isActive] = await registry.getEV(vinHash);
      expect(isActive).to.be.false;

      await expect(registry.connect(prosumer1).reactivateEV(vinHash))
        .to.emit(registry, "EVReactivated")
        .withArgs(vinHash, prosumer1.address);

      [, , , , , , , isActive] = await registry.getEV(vinHash);
      expect(isActive).to.be.true;
    });
  });

  // ============ EV Transfer Tests ============
  describe("EV Transfer", function () {
    it("should transfer EV to another verified prosumer", async function () {
      const { registry, registrar, verifier, prosumer1, prosumer2, discomId } =
        await loadFixture(deployWithProsumerFixture);

      // Register and verify prosumer2
      await registry.connect(registrar).registerProsumer(
        prosumer2.address, sampleKYCHash, ProsumerType.COMMERCIAL, sampleLocation, discomId
      );
      await registry.connect(verifier).updateKYCStatus(prosumer2.address, KYCStatus.VERIFIED);

      // Register EV for prosumer1
      await registry.connect(prosumer1).registerEV(
        sampleVIN, sampleBatteryCapacity, sampleMaxDischargeRate, ChargerType.LEVEL2, false
      );

      const vinHash = ethers.keccak256(ethers.toUtf8Bytes(sampleVIN));

      // Transfer to prosumer2
      await expect(registry.connect(prosumer1).transferEV(vinHash, prosumer2.address))
        .to.emit(registry, "EVTransferred")
        .withArgs(vinHash, prosumer1.address, prosumer2.address);

      const [, owner] = await registry.getEV(vinHash);
      expect(owner).to.equal(prosumer2.address);

      // Check EV counts updated
      const [, , , , , , , evCount1] = await registry.getProsumer(prosumer1.address);
      const [, , , , , , , evCount2] = await registry.getProsumer(prosumer2.address);
      expect(evCount1).to.equal(0);
      expect(evCount2).to.equal(1);
    });

    it("should revert transfer to unverified prosumer", async function () {
      const { registry, registrar, prosumer1, prosumer2, discomId } =
        await loadFixture(deployWithProsumerFixture);

      // Register but don't verify prosumer2
      await registry.connect(registrar).registerProsumer(
        prosumer2.address, sampleKYCHash, ProsumerType.COMMERCIAL, sampleLocation, discomId
      );

      await registry.connect(prosumer1).registerEV(
        sampleVIN, sampleBatteryCapacity, sampleMaxDischargeRate, ChargerType.LEVEL2, false
      );

      const vinHash = ethers.keccak256(ethers.toUtf8Bytes(sampleVIN));

      await expect(registry.connect(prosumer1).transferEV(vinHash, prosumer2.address))
        .to.be.revertedWithCustomError(registry, "ProsumerNotVerified");
    });

    it("should revert transfer if receiver at max EVs", async function () {
      const { registry, registrar, verifier, prosumer1, prosumer2, discomId } =
        await loadFixture(deployWithProsumerFixture);

      // Register and verify prosumer2
      await registry.connect(registrar).registerProsumer(
        prosumer2.address, sampleKYCHash, ProsumerType.COMMERCIAL, sampleLocation, discomId
      );
      await registry.connect(verifier).updateKYCStatus(prosumer2.address, KYCStatus.VERIFIED);

      // Register max EVs for prosumer2
      for (let i = 0; i < MAX_EVS_PER_PROSUMER; i++) {
        await registry.connect(prosumer2).registerEV(
          `VIN_P2_${i}`, sampleBatteryCapacity, sampleMaxDischargeRate, ChargerType.LEVEL2, false
        );
      }

      // Register EV for prosumer1
      await registry.connect(prosumer1).registerEV(
        sampleVIN, sampleBatteryCapacity, sampleMaxDischargeRate, ChargerType.LEVEL2, false
      );

      const vinHash = ethers.keccak256(ethers.toUtf8Bytes(sampleVIN));

      await expect(registry.connect(prosumer1).transferEV(vinHash, prosumer2.address))
        .to.be.revertedWithCustomError(registry, "MaxEVsReached");
    });
  });

  // ============ Prosumer Management Tests ============
  describe("Prosumer Management", function () {
    it("should allow prosumer to update their location", async function () {
      const { registry, prosumer1 } = await loadFixture(deployWithProsumerFixture);

      const newLocation = ethers.keccak256(ethers.toUtf8Bytes("NEW_LOCATION"));

      await expect(registry.connect(prosumer1).updateProsumerLocation(newLocation))
        .to.emit(registry, "ProsumerUpdated");

      const [, , , , encryptedLocation] = await registry.getProsumer(prosumer1.address);
      expect(encryptedLocation).to.equal(newLocation);
    });

    it("should allow assigning prosumer to different DISCOM", async function () {
      const { registry, registrar, discomManager, prosumer1, discomId } =
        await loadFixture(deployWithProsumerFixture);

      // Register another DISCOM
      const tx = await registry.connect(discomManager).registerDISCOM(
        ethers.keccak256(ethers.toUtf8Bytes("LICENSE2")),
        "Gujarat"
      );
      const receipt = await tx.wait();
      const event = receipt?.logs.find((log: any) => log.fragment?.name === "DISCOMRegistered");
      const newDiscomId = (event as any)?.args?.[0];

      await expect(registry.connect(registrar).assignProsumerToDISCOM(prosumer1.address, newDiscomId))
        .to.emit(registry, "ProsumerAssignedToDISCOM")
        .withArgs(prosumer1.address, newDiscomId);

      const [, , , , , assignedDiscom] = await registry.getProsumer(prosumer1.address);
      expect(assignedDiscom).to.equal(newDiscomId);

      // Check DISCOM counts updated
      const [, , , , oldCount] = await registry.getDISCOM(discomId);
      const [, , , , newCount] = await registry.getDISCOM(newDiscomId);
      expect(oldCount).to.equal(0);
      expect(newCount).to.equal(1);
    });

    it("should deactivate and reactivate prosumer", async function () {
      const { registry, registrar, prosumer1 } = await loadFixture(deployWithProsumerFixture);

      await expect(registry.connect(registrar).deactivateProsumer(prosumer1.address))
        .to.emit(registry, "ProsumerDeactivated");

      let [, , , , , , , , isActive] = await registry.getProsumer(prosumer1.address);
      expect(isActive).to.be.false;

      await expect(registry.connect(registrar).reactivateProsumer(prosumer1.address))
        .to.emit(registry, "ProsumerReactivated");

      [, , , , , , , , isActive] = await registry.getProsumer(prosumer1.address);
      expect(isActive).to.be.true;
    });
  });

  // ============ View Functions Tests ============
  describe("View Functions", function () {
    it("should return all prosumers", async function () {
      const { registry, registrar, verifier, prosumer1, prosumer2, discomId } =
        await loadFixture(deployWithDISCOMFixture);

      await registry.connect(registrar).registerProsumer(
        prosumer1.address, sampleKYCHash, ProsumerType.RESIDENTIAL, sampleLocation, discomId
      );
      await registry.connect(registrar).registerProsumer(
        prosumer2.address, sampleKYCHash, ProsumerType.COMMERCIAL, sampleLocation, discomId
      );

      const prosumers = await registry.getAllProsumers();
      expect(prosumers.length).to.equal(2);
      expect(prosumers).to.include(prosumer1.address);
      expect(prosumers).to.include(prosumer2.address);
    });

    it("should return all DISCOMs", async function () {
      const { registry, discomManager, discomId } = await loadFixture(deployWithDISCOMFixture);

      await registry.connect(discomManager).registerDISCOM(
        ethers.keccak256(ethers.toUtf8Bytes("LICENSE2")),
        "Gujarat"
      );

      const discoms = await registry.getAllDISCOMs();
      expect(discoms.length).to.equal(2);
    });

    it("should check if prosumer is verified", async function () {
      const { registry, prosumer1 } = await loadFixture(deployWithProsumerFixture);

      expect(await registry.isVerifiedProsumer(prosumer1.address)).to.be.true;
    });

    it("should return prosumers by type", async function () {
      const { registry, registrar, prosumer1, prosumer2, prosumer3, discomId } =
        await loadFixture(deployWithDISCOMFixture);

      await registry.connect(registrar).registerProsumer(
        prosumer1.address, sampleKYCHash, ProsumerType.RESIDENTIAL, sampleLocation, discomId
      );
      await registry.connect(registrar).registerProsumer(
        prosumer2.address, sampleKYCHash, ProsumerType.RESIDENTIAL, sampleLocation, discomId
      );
      await registry.connect(registrar).registerProsumer(
        prosumer3.address, sampleKYCHash, ProsumerType.COMMERCIAL, sampleLocation, discomId
      );

      const residential = await registry.getProsumersByType(ProsumerType.RESIDENTIAL);
      expect(residential.length).to.equal(2);

      const commercial = await registry.getProsumersByType(ProsumerType.COMMERCIAL);
      expect(commercial.length).to.equal(1);
    });

    it("should count V2G capable EVs", async function () {
      const { registry, registrar, verifier, prosumer1, prosumer2, discomId } =
        await loadFixture(deployWithProsumerFixture);

      // Register and verify prosumer2
      await registry.connect(registrar).registerProsumer(
        prosumer2.address, sampleKYCHash, ProsumerType.COMMERCIAL, sampleLocation, discomId
      );
      await registry.connect(verifier).updateKYCStatus(prosumer2.address, KYCStatus.VERIFIED);

      // Register EVs
      await registry.connect(prosumer1).registerEV("VIN1", sampleBatteryCapacity, sampleMaxDischargeRate, ChargerType.BIDIRECTIONAL, true);
      await registry.connect(prosumer1).registerEV("VIN2", sampleBatteryCapacity, sampleMaxDischargeRate, ChargerType.LEVEL2, false);
      await registry.connect(prosumer2).registerEV("VIN3", sampleBatteryCapacity, sampleMaxDischargeRate, ChargerType.BIDIRECTIONAL, true);

      const v2gCount = await registry.getV2GCapableEVCount();
      expect(v2gCount).to.equal(2);
    });
  });

  // ============ Pausable Tests ============
  describe("Pausable", function () {
    it("should allow admin to pause", async function () {
      const { registry, admin } = await loadFixture(deployFixture);

      await registry.connect(admin).pause();
      expect(await registry.paused()).to.be.true;
    });

    it("should prevent operations when paused", async function () {
      const { registry, admin, registrar, prosumer1, discomId } = await loadFixture(deployWithDISCOMFixture);

      await registry.connect(admin).pause();

      await expect(
        registry.connect(registrar).registerProsumer(
          prosumer1.address, sampleKYCHash, ProsumerType.RESIDENTIAL, sampleLocation, discomId
        )
      ).to.be.revertedWithCustomError(registry, "EnforcedPause");
    });

    it("should allow unpause", async function () {
      const { registry, admin, registrar, prosumer1, discomId } = await loadFixture(deployWithDISCOMFixture);

      await registry.connect(admin).pause();
      await registry.connect(admin).unpause();

      await expect(
        registry.connect(registrar).registerProsumer(
          prosumer1.address, sampleKYCHash, ProsumerType.RESIDENTIAL, sampleLocation, discomId
        )
      ).to.emit(registry, "ProsumerRegistered");
    });
  });

  // ============ Access Control Tests ============
  describe("Access Control", function () {
    it("should allow admin to grant roles", async function () {
      const { registry, admin, unauthorized } = await loadFixture(deployFixture);

      await registry.connect(admin).grantRole(REGISTRAR_ROLE, unauthorized.address);
      expect(await registry.hasRole(REGISTRAR_ROLE, unauthorized.address)).to.be.true;
    });

    it("should allow admin to revoke roles", async function () {
      const { registry, admin, registrar } = await loadFixture(deployFixture);

      await registry.connect(admin).revokeRole(REGISTRAR_ROLE, registrar.address);
      expect(await registry.hasRole(REGISTRAR_ROLE, registrar.address)).to.be.false;
    });
  });

  // Helper function
  async function getBlockTimestamp(): Promise<number> {
    const block = await ethers.provider.getBlock("latest");
    return block?.timestamp || 0;
  }
});
