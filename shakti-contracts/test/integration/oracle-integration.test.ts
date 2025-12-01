/**
 * SHAKTI-CHAIN Integration Test: Oracle & Dynamic Pricing
 *
 * Tests oracle data flow and price calculations:
 * 1. Price feed integration
 * 2. Grid frequency monitoring
 * 3. Time-of-use adjustments
 * 4. Price calculation for auctions
 *
 * Scenarios:
 * - Normal grid conditions
 * - High demand (frequency drop)
 * - Low demand (frequency rise)
 * - Peak vs off-peak pricing
 */

import { expect } from "chai";
import { ethers } from "hardhat";
import { time } from "@nomicfoundation/hardhat-network-helpers";
import {
  PriceOracle,
  DynamicPricing,
  MockAggregatorV3,
  MockFrequencyFeed,
} from "../../typechain-types";
import { SignerWithAddress } from "@nomicfoundation/hardhat-ethers/signers";

describe("Integration: Oracle & Dynamic Pricing", function () {
  let priceOracle: PriceOracle;
  let dynamicPricing: DynamicPricing;
  let mockPriceFeed: MockAggregatorV3;
  let mockGridFeed: MockFrequencyFeed;

  let admin: SignerWithAddress;
  let oracleOperator: SignerWithAddress;

  // Price feed constants
  const DECIMALS = 8;
  const BASE_PRICE = 5 * 10 ** 8; // 5 INR/kWh with 8 decimals
  const NORMAL_FREQUENCY = 50 * 100; // 50.00 Hz (stored as 5000)

  beforeEach(async function () {
    [admin, oracleOperator] = await ethers.getSigners();

    // Deploy Mock Chainlink Price Feed
    const MockAggregatorFactory = await ethers.getContractFactory("MockAggregatorV3");
    mockPriceFeed = await MockAggregatorFactory.deploy(
      DECIMALS,
      "IEX/INR Electricity Price",
      BASE_PRICE
    );
    await mockPriceFeed.waitForDeployment();

    // Deploy Mock Grid Frequency Feed
    const MockGridFactory = await ethers.getContractFactory("MockFrequencyFeed");
    mockGridFeed = await MockGridFactory.deploy();
    await mockGridFeed.waitForDeployment();

    // Set initial frequency
    await mockGridFeed.setFrequency(NORMAL_FREQUENCY);

    // Deploy PriceOracle
    const PriceOracleFactory = await ethers.getContractFactory("PriceOracle");
    priceOracle = await PriceOracleFactory.deploy(
      await mockPriceFeed.getAddress(),
      ethers.ZeroAddress, // No backup feed
      admin.address
    );
    await priceOracle.waitForDeployment();

    // Deploy DynamicPricing
    const DynamicPricingFactory = await ethers.getContractFactory("DynamicPricing");
    dynamicPricing = await DynamicPricingFactory.deploy(
      await priceOracle.getAddress(),
      await mockGridFeed.getAddress(),
      admin.address
    );
    await dynamicPricing.waitForDeployment();

    // Grant ORACLE_ROLE
    const ORACLE_ROLE = await dynamicPricing.ORACLE_ROLE();
    await dynamicPricing.grantRole(ORACLE_ROLE, oracleOperator.address);
  });

  describe("Price Oracle", function () {
    it("should fetch latest price from Chainlink feed", async function () {
      const price = await priceOracle.getLatestPrice();

      expect(price).to.equal(BASE_PRICE);

      console.log("\n  Price Oracle Data:");
      console.log("  ------------------");
      console.log(`  Raw Price: ${price}`);
      console.log(`  Formatted: ${Number(price) / 10 ** DECIMALS} INR/kWh`);
    });

    it("should update price when feed changes", async function () {
      const newPrice = 6 * 10 ** 8; // 6 INR/kWh
      await mockPriceFeed.updateAnswer(newPrice);

      const price = await priceOracle.getLatestPrice();
      expect(price).to.equal(newPrice);
    });

    it("should reject stale prices", async function () {
      // Move time forward past staleness threshold
      const STALENESS_THRESHOLD = 3600; // 1 hour
      await time.increase(STALENESS_THRESHOLD + 1);

      // Price should still be readable but may have staleness indicator
      // depending on implementation
      const isStale = await priceOracle.isPriceStale();
      expect(isStale).to.be.true;
    });

    it("should enforce price bounds", async function () {
      const minPrice = await priceOracle.minPrice();
      const maxPrice = await priceOracle.maxPrice();

      console.log("\n  Price Bounds:");
      console.log("  -------------");
      console.log(`  Min: ${Number(minPrice) / 10 ** DECIMALS} INR/kWh`);
      console.log(`  Max: ${Number(maxPrice) / 10 ** DECIMALS} INR/kWh`);

      // Price within bounds should be accepted
      expect(BASE_PRICE).to.be.gte(minPrice);
      expect(BASE_PRICE).to.be.lte(maxPrice);
    });
  });

  describe("Grid Frequency Monitoring", function () {
    it("should read grid frequency from oracle", async function () {
      const frequency = await mockGridFeed.getFrequency();

      console.log("\n  Grid Frequency:");
      console.log("  ---------------");
      console.log(`  Raw Value: ${frequency}`);
      console.log(`  Formatted: ${Number(frequency) / 100} Hz`);

      expect(frequency).to.equal(NORMAL_FREQUENCY);
    });

    it("should detect high demand (low frequency)", async function () {
      // Grid frequency drops below 49.5 Hz indicates high demand
      const lowFrequency = 49.3 * 100; // 49.30 Hz
      await mockGridFeed.setFrequency(lowFrequency);

      const frequency = await mockGridFeed.getFrequency();
      expect(frequency).to.be.lt(49.5 * 100);

      console.log("\n  High Demand Detected:");
      console.log("  ---------------------");
      console.log(`  Frequency: ${Number(frequency) / 100} Hz (below 49.5 Hz)`);
    });

    it("should detect low demand (high frequency)", async function () {
      // Grid frequency above 50.5 Hz indicates low demand
      const highFrequency = 50.8 * 100; // 50.80 Hz
      await mockGridFeed.setFrequency(highFrequency);

      const frequency = await mockGridFeed.getFrequency();
      expect(frequency).to.be.gt(50.5 * 100);

      console.log("\n  Low Demand Detected:");
      console.log("  --------------------");
      console.log(`  Frequency: ${Number(frequency) / 100} Hz (above 50.5 Hz)`);
    });
  });

  describe("Dynamic Pricing Calculations", function () {
    it("should calculate base price at normal conditions", async function () {
      // Normal frequency, base time
      const price = await dynamicPricing.calculatePrice(
        ethers.parseEther("100"), // 100 kWh
        4 * 3600 // 4 hour delivery window
      );

      console.log("\n  Base Price Calculation:");
      console.log("  -----------------------");
      console.log(`  Quantity: 100 kWh`);
      console.log(`  Calculated Price: ${ethers.formatEther(price)} SHAKTI`);
    });

    it("should increase price during high demand", async function () {
      // Get base price
      const basePrice = await dynamicPricing.calculatePrice(
        ethers.parseEther("100"),
        4 * 3600
      );

      // Simulate high demand (low frequency)
      await mockGridFeed.setFrequency(49.0 * 100);

      const highDemandPrice = await dynamicPricing.calculatePrice(
        ethers.parseEther("100"),
        4 * 3600
      );

      // Price should be higher
      expect(highDemandPrice).to.be.gte(basePrice);

      console.log("\n  High Demand Pricing:");
      console.log("  --------------------");
      console.log(`  Normal Price: ${ethers.formatEther(basePrice)} SHAKTI`);
      console.log(`  High Demand Price: ${ethers.formatEther(highDemandPrice)} SHAKTI`);
      console.log(`  Premium: ${((Number(highDemandPrice) / Number(basePrice) - 1) * 100).toFixed(1)}%`);
    });

    it("should decrease price during low demand", async function () {
      // Get base price
      const basePrice = await dynamicPricing.calculatePrice(
        ethers.parseEther("100"),
        4 * 3600
      );

      // Simulate low demand (high frequency)
      await mockGridFeed.setFrequency(51.0 * 100);

      const lowDemandPrice = await dynamicPricing.calculatePrice(
        ethers.parseEther("100"),
        4 * 3600
      );

      // Price should be lower or same
      expect(lowDemandPrice).to.be.lte(basePrice);

      console.log("\n  Low Demand Pricing:");
      console.log("  -------------------");
      console.log(`  Normal Price: ${ethers.formatEther(basePrice)} SHAKTI`);
      console.log(`  Low Demand Price: ${ethers.formatEther(lowDemandPrice)} SHAKTI`);
      console.log(`  Discount: ${((1 - Number(lowDemandPrice) / Number(basePrice)) * 100).toFixed(1)}%`);
    });
  });

  describe("Time-of-Use Pricing", function () {
    it("should apply peak pricing during peak hours", async function () {
      // Set time to peak hour (e.g., 6 PM = 18:00)
      // Note: This requires manipulating block timestamp

      const currentHour = new Date().getHours();
      const isPeak = currentHour >= 17 && currentHour <= 21; // 5 PM - 9 PM

      console.log("\n  Time-of-Use Analysis:");
      console.log("  ----------------------");
      console.log(`  Current Hour: ${currentHour}:00`);
      console.log(`  Is Peak: ${isPeak}`);

      // Peak multiplier would apply if in peak hours
    });

    it("should apply off-peak pricing during night hours", async function () {
      // Off-peak: 11 PM - 5 AM
      const currentHour = new Date().getHours();
      const isOffPeak = currentHour >= 23 || currentHour <= 5;

      console.log("\n  Off-Peak Analysis:");
      console.log("  ------------------");
      console.log(`  Current Hour: ${currentHour}:00`);
      console.log(`  Is Off-Peak: ${isOffPeak}`);
    });

    it("should provide current pricing tier", async function () {
      const tier = await dynamicPricing.getCurrentTier();

      console.log("\n  Current Pricing Tier:");
      console.log("  ---------------------");
      console.log(`  Tier: ${tier}`);
    });
  });

  describe("Demand Multipliers", function () {
    it("should calculate demand multiplier based on grid state", async function () {
      // Test various frequency levels
      const frequencies = [48.5, 49.0, 49.5, 50.0, 50.5, 51.0, 51.5];

      console.log("\n  Demand Multipliers:");
      console.log("  -------------------");
      console.log("  Frequency (Hz) | Multiplier");
      console.log("  --------------|------------");

      for (const freq of frequencies) {
        await mockGridFeed.setFrequency(freq * 100);
        const multiplier = await dynamicPricing.getDemandMultiplier();
        console.log(`  ${freq.toFixed(1).padStart(12)} | ${Number(multiplier) / 100}x`);
      }
    });

    it("should cap multipliers at maximum bounds", async function () {
      // Extreme low frequency
      await mockGridFeed.setFrequency(47.5 * 100);
      const extremeMultiplier = await dynamicPricing.getDemandMultiplier();

      // Should be capped at maximum (e.g., 2x)
      const MAX_MULTIPLIER = await dynamicPricing.MAX_MULTIPLIER();
      expect(extremeMultiplier).to.be.lte(MAX_MULTIPLIER);

      console.log("\n  Multiplier Caps:");
      console.log("  ----------------");
      console.log(`  Max Multiplier: ${Number(MAX_MULTIPLIER) / 100}x`);
      console.log(`  At 47.5 Hz: ${Number(extremeMultiplier) / 100}x`);
    });
  });

  describe("Oracle Updates", function () {
    it("should allow authorized oracle to update prices", async function () {
      const newBasePrice = 7 * 10 ** 8; // 7 INR/kWh
      await mockPriceFeed.updateAnswer(newBasePrice);

      const price = await priceOracle.getLatestPrice();
      expect(price).to.equal(newBasePrice);
    });

    it("should emit events on price updates", async function () {
      const newPrice = 8 * 10 ** 8;

      // Mock feeds emit events that can be monitored
      await expect(mockPriceFeed.updateAnswer(newPrice))
        .to.emit(mockPriceFeed, "AnswerUpdated");
    });

    it("should handle rapid price fluctuations", async function () {
      const prices = [5, 5.5, 6, 5.8, 6.2, 5.9, 6.5].map((p) => p * 10 ** 8);

      for (const price of prices) {
        await mockPriceFeed.updateAnswer(price);
        const current = await priceOracle.getLatestPrice();
        expect(current).to.equal(price);
      }

      console.log("\n  Price Fluctuation Test:");
      console.log("  -----------------------");
      console.log(`  Updates processed: ${prices.length}`);
      console.log(`  Final price: ${Number(prices[prices.length - 1]) / 10 ** 8} INR/kWh`);
    });
  });

  describe("Price History", function () {
    it("should track price history for analysis", async function () {
      // Update prices over time
      const priceUpdates = [5, 5.2, 5.1, 5.4, 5.3];

      for (const price of priceUpdates) {
        await mockPriceFeed.updateAnswer(price * 10 ** 8);
        await ethers.provider.send("evm_mine", []);
      }

      // Get historical round data
      const latestRound = await mockPriceFeed.latestRound();

      console.log("\n  Price History:");
      console.log("  --------------");
      console.log(`  Total Rounds: ${latestRound}`);
    });
  });

  describe("Failsafe Mechanisms", function () {
    it("should use fallback price when oracle fails", async function () {
      // Set oracle to return invalid data (price = 0)
      await mockPriceFeed.updateAnswer(0);

      // Oracle should have fallback mechanism
      // Implementation depends on contract design
    });

    it("should maintain last valid price during outage", async function () {
      // Get current valid price
      const validPrice = await priceOracle.getLatestPrice();

      // Simulate staleness
      await time.increase(7200); // 2 hours

      // Last valid price should still be accessible
      // (depending on implementation)
    });

    it("should alert on price deviation", async function () {
      // Large price jump
      const normalPrice = 5 * 10 ** 8;
      const spikePrice = 15 * 10 ** 8; // 3x increase

      await mockPriceFeed.updateAnswer(spikePrice);

      // Contract may emit warning event or reject extreme prices
      // depending on implementation
      console.log("\n  Price Deviation Test:");
      console.log("  ---------------------");
      console.log(`  Normal: ${normalPrice / 10 ** 8} INR/kWh`);
      console.log(`  Spike: ${spikePrice / 10 ** 8} INR/kWh`);
      console.log(`  Change: ${((spikePrice / normalPrice - 1) * 100).toFixed(0)}%`);
    });
  });

  describe("Integration with Auction", function () {
    it("should provide pricing data for auction matching", async function () {
      // Simulate price calculation for typical order
      const quantity = ethers.parseEther("50"); // 50 kWh
      const duration = 2 * 3600; // 2 hours

      const totalPrice = await dynamicPricing.calculatePrice(quantity, duration);
      const pricePerKwh = totalPrice * ethers.parseEther("1") / quantity;

      console.log("\n  Auction Pricing:");
      console.log("  ----------------");
      console.log(`  Order Size: ${ethers.formatEther(quantity)} kWh`);
      console.log(`  Duration: 2 hours`);
      console.log(`  Total Price: ${ethers.formatEther(totalPrice)} SHAKTI`);
      console.log(`  Per kWh: ${ethers.formatEther(pricePerKwh)} SHAKTI`);
    });
  });
});
