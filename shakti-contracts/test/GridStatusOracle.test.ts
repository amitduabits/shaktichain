import { expect } from "chai";
import { ethers } from "hardhat";
import { loadFixture, time } from "@nomicfoundation/hardhat-network-helpers";
import { HardhatEthersSigner } from "@nomicfoundation/hardhat-ethers/signers";
import { GridStatusOracle, MockAggregatorV3 } from "../typechain-types";

describe("GridStatusOracle", function () {
  // Constants
  const TARGET_FREQUENCY = 50000n; // 50.000 Hz
  const PERCENTAGE_PRECISION = 10000n;
  const PEAK_CAPACITY = 50000n; // 50,000 MW

  // Frequency values (in mHz)
  const NORMAL_FREQUENCY = 50000n;
  const UNDER_FREQ_ALERT = 49900n;
  const UNDER_FREQ_CRITICAL = 49500n;
  const OVER_FREQ_ALERT = 50100n;
  const OVER_FREQ_CRITICAL = 50500n;

  // Demand levels
  enum DemandLevel {
    LOW = 0,
    NORMAL = 1,
    HIGH = 2,
    CRITICAL = 3
  }

  // Grid conditions
  enum GridCondition {
    STABLE = 0,
    UNDER_FREQUENCY = 1,
    OVER_FREQUENCY = 2,
    STRESSED = 3,
    EMERGENCY = 4
  }

  async function deployOracleFixture() {
    const [admin, operator, updater, user] = await ethers.getSigners();

    // Deploy mock frequency feed
    const MockAggregator = await ethers.getContractFactory("MockAggregatorV3");
    const frequencyFeed = await MockAggregator.deploy(3, "Grid Frequency mHz", NORMAL_FREQUENCY);

    // Deploy GridStatusOracle
    const GridStatusOracle = await ethers.getContractFactory("GridStatusOracle");
    const oracle = await GridStatusOracle.deploy(
      await frequencyFeed.getAddress(),
      admin.address,
      PEAK_CAPACITY
    );

    // Grant roles
    const OPERATOR_ROLE = await oracle.OPERATOR_ROLE();
    const GRID_UPDATER_ROLE = await oracle.GRID_UPDATER_ROLE();

    await oracle.connect(admin).grantRole(OPERATOR_ROLE, operator.address);
    await oracle.connect(admin).grantRole(GRID_UPDATER_ROLE, updater.address);

    return { oracle, frequencyFeed, admin, operator, updater, user };
  }

  describe("Deployment", function () {
    it("should deploy with correct parameters", async function () {
      const { oracle, frequencyFeed, admin } = await loadFixture(deployOracleFixture);

      expect(await oracle.frequencyFeed()).to.equal(await frequencyFeed.getAddress());
      expect(await oracle.peakCapacity()).to.equal(PEAK_CAPACITY);

      const DEFAULT_ADMIN_ROLE = await oracle.DEFAULT_ADMIN_ROLE();
      expect(await oracle.hasRole(DEFAULT_ADMIN_ROLE, admin.address)).to.be.true;
    });

    it("should revert if admin is zero address", async function () {
      const MockAggregator = await ethers.getContractFactory("MockAggregatorV3");
      const feed = await MockAggregator.deploy(3, "Test", NORMAL_FREQUENCY);

      const GridStatusOracle = await ethers.getContractFactory("GridStatusOracle");

      await expect(
        GridStatusOracle.deploy(
          await feed.getAddress(),
          ethers.ZeroAddress,
          PEAK_CAPACITY
        )
      ).to.be.revertedWithCustomError(GridStatusOracle, "ZeroAddress");
    });

    it("should initialize with default thresholds", async function () {
      const { oracle } = await loadFixture(deployOracleFixture);

      const freqThresholds = await oracle.freqThresholds();
      expect(freqThresholds.underFrequencyAlert).to.equal(49900);
      expect(freqThresholds.underFrequencyCritical).to.equal(49500);
      expect(freqThresholds.overFrequencyAlert).to.equal(50100);
      expect(freqThresholds.overFrequencyCritical).to.equal(50500);

      const demandThresholds = await oracle.demandThresholds();
      expect(demandThresholds.lowThreshold).to.equal(6000);
      expect(demandThresholds.highThreshold).to.equal(8000);
      expect(demandThresholds.criticalThreshold).to.equal(9500);
    });

    it("should initialize with normal status", async function () {
      const { oracle } = await loadFixture(deployOracleFixture);

      const status = await oracle.getFullStatus();
      expect(status.frequency).to.equal(TARGET_FREQUENCY);
      expect(status.demandLevel).to.equal(DemandLevel.NORMAL);
      expect(status.condition).to.equal(GridCondition.STABLE);
    });
  });

  describe("Grid Frequency", function () {
    it("should get frequency from Chainlink feed", async function () {
      const { oracle, frequencyFeed } = await loadFixture(deployOracleFixture);

      const testFreq = 49950n;
      await frequencyFeed.updateAnswer(testFreq);

      const frequency = await oracle.getGridFrequency();
      expect(frequency).to.equal(testFreq);
    });

    it("should fall back to stored value if feed is stale", async function () {
      const { oracle, frequencyFeed, updater } = await loadFixture(deployOracleFixture);

      // Update stored value
      await oracle.connect(updater).updateFrequency(49980);

      // Make feed stale
      await frequencyFeed.setStalePrice(true, 120);

      const frequency = await oracle.getGridFrequency();
      expect(frequency).to.equal(49980);
    });

    it("should calculate frequency deviation", async function () {
      const { oracle, updater } = await loadFixture(deployOracleFixture);

      // Under frequency
      await oracle.connect(updater).updateFrequency(49900);
      let [deviation, isUnder] = await oracle.getFrequencyDeviation();
      expect(deviation).to.equal(100);
      expect(isUnder).to.be.true;

      // Over frequency
      await oracle.connect(updater).updateFrequency(50150);
      [deviation, isUnder] = await oracle.getFrequencyDeviation();
      expect(deviation).to.equal(150);
      expect(isUnder).to.be.false;
    });
  });

  describe("Demand Level", function () {
    it("should classify LOW demand correctly", async function () {
      const { oracle, updater } = await loadFixture(deployOracleFixture);

      await oracle.connect(updater).updateGridStatus(
        NORMAL_FREQUENCY,
        5000, // 50% load factor - LOW
        2000  // 20% renewable
      );

      expect(await oracle.getDemandLevel()).to.equal(DemandLevel.LOW);
    });

    it("should classify NORMAL demand correctly", async function () {
      const { oracle, updater } = await loadFixture(deployOracleFixture);

      await oracle.connect(updater).updateGridStatus(
        NORMAL_FREQUENCY,
        7000, // 70% load factor - NORMAL
        2000
      );

      expect(await oracle.getDemandLevel()).to.equal(DemandLevel.NORMAL);
    });

    it("should classify HIGH demand correctly", async function () {
      const { oracle, updater } = await loadFixture(deployOracleFixture);

      await oracle.connect(updater).updateGridStatus(
        NORMAL_FREQUENCY,
        8500, // 85% load factor - HIGH
        2000
      );

      expect(await oracle.getDemandLevel()).to.equal(DemandLevel.HIGH);
    });

    it("should classify CRITICAL demand correctly", async function () {
      const { oracle, updater } = await loadFixture(deployOracleFixture);

      await oracle.connect(updater).updateGridStatus(
        NORMAL_FREQUENCY,
        9600, // 96% load factor - CRITICAL
        2000
      );

      expect(await oracle.getDemandLevel()).to.equal(DemandLevel.CRITICAL);
    });
  });

  describe("Grid Condition", function () {
    it("should detect STABLE condition", async function () {
      const { oracle, updater } = await loadFixture(deployOracleFixture);

      await oracle.connect(updater).updateGridStatus(
        NORMAL_FREQUENCY,
        7000,
        2000
      );

      expect(await oracle.getGridCondition()).to.equal(GridCondition.STABLE);
      expect(await oracle.isGridStressed()).to.be.false;
    });

    it("should detect UNDER_FREQUENCY condition", async function () {
      const { oracle, updater } = await loadFixture(deployOracleFixture);

      await oracle.connect(updater).updateGridStatus(
        49850, // Below alert threshold
        7000,
        2000
      );

      expect(await oracle.getGridCondition()).to.equal(GridCondition.UNDER_FREQUENCY);
    });

    it("should detect OVER_FREQUENCY condition", async function () {
      const { oracle, updater } = await loadFixture(deployOracleFixture);

      await oracle.connect(updater).updateGridStatus(
        50150, // Above alert threshold
        7000,
        2000
      );

      expect(await oracle.getGridCondition()).to.equal(GridCondition.OVER_FREQUENCY);
    });

    it("should detect STRESSED condition", async function () {
      const { oracle, updater } = await loadFixture(deployOracleFixture);

      await oracle.connect(updater).updateGridStatus(
        49850, // Under-frequency alert
        8500,  // HIGH demand
        2000
      );

      expect(await oracle.getGridCondition()).to.equal(GridCondition.STRESSED);
      expect(await oracle.isGridStressed()).to.be.true;
    });

    it("should detect EMERGENCY condition on critical frequency", async function () {
      const { oracle, updater } = await loadFixture(deployOracleFixture);

      await oracle.connect(updater).updateGridStatus(
        49400, // Below critical threshold
        7000,
        2000
      );

      expect(await oracle.getGridCondition()).to.equal(GridCondition.EMERGENCY);
      expect(await oracle.isGridStressed()).to.be.true;
    });

    it("should detect EMERGENCY on critical demand", async function () {
      const { oracle, updater } = await loadFixture(deployOracleFixture);

      await oracle.connect(updater).updateGridStatus(
        NORMAL_FREQUENCY,
        9600, // CRITICAL demand
        2000
      );

      expect(await oracle.getGridCondition()).to.equal(GridCondition.STRESSED);
    });
  });

  describe("V2G Recommendations", function () {
    it("should recommend V2G during under-frequency", async function () {
      const { oracle, updater } = await loadFixture(deployOracleFixture);

      await oracle.connect(updater).updateGridStatus(
        49850,
        7000,
        2000
      );

      expect(await oracle.isV2GRecommended()).to.be.true;
      expect(await oracle.isChargingRecommended()).to.be.false;
    });

    it("should recommend charging during over-frequency", async function () {
      const { oracle, updater } = await loadFixture(deployOracleFixture);

      await oracle.connect(updater).updateGridStatus(
        50150,
        7000,
        2000
      );

      expect(await oracle.isV2GRecommended()).to.be.false;
      expect(await oracle.isChargingRecommended()).to.be.true;
    });

    it("should recommend charging during low demand", async function () {
      const { oracle, updater } = await loadFixture(deployOracleFixture);

      await oracle.connect(updater).updateGridStatus(
        NORMAL_FREQUENCY,
        5000, // LOW demand
        2000
      );

      expect(await oracle.isChargingRecommended()).to.be.true;
    });

    it("should recommend V2G during critical demand", async function () {
      const { oracle, updater } = await loadFixture(deployOracleFixture);

      await oracle.connect(updater).updateGridStatus(
        NORMAL_FREQUENCY,
        9600, // CRITICAL demand
        2000
      );

      expect(await oracle.isV2GRecommended()).to.be.true;
    });
  });

  describe("V2G Incentive Multiplier", function () {
    it("should return 1.0x for stable grid", async function () {
      const { oracle, updater } = await loadFixture(deployOracleFixture);

      await oracle.connect(updater).updateGridStatus(
        NORMAL_FREQUENCY,
        7000,
        2000
      );

      const multiplier = await oracle.getV2GIncentiveMultiplier();
      expect(multiplier).to.equal(10000); // 1.0x
    });

    it("should return 1.5x for under-frequency", async function () {
      const { oracle, updater } = await loadFixture(deployOracleFixture);

      await oracle.connect(updater).updateGridStatus(
        49850,
        7000,
        2000
      );

      const multiplier = await oracle.getV2GIncentiveMultiplier();
      expect(multiplier).to.equal(15000); // 1.5x
    });

    it("should return 2.0x for stressed grid", async function () {
      const { oracle, updater } = await loadFixture(deployOracleFixture);

      await oracle.connect(updater).updateGridStatus(
        49850,
        8500, // HIGH demand
        2000
      );

      const multiplier = await oracle.getV2GIncentiveMultiplier();
      // 2.0x base, +20% for HIGH = 2.4x = 24000
      expect(multiplier).to.equal(24000);
    });

    it("should return 3.0x+ for emergency", async function () {
      const { oracle, updater } = await loadFixture(deployOracleFixture);

      await oracle.connect(updater).updateGridStatus(
        49400, // EMERGENCY
        9600,  // CRITICAL demand
        2000
      );

      const multiplier = await oracle.getV2GIncentiveMultiplier();
      // 3.0x base, +50% for CRITICAL = 4.5x = 45000
      expect(multiplier).to.equal(45000);
    });
  });

  describe("Renewable Mix", function () {
    it("should update renewable mix", async function () {
      const { oracle, updater } = await loadFixture(deployOracleFixture);

      await oracle.connect(updater).updateRenewableMix(4500); // 45%

      expect(await oracle.getRenewableMix()).to.equal(4500);
    });

    it("should revert if renewable mix exceeds 100%", async function () {
      const { oracle, updater } = await loadFixture(deployOracleFixture);

      await expect(
        oracle.connect(updater).updateRenewableMix(10001)
      ).to.be.revertedWithCustomError(oracle, "InvalidRenewableMix");
    });
  });

  describe("Status Updates", function () {
    it("should update full grid status", async function () {
      const { oracle, updater } = await loadFixture(deployOracleFixture);

      await expect(
        oracle.connect(updater).updateGridStatus(
          49950,
          7500,
          3000
        )
      ).to.emit(oracle, "GridStatusUpdated");

      const status = await oracle.getFullStatus();
      expect(status.frequency).to.equal(49950);
      expect(status.loadFactor).to.equal(7500);
      expect(status.renewableMix).to.equal(3000);
    });

    it("should update frequency quickly", async function () {
      const { oracle, updater } = await loadFixture(deployOracleFixture);

      await oracle.connect(updater).updateFrequency(49920);

      const status = await oracle.getFullStatus();
      expect(status.frequency).to.equal(49920);
    });

    it("should update demand level directly", async function () {
      const { oracle, updater } = await loadFixture(deployOracleFixture);

      await expect(
        oracle.connect(updater).updateDemandLevel(DemandLevel.HIGH)
      ).to.emit(oracle, "DemandLevelChanged");

      expect(await oracle.getDemandLevel()).to.equal(DemandLevel.HIGH);
    });

    it("should revert invalid frequency", async function () {
      const { oracle, updater } = await loadFixture(deployOracleFixture);

      await expect(
        oracle.connect(updater).updateFrequency(46000) // Below min
      ).to.be.revertedWithCustomError(oracle, "InvalidFrequency");

      await expect(
        oracle.connect(updater).updateFrequency(54000) // Above max
      ).to.be.revertedWithCustomError(oracle, "InvalidFrequency");
    });

    it("should revert if non-updater tries to update", async function () {
      const { oracle, user } = await loadFixture(deployOracleFixture);

      await expect(
        oracle.connect(user).updateFrequency(50000)
      ).to.be.reverted;
    });
  });

  describe("Alerts and Events", function () {
    it("should emit frequency alert on under-frequency", async function () {
      const { oracle, updater } = await loadFixture(deployOracleFixture);

      await expect(
        oracle.connect(updater).updateGridStatus(49850, 7000, 2000)
      ).to.emit(oracle, "FrequencyAlert");
    });

    it("should emit frequency alert on over-frequency", async function () {
      const { oracle, updater } = await loadFixture(deployOracleFixture);

      await expect(
        oracle.connect(updater).updateGridStatus(50150, 7000, 2000)
      ).to.emit(oracle, "FrequencyAlert");
    });

    it("should emit grid stress detected", async function () {
      const { oracle, updater } = await loadFixture(deployOracleFixture);

      await expect(
        oracle.connect(updater).updateGridStatus(49850, 8500, 2000)
      ).to.emit(oracle, "GridStressDetected");
    });

    it("should count stress events", async function () {
      const { oracle, updater } = await loadFixture(deployOracleFixture);

      await oracle.connect(updater).updateGridStatus(49850, 8500, 2000);
      expect(await oracle.stressEventCount()).to.equal(1);

      await oracle.connect(updater).updateGridStatus(49400, 8500, 2000);
      expect(await oracle.stressEventCount()).to.equal(2);
    });
  });

  describe("Historical Data", function () {
    it("should record to history", async function () {
      const { oracle, updater } = await loadFixture(deployOracleFixture);

      await oracle.connect(updater).updateGridStatus(49900, 7500, 3500);

      const [frequencies, timestamps, demandLevels] = await oracle.getHourlyHistory();

      // First entry should have data
      expect(frequencies[0]).to.equal(49900);
      expect(demandLevels[0]).to.equal(DemandLevel.NORMAL);
    });

    it("should use circular buffer for history", async function () {
      const { oracle, updater } = await loadFixture(deployOracleFixture);

      // Record multiple entries
      for (let i = 0; i < 5; i++) {
        await oracle.connect(updater).updateGridStatus(
          50000n - BigInt(i * 10),
          7000,
          2000
        );
        await time.increase(60); // 1 minute
      }

      const historyIndex = await oracle.historyIndex();
      expect(historyIndex).to.equal(5);
    });
  });

  describe("Admin Functions", function () {
    it("should set frequency thresholds", async function () {
      const { oracle, operator } = await loadFixture(deployOracleFixture);

      await expect(
        oracle.connect(operator).setFrequencyThresholds(
          49800, 49400, 50200, 50600
        )
      ).to.emit(oracle, "ThresholdsUpdated");

      const thresholds = await oracle.freqThresholds();
      expect(thresholds.underFrequencyAlert).to.equal(49800);
      expect(thresholds.overFrequencyCritical).to.equal(50600);
    });

    it("should set demand thresholds", async function () {
      const { oracle, operator } = await loadFixture(deployOracleFixture);

      await expect(
        oracle.connect(operator).setDemandThresholds(5000, 7500, 9000)
      ).to.emit(oracle, "ThresholdsUpdated");

      const thresholds = await oracle.demandThresholds();
      expect(thresholds.lowThreshold).to.equal(5000);
      expect(thresholds.highThreshold).to.equal(7500);
      expect(thresholds.criticalThreshold).to.equal(9000);
    });

    it("should revert invalid frequency thresholds", async function () {
      const { oracle, operator } = await loadFixture(deployOracleFixture);

      // under_alert must be less than target
      await expect(
        oracle.connect(operator).setFrequencyThresholds(
          50100, 49400, 50200, 50600 // under_alert > target
        )
      ).to.be.revertedWithCustomError(oracle, "InvalidThreshold");
    });

    it("should revert invalid demand thresholds", async function () {
      const { oracle, operator } = await loadFixture(deployOracleFixture);

      // low must be less than high
      await expect(
        oracle.connect(operator).setDemandThresholds(8000, 6000, 9500)
      ).to.be.revertedWithCustomError(oracle, "InvalidThreshold");
    });

    it("should set peak capacity", async function () {
      const { oracle, operator } = await loadFixture(deployOracleFixture);

      await oracle.connect(operator).setPeakCapacity(60000);
      expect(await oracle.peakCapacity()).to.equal(60000);
    });

    it("should set frequency feed", async function () {
      const { oracle, admin } = await loadFixture(deployOracleFixture);

      const MockAggregator = await ethers.getContractFactory("MockAggregatorV3");
      const newFeed = await MockAggregator.deploy(3, "New Feed", NORMAL_FREQUENCY);

      await expect(
        oracle.connect(admin).setFrequencyFeed(await newFeed.getAddress())
      ).to.emit(oracle, "FeedUpdated");

      expect(await oracle.frequencyFeed()).to.equal(await newFeed.getAddress());
    });

    it("should pause and unpause", async function () {
      const { oracle, admin, updater } = await loadFixture(deployOracleFixture);

      await oracle.connect(admin).pause();

      await expect(
        oracle.connect(updater).updateFrequency(50000)
      ).to.be.revertedWithCustomError(oracle, "EnforcedPause");

      await oracle.connect(admin).unpause();

      await oracle.connect(updater).updateFrequency(50000);
      expect((await oracle.getFullStatus()).frequency).to.equal(50000);
    });
  });

  describe("Edge Cases", function () {
    it("should handle boundary frequency values", async function () {
      const { oracle, updater } = await loadFixture(deployOracleFixture);

      // Exactly at alert threshold
      await oracle.connect(updater).updateGridStatus(49900, 7000, 2000);
      expect(await oracle.getGridCondition()).to.equal(GridCondition.UNDER_FREQUENCY);

      // Just above alert threshold
      await oracle.connect(updater).updateGridStatus(49901, 7000, 2000);
      expect(await oracle.getGridCondition()).to.equal(GridCondition.STABLE);
    });

    it("should handle boundary demand values", async function () {
      const { oracle, updater } = await loadFixture(deployOracleFixture);

      // Exactly at high threshold
      await oracle.connect(updater).updateGridStatus(50000, 8000, 2000);
      expect(await oracle.getDemandLevel()).to.equal(DemandLevel.HIGH);

      // Just below high threshold
      await oracle.connect(updater).updateGridStatus(50000, 7999, 2000);
      expect(await oracle.getDemandLevel()).to.equal(DemandLevel.NORMAL);
    });

    it("should not recommend both V2G and charging", async function () {
      const { oracle, updater } = await loadFixture(deployOracleFixture);

      // Various scenarios
      const scenarios = [
        { freq: 49850n, load: 5000n }, // under-freq + low demand
        { freq: 50150n, load: 9600n }, // over-freq + critical demand
      ];

      for (const scenario of scenarios) {
        await oracle.connect(updater).updateGridStatus(
          scenario.freq,
          scenario.load,
          2000
        );

        const v2g = await oracle.isV2GRecommended();
        const charging = await oracle.isChargingRecommended();

        // Should never recommend both
        expect(v2g && charging).to.be.false;
      }
    });

    it("should handle feed returning zero", async function () {
      const { oracle, frequencyFeed, updater } = await loadFixture(deployOracleFixture);

      // Update stored value first
      await oracle.connect(updater).updateFrequency(49980);

      // Set feed to return 0
      await frequencyFeed.updateAnswer(0);

      // Should fall back to stored value
      const frequency = await oracle.getGridFrequency();
      expect(frequency).to.equal(49980);
    });
  });
});
