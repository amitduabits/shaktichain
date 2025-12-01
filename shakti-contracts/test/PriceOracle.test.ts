import { expect } from "chai";
import { ethers } from "hardhat";
import { loadFixture, time } from "@nomicfoundation/hardhat-network-helpers";
import { HardhatEthersSigner } from "@nomicfoundation/hardhat-ethers/signers";
import { PriceOracle, MockAggregatorV3 } from "../typechain-types";

describe("PriceOracle", function () {
  // Constants
  const PRICE_PRECISION = BigInt(1e8);
  const MULTIPLIER_PRECISION = 10000n;
  const MAX_STALENESS = 5 * 60; // 5 minutes

  // Default price bounds (in paise with 8 decimals)
  // Min: 2 INR/kWh = 200 paise = 200 * 1e8
  // Max: 15 INR/kWh = 1500 paise = 1500 * 1e8
  const MIN_PRICE = 200n * PRICE_PRECISION;
  const MAX_PRICE = 1500n * PRICE_PRECISION;

  // Sample price: 5 INR/kWh = 500 paise
  const SAMPLE_PRICE = 500n * PRICE_PRECISION;

  async function deployOracleFixture() {
    const [admin, operator, updater, user] = await ethers.getSigners();

    // Deploy mock price feeds
    const MockAggregator = await ethers.getContractFactory("MockAggregatorV3");
    const primaryFeed = await MockAggregator.deploy(8, "IEX/INR Price", SAMPLE_PRICE);
    const backupFeed = await MockAggregator.deploy(8, "IEX/INR Backup", SAMPLE_PRICE);

    // Deploy PriceOracle
    const PriceOracle = await ethers.getContractFactory("PriceOracle");
    const oracle = await PriceOracle.deploy(
      await primaryFeed.getAddress(),
      await backupFeed.getAddress(),
      admin.address,
      MIN_PRICE,
      MAX_PRICE
    );

    // Grant roles
    const OPERATOR_ROLE = await oracle.OPERATOR_ROLE();
    const PRICE_UPDATER_ROLE = await oracle.PRICE_UPDATER_ROLE();

    await oracle.connect(admin).grantRole(OPERATOR_ROLE, operator.address);
    await oracle.connect(admin).grantRole(PRICE_UPDATER_ROLE, updater.address);

    return { oracle, primaryFeed, backupFeed, admin, operator, updater, user };
  }

  describe("Deployment", function () {
    it("should deploy with correct parameters", async function () {
      const { oracle, primaryFeed, admin } = await loadFixture(deployOracleFixture);

      expect(await oracle.primaryPriceFeed()).to.equal(await primaryFeed.getAddress());
      expect(await oracle.minPrice()).to.equal(MIN_PRICE);
      expect(await oracle.maxPrice()).to.equal(MAX_PRICE);

      const DEFAULT_ADMIN_ROLE = await oracle.DEFAULT_ADMIN_ROLE();
      expect(await oracle.hasRole(DEFAULT_ADMIN_ROLE, admin.address)).to.be.true;
    });

    it("should revert if primary feed is zero address", async function () {
      const [admin] = await ethers.getSigners();
      const PriceOracle = await ethers.getContractFactory("PriceOracle");

      await expect(
        PriceOracle.deploy(
          ethers.ZeroAddress,
          ethers.ZeroAddress,
          admin.address,
          MIN_PRICE,
          MAX_PRICE
        )
      ).to.be.revertedWithCustomError(PriceOracle, "ZeroAddress");
    });

    it("should revert if min >= max price", async function () {
      const [admin] = await ethers.getSigners();
      const MockAggregator = await ethers.getContractFactory("MockAggregatorV3");
      const feed = await MockAggregator.deploy(8, "Test", SAMPLE_PRICE);

      const PriceOracle = await ethers.getContractFactory("PriceOracle");

      await expect(
        PriceOracle.deploy(
          await feed.getAddress(),
          ethers.ZeroAddress,
          admin.address,
          MAX_PRICE,
          MIN_PRICE
        )
      ).to.be.revertedWithCustomError(PriceOracle, "InvalidBounds");
    });

    it("should initialize default hour multipliers", async function () {
      const { oracle } = await loadFixture(deployOracleFixture);

      // Off-peak (0-6): 0.7x = 7000
      expect(await oracle.hourMultipliers(0)).to.equal(7000);
      expect(await oracle.hourMultipliers(5)).to.equal(7000);

      // Standard (6-18): 1.0x = 10000
      expect(await oracle.hourMultipliers(6)).to.equal(10000);
      expect(await oracle.hourMultipliers(12)).to.equal(10000);

      // Peak (18-22): 1.5x = 15000
      expect(await oracle.hourMultipliers(18)).to.equal(15000);
      expect(await oracle.hourMultipliers(21)).to.equal(15000);

      // Evening standard (22-24): 1.0x = 10000
      expect(await oracle.hourMultipliers(22)).to.equal(10000);
      expect(await oracle.hourMultipliers(23)).to.equal(10000);
    });
  });

  describe("Price Fetching", function () {
    it("should get spot price from primary feed", async function () {
      const { oracle, primaryFeed } = await loadFixture(deployOracleFixture);

      const [price, timestamp] = await oracle.getSpotPrice();
      expect(price).to.equal(SAMPLE_PRICE);
    });

    it("should fall back to backup feed if primary fails", async function () {
      const { oracle, primaryFeed, backupFeed } = await loadFixture(deployOracleFixture);

      // Make primary feed revert
      await primaryFeed.setShouldRevert(true);

      // Update backup with different price
      const backupPrice = 600n * PRICE_PRECISION;
      await backupFeed.updateAnswer(backupPrice);

      const [price] = await oracle.getSpotPrice();
      expect(price).to.equal(backupPrice);
    });

    it("should reject stale prices", async function () {
      const { oracle, primaryFeed, backupFeed } = await loadFixture(deployOracleFixture);

      // Make both feeds return stale prices
      await primaryFeed.setStalePrice(true, MAX_STALENESS + 60);
      await backupFeed.setStalePrice(true, MAX_STALENESS + 60);

      // Should fall back to stored/TWAP price
      const [price] = await oracle.getSpotPrice();
      // Will be 0 since no TWAP and no stored price yet
      expect(price).to.equal(0n);
    });

    it("should use manual override when active", async function () {
      const { oracle, admin } = await loadFixture(deployOracleFixture);

      const overridePrice = 700n * PRICE_PRECISION;
      await oracle.connect(admin).setManualOverride(overridePrice, true);

      const [price] = await oracle.getSpotPrice();
      expect(price).to.equal(overridePrice);
    });

    it("should ignore manual override when inactive", async function () {
      const { oracle, admin } = await loadFixture(deployOracleFixture);

      const overridePrice = 700n * PRICE_PRECISION;
      await oracle.connect(admin).setManualOverride(overridePrice, false);

      const [price] = await oracle.getSpotPrice();
      expect(price).to.equal(SAMPLE_PRICE);
    });
  });

  describe("Effective Price with Multipliers", function () {
    it("should apply off-peak multiplier (0.7x)", async function () {
      const { oracle } = await loadFixture(deployOracleFixture);

      // Hour 3 is off-peak (0.7x)
      const effectivePrice = await oracle.getEffectivePrice(3);
      const expectedPrice = (SAMPLE_PRICE * 7000n) / MULTIPLIER_PRECISION;
      expect(effectivePrice).to.equal(expectedPrice);
    });

    it("should apply peak multiplier (1.5x)", async function () {
      const { oracle } = await loadFixture(deployOracleFixture);

      // Hour 20 is peak (1.5x)
      const effectivePrice = await oracle.getEffectivePrice(20);
      const expectedPrice = (SAMPLE_PRICE * 15000n) / MULTIPLIER_PRECISION;
      expect(effectivePrice).to.equal(expectedPrice);
    });

    it("should apply standard multiplier (1.0x)", async function () {
      const { oracle } = await loadFixture(deployOracleFixture);

      // Hour 10 is standard (1.0x)
      const effectivePrice = await oracle.getEffectivePrice(10);
      expect(effectivePrice).to.equal(SAMPLE_PRICE);
    });

    it("should revert for invalid hour", async function () {
      const { oracle } = await loadFixture(deployOracleFixture);

      await expect(oracle.getEffectivePrice(24))
        .to.be.revertedWithCustomError(oracle, "InvalidHour");
    });
  });

  describe("Peak Multiplier", function () {
    it("should return correct multiplier for each hour", async function () {
      const { oracle } = await loadFixture(deployOracleFixture);

      expect(await oracle.getPeakMultiplier(0)).to.equal(7000);
      expect(await oracle.getPeakMultiplier(12)).to.equal(10000);
      expect(await oracle.getPeakMultiplier(19)).to.equal(15000);
      expect(await oracle.getPeakMultiplier(23)).to.equal(10000);
    });
  });

  describe("Price Updates", function () {
    it("should update price from feed", async function () {
      const { oracle, primaryFeed } = await loadFixture(deployOracleFixture);

      const newPrice = 600n * PRICE_PRECISION;
      await primaryFeed.updateAnswer(newPrice);

      await expect(oracle.updatePrice())
        .to.emit(oracle, "PriceUpdated");

      const latestPrice = await oracle.latestPrice();
      expect(latestPrice.price).to.equal(newPrice);
    });

    it("should allow manual price setting by updater", async function () {
      const { oracle, updater } = await loadFixture(deployOracleFixture);

      const newPrice = 800n * PRICE_PRECISION;
      await expect(oracle.connect(updater).setPrice(newPrice))
        .to.emit(oracle, "PriceUpdated");

      const latestPrice = await oracle.latestPrice();
      expect(latestPrice.price).to.equal(newPrice);
    });

    it("should reject price outside bounds", async function () {
      const { oracle, updater } = await loadFixture(deployOracleFixture);

      const tooLow = 100n * PRICE_PRECISION;
      await expect(oracle.connect(updater).setPrice(tooLow))
        .to.be.revertedWithCustomError(oracle, "PriceOutOfBounds");

      const tooHigh = 2000n * PRICE_PRECISION;
      await expect(oracle.connect(updater).setPrice(tooHigh))
        .to.be.revertedWithCustomError(oracle, "PriceOutOfBounds");
    });

    it("should revert if non-updater tries to set price", async function () {
      const { oracle, user } = await loadFixture(deployOracleFixture);

      await expect(oracle.connect(user).setPrice(SAMPLE_PRICE))
        .to.be.reverted;
    });
  });

  describe("TWAP", function () {
    it("should calculate TWAP from hourly prices", async function () {
      const { oracle, updater } = await loadFixture(deployOracleFixture);

      // Record some hourly prices
      const price1 = 400n * PRICE_PRECISION;
      const price2 = 600n * PRICE_PRECISION;

      await oracle.connect(updater).setPrice(price1);
      await oracle.recordHourlyPrice();

      await time.increase(3600); // 1 hour

      await oracle.connect(updater).setPrice(price2);
      await oracle.recordHourlyPrice();

      await oracle.updateTWAP();

      const twap = await oracle.twapPrice();
      expect(twap).to.be.gt(0n);
    });
  });

  describe("Historical Prices", function () {
    it("should record hourly prices", async function () {
      const { oracle, updater } = await loadFixture(deployOracleFixture);

      await oracle.connect(updater).setPrice(SAMPLE_PRICE);
      await oracle.recordHourlyPrice();

      const currentHour = await oracle.getCurrentISTHour();
      const [price, timestamp, sampleCount] = await oracle.getHistoricalPrice(currentHour);

      expect(price).to.equal(SAMPLE_PRICE);
      expect(sampleCount).to.equal(1);
    });

    it("should get 24-hour history", async function () {
      const { oracle } = await loadFixture(deployOracleFixture);

      const [prices, timestamps] = await oracle.get24HourHistory();
      expect(prices.length).to.equal(24);
      expect(timestamps.length).to.equal(24);
    });

    it("should update running average for same hour", async function () {
      const { oracle, updater } = await loadFixture(deployOracleFixture);

      const price1 = 400n * PRICE_PRECISION;
      const price2 = 600n * PRICE_PRECISION;

      await oracle.connect(updater).setPrice(price1);
      await oracle.recordHourlyPrice();

      await oracle.connect(updater).setPrice(price2);
      await oracle.recordHourlyPrice();

      const currentHour = await oracle.getCurrentISTHour();
      const [avgPrice, , sampleCount] = await oracle.getHistoricalPrice(currentHour);

      expect(sampleCount).to.equal(2);
      // Average of 400 and 600 = 500
      expect(avgPrice).to.equal(SAMPLE_PRICE);
    });
  });

  describe("Time Helpers", function () {
    it("should detect peak hours", async function () {
      const { oracle } = await loadFixture(deployOracleFixture);

      // This depends on current block time - may vary
      const isPeak = await oracle.isPeakHour();
      const isOffPeak = await oracle.isOffPeakHour();

      // Can't both be true
      if (isPeak) {
        expect(isOffPeak).to.be.false;
      }
    });

    it("should return valid IST hour", async function () {
      const { oracle } = await loadFixture(deployOracleFixture);

      const hour = await oracle.getCurrentISTHour();
      expect(hour).to.be.lt(24);
      expect(hour).to.be.gte(0);
    });
  });

  describe("Admin Functions", function () {
    it("should update price bounds", async function () {
      const { oracle, operator } = await loadFixture(deployOracleFixture);

      const newMin = 100n * PRICE_PRECISION;
      const newMax = 2000n * PRICE_PRECISION;

      await expect(oracle.connect(operator).setPriceBounds(newMin, newMax))
        .to.emit(oracle, "PriceBoundsUpdated");

      expect(await oracle.minPrice()).to.equal(newMin);
      expect(await oracle.maxPrice()).to.equal(newMax);
    });

    it("should update deviation threshold", async function () {
      const { oracle, operator } = await loadFixture(deployOracleFixture);

      await expect(oracle.connect(operator).setDeviationThreshold(500))
        .to.emit(oracle, "DeviationThresholdUpdated");

      expect(await oracle.deviationThreshold()).to.equal(500);
    });

    it("should set individual hour multiplier", async function () {
      const { oracle, operator } = await loadFixture(deployOracleFixture);

      await expect(oracle.connect(operator).setHourMultiplier(12, 12000))
        .to.emit(oracle, "MultiplierUpdated")
        .withArgs(12, 10000, 12000);

      expect(await oracle.hourMultipliers(12)).to.equal(12000);
    });

    it("should batch set multipliers", async function () {
      const { oracle, operator } = await loadFixture(deployOracleFixture);

      const hours = [6, 7, 8];
      const multipliers = [11000, 11000, 11000];

      await oracle.connect(operator).setBatchMultipliers(hours, multipliers);

      expect(await oracle.hourMultipliers(6)).to.equal(11000);
      expect(await oracle.hourMultipliers(7)).to.equal(11000);
      expect(await oracle.hourMultipliers(8)).to.equal(11000);
    });

    it("should revert batch with mismatched arrays", async function () {
      const { oracle, operator } = await loadFixture(deployOracleFixture);

      await expect(
        oracle.connect(operator).setBatchMultipliers([1, 2], [10000])
      ).to.be.revertedWithCustomError(oracle, "ArrayLengthMismatch");
    });

    it("should update primary price feed", async function () {
      const { oracle, admin } = await loadFixture(deployOracleFixture);

      const MockAggregator = await ethers.getContractFactory("MockAggregatorV3");
      const newFeed = await MockAggregator.deploy(8, "New Feed", SAMPLE_PRICE);

      await expect(oracle.connect(admin).setPrimaryPriceFeed(await newFeed.getAddress()))
        .to.emit(oracle, "PriceFeedUpdated");

      expect(await oracle.primaryPriceFeed()).to.equal(await newFeed.getAddress());
    });

    it("should pause and unpause", async function () {
      const { oracle, admin, updater } = await loadFixture(deployOracleFixture);

      await oracle.connect(admin).pause();

      await expect(oracle.connect(updater).setPrice(SAMPLE_PRICE))
        .to.be.revertedWithCustomError(oracle, "EnforcedPause");

      await oracle.connect(admin).unpause();

      await expect(oracle.connect(updater).setPrice(SAMPLE_PRICE))
        .to.emit(oracle, "PriceUpdated");
    });
  });

  describe("Edge Cases", function () {
    it("should handle zero multiplier as 1.0x", async function () {
      const { oracle, operator } = await loadFixture(deployOracleFixture);

      // Try to set multiplier to 0 - should revert
      await expect(oracle.connect(operator).setHourMultiplier(12, 0))
        .to.be.revertedWithCustomError(oracle, "InvalidMultiplier");
    });

    it("should reject multiplier above 5x", async function () {
      const { oracle, operator } = await loadFixture(deployOracleFixture);

      await expect(oracle.connect(operator).setHourMultiplier(12, 50001))
        .to.be.revertedWithCustomError(oracle, "InvalidMultiplier");
    });

    it("should handle feed returning negative price", async function () {
      const { oracle, primaryFeed, backupFeed } = await loadFixture(deployOracleFixture);

      // Set negative price on both feeds
      await primaryFeed.updateAnswer(-100);
      await backupFeed.updateAnswer(-100);

      // Should reject negative and return 0 or fallback
      const [price] = await oracle.getSpotPrice();
      expect(price).to.equal(0n);
    });

    it("should validate manual override against bounds", async function () {
      const { oracle, admin } = await loadFixture(deployOracleFixture);

      await expect(
        oracle.connect(admin).setManualOverride(100n * PRICE_PRECISION, true)
      ).to.be.revertedWithCustomError(oracle, "PriceOutOfBounds");
    });
  });
});
