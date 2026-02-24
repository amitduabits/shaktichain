import { expect } from "chai";
import { ethers } from "hardhat";
import {
  DynamicPricing,
  GridStatusOracle,
  MockAggregatorV3,
  MockFrequencyFeed,
  PriceOracle,
} from "../../typechain-types";

describe("Integration: Oracle & Dynamic Pricing", function () {
  let priceOracle: PriceOracle;
  let gridOracle: GridStatusOracle;
  let dynamicPricing: DynamicPricing;
  let priceFeed: MockAggregatorV3;
  let freqFeed: MockFrequencyFeed;

  const DECIMALS = 8;
  const BASE_PRICE = 500 * 10 ** 8; // 500 paise/kWh = 5 INR/kWh

  beforeEach(async function () {
    const [admin] = await ethers.getSigners();

    const MockAggregatorFactory = await ethers.getContractFactory("MockAggregatorV3");
    priceFeed = await MockAggregatorFactory.deploy(
      DECIMALS,
      "IEX/INR Electricity Price",
      BASE_PRICE
    );
    await priceFeed.waitForDeployment();

    const MockFrequencyFactory = await ethers.getContractFactory("MockFrequencyFeed");
    freqFeed = await MockFrequencyFactory.deploy();
    await freqFeed.waitForDeployment();
    await freqFeed.updateAnswer(50000n); // 50.000 Hz

    const PriceOracleFactory = await ethers.getContractFactory("PriceOracle");
    priceOracle = await PriceOracleFactory.deploy(
      await priceFeed.getAddress(),
      ethers.ZeroAddress,
      admin.address,
      100n * 10n ** 8n,
      2000n * 10n ** 8n
    );
    await priceOracle.waitForDeployment();

    const GridOracleFactory = await ethers.getContractFactory("GridStatusOracle");
    gridOracle = await GridOracleFactory.deploy(
      await freqFeed.getAddress(),
      admin.address,
      10000
    );
    await gridOracle.waitForDeployment();

    const DynamicPricingFactory = await ethers.getContractFactory("DynamicPricing");
    dynamicPricing = await DynamicPricingFactory.deploy(
      await priceOracle.getAddress(),
      await gridOracle.getAddress(),
      admin.address
    );
    await dynamicPricing.waitForDeployment();
  });

  it("reads spot price from the oracle feed", async function () {
    const [spotPrice] = await priceOracle.getSpotPrice();
    expect(spotPrice).to.equal(BASE_PRICE);
  });

  it("increases price under under-frequency stress and discounts over-frequency", async function () {
    const [spotPrice] = await priceOracle.getSpotPrice();
    const hour = 15; // shoulder/normal window
    const demandRatio = 10000; // balanced

    await freqFeed.updateAnswer(50000n);
    const normalPrice = await dynamicPricing.calculateDynamicPrice(spotPrice, hour, demandRatio);

    await freqFeed.updateAnswer(49000n); // under-frequency => premium
    const stressedPrice = await dynamicPricing.calculateDynamicPrice(spotPrice, hour, demandRatio);

    await freqFeed.updateAnswer(51000n); // over-frequency => discount
    const relaxedPrice = await dynamicPricing.calculateDynamicPrice(spotPrice, hour, demandRatio);

    expect(stressedPrice).to.be.gte(normalPrice);
    expect(relaxedPrice).to.be.lte(normalPrice);
  });
});
