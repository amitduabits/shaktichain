import { expect } from "chai";
import { ethers } from "hardhat";
import { loadFixture, time } from "@nomicfoundation/hardhat-network-helpers";
import { HardhatEthersSigner } from "@nomicfoundation/hardhat-ethers/signers";
import { DynamicPricing, PriceOracle, GridStatusOracle, MockAggregatorV3 } from "../typechain-types";

describe("DynamicPricing", function () {
  // Constants
  const MULTIPLIER_PRECISION = 10000n;
  const PRICE_PRECISION = BigInt(1e8);

  // Price bounds
  const MIN_PRICE = 200n * PRICE_PRECISION;  // 2 INR/kWh
  const MAX_PRICE = 1500n * PRICE_PRECISION; // 15 INR/kWh
  const SAMPLE_PRICE = 500n * PRICE_PRECISION; // 5 INR/kWh

  // Demand levels
  enum DemandLevel {
    SURPLUS = 0,
    LOW_DEMAND = 1,
    BALANCED = 2,
    MODERATE_HIGH = 3,
    HIGH_DEMAND = 4,
    SURGE = 5
  }

  // Time of use
  enum TimeOfUse {
    OFF_PEAK = 0,
    SHOULDER = 1,
    PEAK = 2
  }

  // Seasons
  enum Season {
    SUMMER = 0,
    MONSOON = 1,
    AUTUMN = 2,
    WINTER = 3
  }

  async function deployDynamicPricingFixture() {
    const [admin, operator, governance, user] = await ethers.getSigners();

    // Deploy mock feeds
    const MockAggregator = await ethers.getContractFactory("MockAggregatorV3");
    const priceFeed = await MockAggregator.deploy(8, "IEX/INR Price", SAMPLE_PRICE);
    const frequencyFeed = await MockAggregator.deploy(3, "Grid Frequency", 50000);

    // Deploy PriceOracle
    const PriceOracle = await ethers.getContractFactory("PriceOracle");
    const priceOracle = await PriceOracle.deploy(
      await priceFeed.getAddress(),
      ethers.ZeroAddress,
      admin.address,
      MIN_PRICE,
      MAX_PRICE
    );

    // Deploy GridStatusOracle
    const GridStatusOracle = await ethers.getContractFactory("GridStatusOracle");
    const gridOracle = await GridStatusOracle.deploy(
      await frequencyFeed.getAddress(),
      admin.address,
      50000
    );

    // Deploy DynamicPricing
    const DynamicPricing = await ethers.getContractFactory("DynamicPricing");
    const dynamicPricing = await DynamicPricing.deploy(
      await priceOracle.getAddress(),
      await gridOracle.getAddress(),
      admin.address
    );

    // Grant roles
    const OPERATOR_ROLE = await dynamicPricing.OPERATOR_ROLE();
    const GOVERNANCE_ROLE = await dynamicPricing.GOVERNANCE_ROLE();
    const GRID_UPDATER_ROLE = await gridOracle.GRID_UPDATER_ROLE();

    await dynamicPricing.connect(admin).grantRole(OPERATOR_ROLE, operator.address);
    await dynamicPricing.connect(admin).grantRole(GOVERNANCE_ROLE, governance.address);
    await gridOracle.connect(admin).grantRole(GRID_UPDATER_ROLE, admin.address);

    return {
      dynamicPricing,
      priceOracle,
      gridOracle,
      priceFeed,
      frequencyFeed,
      admin,
      operator,
      governance,
      user
    };
  }

  describe("Deployment", function () {
    it("should deploy with correct parameters", async function () {
      const { dynamicPricing, priceOracle, gridOracle, admin } = await loadFixture(deployDynamicPricingFixture);

      expect(await dynamicPricing.priceOracle()).to.equal(await priceOracle.getAddress());
      expect(await dynamicPricing.gridOracle()).to.equal(await gridOracle.getAddress());

      const DEFAULT_ADMIN_ROLE = await dynamicPricing.DEFAULT_ADMIN_ROLE();
      expect(await dynamicPricing.hasRole(DEFAULT_ADMIN_ROLE, admin.address)).to.be.true;
    });

    it("should revert if price oracle is zero address", async function () {
      const [admin] = await ethers.getSigners();
      const MockAggregator = await ethers.getContractFactory("MockAggregatorV3");
      const frequencyFeed = await MockAggregator.deploy(3, "Test", 50000);

      const GridStatusOracle = await ethers.getContractFactory("GridStatusOracle");
      const gridOracle = await GridStatusOracle.deploy(
        await frequencyFeed.getAddress(),
        admin.address,
        50000
      );

      const DynamicPricing = await ethers.getContractFactory("DynamicPricing");

      await expect(
        DynamicPricing.deploy(
          ethers.ZeroAddress,
          await gridOracle.getAddress(),
          admin.address
        )
      ).to.be.revertedWithCustomError(DynamicPricing, "ZeroAddress");
    });

    it("should initialize default multipliers", async function () {
      const { dynamicPricing } = await loadFixture(deployDynamicPricingFixture);

      // Demand multipliers
      expect(await dynamicPricing.demandMultipliers(DemandLevel.SURPLUS)).to.equal(7000);
      expect(await dynamicPricing.demandMultipliers(DemandLevel.BALANCED)).to.equal(10000);
      expect(await dynamicPricing.demandMultipliers(DemandLevel.SURGE)).to.equal(15000);

      // Time-of-use multipliers
      expect(await dynamicPricing.timeOfUseMultipliers(TimeOfUse.OFF_PEAK)).to.equal(8000);
      expect(await dynamicPricing.timeOfUseMultipliers(TimeOfUse.SHOULDER)).to.equal(11000);
      expect(await dynamicPricing.timeOfUseMultipliers(TimeOfUse.PEAK)).to.equal(13000);

      // Seasonal multipliers
      expect(await dynamicPricing.seasonalMultipliers(Season.SUMMER)).to.equal(11500);
      expect(await dynamicPricing.seasonalMultipliers(Season.MONSOON)).to.equal(9500);
      expect(await dynamicPricing.seasonalMultipliers(Season.WINTER)).to.equal(10500);
    });
  });

  describe("Demand-Based Pricing", function () {
    it("should classify SURPLUS demand correctly", async function () {
      const { dynamicPricing } = await loadFixture(deployDynamicPricingFixture);

      // Ratio < 0.5 (5000 basis points)
      const level = await dynamicPricing.getDemandLevel(4000);
      expect(level).to.equal(DemandLevel.SURPLUS);
    });

    it("should classify LOW_DEMAND correctly", async function () {
      const { dynamicPricing } = await loadFixture(deployDynamicPricingFixture);

      // Ratio 0.5 - 0.8
      const level = await dynamicPricing.getDemandLevel(6000);
      expect(level).to.equal(DemandLevel.LOW_DEMAND);
    });

    it("should classify BALANCED correctly", async function () {
      const { dynamicPricing } = await loadFixture(deployDynamicPricingFixture);

      // Ratio 0.8 - 1.2
      const level = await dynamicPricing.getDemandLevel(10000);
      expect(level).to.equal(DemandLevel.BALANCED);
    });

    it("should classify MODERATE_HIGH correctly", async function () {
      const { dynamicPricing } = await loadFixture(deployDynamicPricingFixture);

      // Ratio 1.2 - 1.5
      const level = await dynamicPricing.getDemandLevel(13000);
      expect(level).to.equal(DemandLevel.MODERATE_HIGH);
    });

    it("should classify HIGH_DEMAND correctly", async function () {
      const { dynamicPricing } = await loadFixture(deployDynamicPricingFixture);

      // Ratio 1.5 - 2.0
      const level = await dynamicPricing.getDemandLevel(17000);
      expect(level).to.equal(DemandLevel.HIGH_DEMAND);
    });

    it("should classify SURGE correctly", async function () {
      const { dynamicPricing } = await loadFixture(deployDynamicPricingFixture);

      // Ratio > 2.0
      const level = await dynamicPricing.getDemandLevel(25000);
      expect(level).to.equal(DemandLevel.SURGE);
    });

    it("should return correct demand multiplier", async function () {
      const { dynamicPricing } = await loadFixture(deployDynamicPricingFixture);

      // Surplus: 0.7x
      expect(await dynamicPricing.getDemandMultiplier(3000)).to.equal(7000);

      // Balanced: 1.0x
      expect(await dynamicPricing.getDemandMultiplier(10000)).to.equal(10000);

      // Surge: 1.5x
      expect(await dynamicPricing.getDemandMultiplier(25000)).to.equal(15000);
    });
  });

  describe("Time-of-Use Pricing", function () {
    it("should classify OFF_PEAK hours correctly", async function () {
      const { dynamicPricing } = await loadFixture(deployDynamicPricingFixture);

      // 22:00 - 06:00
      expect(await dynamicPricing.getTimeOfUsePeriod(0)).to.equal(TimeOfUse.OFF_PEAK);
      expect(await dynamicPricing.getTimeOfUsePeriod(3)).to.equal(TimeOfUse.OFF_PEAK);
      expect(await dynamicPricing.getTimeOfUsePeriod(5)).to.equal(TimeOfUse.OFF_PEAK);
      expect(await dynamicPricing.getTimeOfUsePeriod(22)).to.equal(TimeOfUse.OFF_PEAK);
      expect(await dynamicPricing.getTimeOfUsePeriod(23)).to.equal(TimeOfUse.OFF_PEAK);
    });

    it("should classify SHOULDER hours correctly", async function () {
      const { dynamicPricing } = await loadFixture(deployDynamicPricingFixture);

      // 06:00 - 10:00, 14:00 - 18:00
      expect(await dynamicPricing.getTimeOfUsePeriod(6)).to.equal(TimeOfUse.SHOULDER);
      expect(await dynamicPricing.getTimeOfUsePeriod(9)).to.equal(TimeOfUse.SHOULDER);
      expect(await dynamicPricing.getTimeOfUsePeriod(14)).to.equal(TimeOfUse.SHOULDER);
      expect(await dynamicPricing.getTimeOfUsePeriod(17)).to.equal(TimeOfUse.SHOULDER);
    });

    it("should classify PEAK hours correctly", async function () {
      const { dynamicPricing } = await loadFixture(deployDynamicPricingFixture);

      // 18:00 - 22:00
      expect(await dynamicPricing.getTimeOfUsePeriod(18)).to.equal(TimeOfUse.PEAK);
      expect(await dynamicPricing.getTimeOfUsePeriod(20)).to.equal(TimeOfUse.PEAK);
      expect(await dynamicPricing.getTimeOfUsePeriod(21)).to.equal(TimeOfUse.PEAK);
    });

    it("should return correct TOU multiplier", async function () {
      const { dynamicPricing } = await loadFixture(deployDynamicPricingFixture);

      // Off-peak: 0.8x (-20%)
      expect(await dynamicPricing.getTimeOfUseMultiplier(3)).to.equal(8000);

      // Shoulder: 1.1x (+10%)
      expect(await dynamicPricing.getTimeOfUseMultiplier(8)).to.equal(11000);

      // Peak: 1.3x (+30%)
      expect(await dynamicPricing.getTimeOfUseMultiplier(20)).to.equal(13000);
    });
  });

  describe("Grid Stress Pricing", function () {
    it("should apply under-frequency multiplier", async function () {
      const { dynamicPricing, frequencyFeed } = await loadFixture(deployDynamicPricingFixture);

      // Set grid to under-frequency via mock feed
      await frequencyFeed.updateAnswer(49400); // Below 49.5 Hz

      const [multiplier, isStressed] = await dynamicPricing.getGridStressMultiplier();
      expect(multiplier).to.equal(15000); // +50%
      expect(isStressed).to.be.true;
    });

    it("should apply over-frequency multiplier", async function () {
      const { dynamicPricing, frequencyFeed } = await loadFixture(deployDynamicPricingFixture);

      // Set grid to over-frequency via mock feed
      await frequencyFeed.updateAnswer(50600); // Above 50.5 Hz

      const [multiplier, isStressed] = await dynamicPricing.getGridStressMultiplier();
      expect(multiplier).to.equal(7000); // -30%
      expect(isStressed).to.be.true;
    });

    it("should return neutral multiplier for normal frequency", async function () {
      const { dynamicPricing, frequencyFeed } = await loadFixture(deployDynamicPricingFixture);

      // Set grid to normal frequency
      await frequencyFeed.updateAnswer(50000);

      const [multiplier, isStressed] = await dynamicPricing.getGridStressMultiplier();
      expect(multiplier).to.equal(10000); // 1.0x
      expect(isStressed).to.be.false;
    });
  });

  describe("Seasonal Pricing", function () {
    it("should return summer multiplier", async function () {
      const { dynamicPricing } = await loadFixture(deployDynamicPricingFixture);

      expect(await dynamicPricing.getSeasonalMultiplier(Season.SUMMER)).to.equal(11500); // +15%
    });

    it("should return monsoon multiplier", async function () {
      const { dynamicPricing } = await loadFixture(deployDynamicPricingFixture);

      expect(await dynamicPricing.getSeasonalMultiplier(Season.MONSOON)).to.equal(9500); // -5%
    });

    it("should return winter multiplier", async function () {
      const { dynamicPricing } = await loadFixture(deployDynamicPricingFixture);

      expect(await dynamicPricing.getSeasonalMultiplier(Season.WINTER)).to.equal(10500); // +5%
    });

    it("should allow manual season override", async function () {
      const { dynamicPricing, operator } = await loadFixture(deployDynamicPricingFixture);

      await dynamicPricing.connect(operator).setCurrentSeason(Season.SUMMER);

      expect(await dynamicPricing.currentSeason()).to.equal(Season.SUMMER);
      expect(await dynamicPricing.autoSeasonDetection()).to.be.false;
    });

    it("should re-enable auto season detection", async function () {
      const { dynamicPricing, operator } = await loadFixture(deployDynamicPricingFixture);

      await dynamicPricing.connect(operator).setCurrentSeason(Season.SUMMER);
      await dynamicPricing.connect(operator).enableAutoSeasonDetection();

      expect(await dynamicPricing.autoSeasonDetection()).to.be.true;
    });
  });

  describe("Dynamic Price Calculation", function () {
    it("should calculate dynamic price with all factors", async function () {
      const { dynamicPricing } = await loadFixture(deployDynamicPricingFixture);

      // Base price: 500 paise (5 INR)
      // Hour: 20 (peak) -> 1.3x
      // Demand ratio: 10000 (balanced) -> 1.0x
      // Grid: normal -> 1.0x
      // Season: depends on current date

      const finalPrice = await dynamicPricing.calculateDynamicPrice(
        SAMPLE_PRICE,
        20,      // Peak hour
        10000    // Balanced demand
      );

      // Price should be modified by multipliers
      expect(finalPrice).to.be.gt(0);
      expect(finalPrice).to.be.gte(MIN_PRICE);
      expect(finalPrice).to.be.lte(MAX_PRICE);
    });

    it("should return price breakdown", async function () {
      const { dynamicPricing } = await loadFixture(deployDynamicPricingFixture);

      const components = await dynamicPricing.getPriceBreakdown(
        SAMPLE_PRICE,
        20,     // Peak
        14000   // Moderate high demand (1.2 - 1.5 range)
      );

      expect(components.basePrice).to.equal(SAMPLE_PRICE);
      expect(components.demandMultiplier).to.equal(11500); // 1.15x for moderate high
      expect(components.timeOfUseMultiplier).to.equal(13000); // 1.3x for peak
      expect(components.gridStressMultiplier).to.equal(10000); // 1.0x normal grid
      expect(components.finalPrice).to.be.gt(0);
    });

    it("should apply surplus discount correctly", async function () {
      const { dynamicPricing } = await loadFixture(deployDynamicPricingFixture);

      // Surplus demand (ratio < 0.5) should apply 0.7x
      const surplusPrice = await dynamicPricing.calculateDynamicPrice(
        SAMPLE_PRICE,
        10,    // Standard hour (shoulder)
        3000   // Surplus demand
      );

      const balancedPrice = await dynamicPricing.calculateDynamicPrice(
        SAMPLE_PRICE,
        10,
        10000  // Balanced demand
      );

      // Surplus should be lower than balanced
      expect(surplusPrice).to.be.lt(balancedPrice);
    });

    it("should apply surge pricing correctly", async function () {
      const { dynamicPricing } = await loadFixture(deployDynamicPricingFixture);

      // Surge demand (ratio > 2.0) should apply 1.5x
      const surgePrice = await dynamicPricing.calculateDynamicPrice(
        SAMPLE_PRICE,
        10,
        25000  // Surge demand
      );

      const balancedPrice = await dynamicPricing.calculateDynamicPrice(
        SAMPLE_PRICE,
        10,
        10000  // Balanced demand
      );

      // Surge should be higher than balanced
      expect(surgePrice).to.be.gt(balancedPrice);
    });

    it("should revert for invalid hour", async function () {
      const { dynamicPricing } = await loadFixture(deployDynamicPricingFixture);

      await expect(
        dynamicPricing.calculateDynamicPrice(SAMPLE_PRICE, 24, 10000)
      ).to.be.revertedWithCustomError(dynamicPricing, "InvalidHour");
    });
  });

  describe("Price Bounds", function () {
    it("should return correct price bounds", async function () {
      const { dynamicPricing } = await loadFixture(deployDynamicPricingFixture);

      const [min, max, dailyMin, dailyMax] = await dynamicPricing.getPriceBounds();

      expect(min).to.equal(MIN_PRICE);
      expect(max).to.equal(MAX_PRICE);
    });

    it("should enforce absolute minimum price", async function () {
      const { dynamicPricing } = await loadFixture(deployDynamicPricingFixture);

      // Very low base price with surplus demand and off-peak
      const price = await dynamicPricing.calculateDynamicPrice(
        100n * PRICE_PRECISION, // 1 INR base
        3,      // Off-peak
        3000    // Surplus
      );

      // Should be clamped to minimum
      expect(price).to.be.gte(MIN_PRICE);
    });

    it("should enforce absolute maximum price", async function () {
      const { dynamicPricing, gridOracle, admin } = await loadFixture(deployDynamicPricingFixture);

      // Set under-frequency for additional multiplier
      await gridOracle.connect(admin).updateFrequency(49400);

      // Very high base price with surge demand and peak hour
      const price = await dynamicPricing.calculateDynamicPrice(
        1000n * PRICE_PRECISION, // 10 INR base
        20,     // Peak
        30000   // Surge
      );

      // Should be clamped to maximum
      expect(price).to.be.lte(MAX_PRICE);
    });

    it("should validate prices correctly", async function () {
      const { dynamicPricing } = await loadFixture(deployDynamicPricingFixture);

      // Valid price
      let [valid, reason] = await dynamicPricing.validatePrice(SAMPLE_PRICE);
      expect(valid).to.be.true;

      // Below minimum
      [valid, reason] = await dynamicPricing.validatePrice(100n * PRICE_PRECISION);
      expect(valid).to.be.false;
      expect(reason).to.equal("Below minimum price");

      // Above maximum
      [valid, reason] = await dynamicPricing.validatePrice(2000n * PRICE_PRECISION);
      expect(valid).to.be.false;
      expect(reason).to.equal("Above maximum price");
    });
  });

  describe("Daily Price Limits", function () {
    it("should track daily price data", async function () {
      const { dynamicPricing, operator } = await loadFixture(deployDynamicPricingFixture);

      await dynamicPricing.connect(operator).resetDailyPrice();

      const dailyData = await dynamicPricing.dailyPrice();
      expect(dailyData.openingPrice).to.equal(SAMPLE_PRICE);
      expect(dailyData.updateCount).to.equal(1);
    });

    it("should enforce daily change limits", async function () {
      const { dynamicPricing, operator } = await loadFixture(deployDynamicPricingFixture);

      // Reset daily price
      await dynamicPricing.connect(operator).resetDailyPrice();

      // Get bounds
      const [, , dailyMin, dailyMax] = await dynamicPricing.getPriceBounds();

      // Daily limits should be ±20% of opening price
      const expectedChange = (SAMPLE_PRICE * 2000n) / MULTIPLIER_PRECISION;

      expect(dailyMax).to.be.lte(SAMPLE_PRICE + expectedChange);
      expect(dailyMin).to.be.gte(SAMPLE_PRICE > expectedChange ? SAMPLE_PRICE - expectedChange : MIN_PRICE);
    });
  });

  describe("Update Functions", function () {
    it("should update and cache price", async function () {
      const { dynamicPricing, operator } = await loadFixture(deployDynamicPricingFixture);

      await dynamicPricing.connect(operator).resetDailyPrice();
      await dynamicPricing.updateCachedPrice();

      expect(await dynamicPricing.lastCalculatedPrice()).to.be.gt(0);
      expect(await dynamicPricing.lastCalculationTime()).to.be.gt(0);
    });

    it("should emit event on price calculation", async function () {
      const { dynamicPricing, operator } = await loadFixture(deployDynamicPricingFixture);

      await dynamicPricing.connect(operator).resetDailyPrice();

      await expect(dynamicPricing.updateCachedPrice())
        .to.emit(dynamicPricing, "DynamicPriceCalculated");
    });
  });

  describe("Admin Functions", function () {
    it("should update demand multiplier", async function () {
      const { dynamicPricing, governance } = await loadFixture(deployDynamicPricingFixture);

      await expect(
        dynamicPricing.connect(governance).setDemandMultiplier(DemandLevel.SURGE, 16000)
      ).to.emit(dynamicPricing, "DemandMultiplierUpdated")
        .withArgs(DemandLevel.SURGE, 15000, 16000);

      expect(await dynamicPricing.demandMultipliers(DemandLevel.SURGE)).to.equal(16000);
    });

    it("should update time-of-use multiplier", async function () {
      const { dynamicPricing, governance } = await loadFixture(deployDynamicPricingFixture);

      await expect(
        dynamicPricing.connect(governance).setTimeOfUseMultiplier(TimeOfUse.PEAK, 14000)
      ).to.emit(dynamicPricing, "TimeOfUseMultiplierUpdated");

      expect(await dynamicPricing.timeOfUseMultipliers(TimeOfUse.PEAK)).to.equal(14000);
    });

    it("should update seasonal multiplier (governance)", async function () {
      const { dynamicPricing, governance } = await loadFixture(deployDynamicPricingFixture);

      await expect(
        dynamicPricing.connect(governance).updateSeasonalMultiplier(Season.SUMMER, 12000)
      ).to.emit(dynamicPricing, "SeasonalMultiplierUpdated");

      expect(await dynamicPricing.seasonalMultipliers(Season.SUMMER)).to.equal(12000);
    });

    it("should update grid stress multipliers", async function () {
      const { dynamicPricing, governance } = await loadFixture(deployDynamicPricingFixture);

      await dynamicPricing.connect(governance).setGridStressMultipliers(16000, 6000);

      expect(await dynamicPricing.underFrequencyMultiplier()).to.equal(16000);
      expect(await dynamicPricing.overFrequencyMultiplier()).to.equal(6000);
    });

    it("should update max daily change", async function () {
      const { dynamicPricing, governance } = await loadFixture(deployDynamicPricingFixture);

      await expect(
        dynamicPricing.connect(governance).setMaxDailyChange(3000)
      ).to.emit(dynamicPricing, "MaxDailyChangeUpdated");

      expect(await dynamicPricing.maxDailyChange()).to.equal(3000);
    });

    it("should update demand thresholds", async function () {
      const { dynamicPricing, governance } = await loadFixture(deployDynamicPricingFixture);

      await dynamicPricing.connect(governance).setDemandThresholds(
        4000,  // surplus
        7000,  // low demand
        11000, // balanced upper
        14000, // moderate high
        18000  // high demand
      );

      const thresholds = await dynamicPricing.demandThresholds();
      expect(thresholds.surplusThreshold).to.equal(4000);
      expect(thresholds.highDemandThreshold).to.equal(18000);
    });

    it("should revert invalid multipliers", async function () {
      const { dynamicPricing, governance } = await loadFixture(deployDynamicPricingFixture);

      // Too low
      await expect(
        dynamicPricing.connect(governance).setDemandMultiplier(DemandLevel.BALANCED, 4000)
      ).to.be.revertedWithCustomError(dynamicPricing, "InvalidMultiplier");

      // Too high
      await expect(
        dynamicPricing.connect(governance).setDemandMultiplier(DemandLevel.BALANCED, 25000)
      ).to.be.revertedWithCustomError(dynamicPricing, "InvalidMultiplier");
    });

    it("should update oracles", async function () {
      const { dynamicPricing, admin, priceOracle } = await loadFixture(deployDynamicPricingFixture);

      // Deploy new oracle
      const MockAggregator = await ethers.getContractFactory("MockAggregatorV3");
      const newFeed = await MockAggregator.deploy(8, "New", SAMPLE_PRICE);

      const PriceOracle = await ethers.getContractFactory("PriceOracle");
      const newPriceOracle = await PriceOracle.deploy(
        await newFeed.getAddress(),
        ethers.ZeroAddress,
        admin.address,
        MIN_PRICE,
        MAX_PRICE
      );

      await expect(
        dynamicPricing.connect(admin).setPriceOracle(await newPriceOracle.getAddress())
      ).to.emit(dynamicPricing, "OracleUpdated");

      expect(await dynamicPricing.priceOracle()).to.equal(await newPriceOracle.getAddress());
    });

    it("should pause and unpause", async function () {
      const { dynamicPricing, admin } = await loadFixture(deployDynamicPricingFixture);

      await dynamicPricing.connect(admin).pause();

      await expect(dynamicPricing.updateCachedPrice())
        .to.be.revertedWithCustomError(dynamicPricing, "EnforcedPause");

      await dynamicPricing.connect(admin).unpause();

      await dynamicPricing.updateCachedPrice();
    });
  });

  describe("Integration Scenarios", function () {
    it("should handle peak demand during peak hours", async function () {
      const { dynamicPricing, frequencyFeed } = await loadFixture(deployDynamicPricingFixture);

      // Set grid to under-frequency (high demand response needed)
      await frequencyFeed.updateAnswer(49400);

      // Peak hour (20:00) + Surge demand + Under-frequency
      const price = await dynamicPricing.calculateDynamicPrice(
        SAMPLE_PRICE,
        20,     // Peak hour
        25000   // Surge demand
      );

      // Should be significantly higher than base
      expect(price).to.be.gt(SAMPLE_PRICE);

      // Get breakdown
      const components = await dynamicPricing.getPriceBreakdown(
        SAMPLE_PRICE,
        20,
        25000
      );

      expect(components.demandMultiplier).to.equal(15000);      // Surge
      expect(components.timeOfUseMultiplier).to.equal(13000);   // Peak
      expect(components.gridStressMultiplier).to.equal(15000);  // Under-freq
    });

    it("should handle low demand during off-peak hours", async function () {
      const { dynamicPricing, frequencyFeed } = await loadFixture(deployDynamicPricingFixture);

      // Set grid to over-frequency (excess supply)
      await frequencyFeed.updateAnswer(50600);

      // Off-peak hour (3:00) + Surplus demand + Over-frequency
      const price = await dynamicPricing.calculateDynamicPrice(
        SAMPLE_PRICE,
        3,      // Off-peak hour
        3000    // Surplus demand
      );

      // Should be lower than base
      expect(price).to.be.lt(SAMPLE_PRICE);

      // Get breakdown
      const components = await dynamicPricing.getPriceBreakdown(
        SAMPLE_PRICE,
        3,
        3000
      );

      expect(components.demandMultiplier).to.equal(7000);       // Surplus
      expect(components.timeOfUseMultiplier).to.equal(8000);    // Off-peak
      expect(components.gridStressMultiplier).to.equal(7000);   // Over-freq
    });

    it("should calculate current dynamic price", async function () {
      const { dynamicPricing } = await loadFixture(deployDynamicPricingFixture);

      const [finalPrice, components] = await dynamicPricing.calculateCurrentDynamicPrice();

      expect(finalPrice).to.be.gt(0);
      expect(components.basePrice).to.equal(SAMPLE_PRICE);
      expect(components.finalPrice).to.equal(finalPrice);
    });
  });

  describe("Edge Cases", function () {
    it("should handle zero demand ratio gracefully", async function () {
      const { dynamicPricing } = await loadFixture(deployDynamicPricingFixture);

      // Zero ratio should classify as SURPLUS
      const level = await dynamicPricing.getDemandLevel(0);
      expect(level).to.equal(DemandLevel.SURPLUS);

      const price = await dynamicPricing.calculateDynamicPrice(
        SAMPLE_PRICE,
        12,
        0
      );
      expect(price).to.be.gt(0);
    });

    it("should handle extremely high demand ratio", async function () {
      const { dynamicPricing } = await loadFixture(deployDynamicPricingFixture);

      // Very high ratio should classify as SURGE
      const level = await dynamicPricing.getDemandLevel(100000);
      expect(level).to.equal(DemandLevel.SURGE);
    });

    it("should handle boundary demand ratios", async function () {
      const { dynamicPricing } = await loadFixture(deployDynamicPricingFixture);

      // Exactly at threshold
      expect(await dynamicPricing.getDemandLevel(5000)).to.equal(DemandLevel.LOW_DEMAND);
      expect(await dynamicPricing.getDemandLevel(8000)).to.equal(DemandLevel.BALANCED);
      expect(await dynamicPricing.getDemandLevel(12000)).to.equal(DemandLevel.MODERATE_HIGH);
    });

    it("should handle boundary hours", async function () {
      const { dynamicPricing } = await loadFixture(deployDynamicPricingFixture);

      // Boundary hours
      expect(await dynamicPricing.getTimeOfUsePeriod(6)).to.equal(TimeOfUse.SHOULDER);  // Start of shoulder
      expect(await dynamicPricing.getTimeOfUsePeriod(10)).to.equal(TimeOfUse.OFF_PEAK); // After morning shoulder
      expect(await dynamicPricing.getTimeOfUsePeriod(18)).to.equal(TimeOfUse.PEAK);     // Start of peak
      expect(await dynamicPricing.getTimeOfUsePeriod(22)).to.equal(TimeOfUse.OFF_PEAK); // End of peak
    });
  });
});
