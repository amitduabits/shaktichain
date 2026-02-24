import { expect } from "chai";
import { ethers } from "hardhat";
import { loadFixture, time } from "@nomicfoundation/hardhat-network-helpers";
import { ShaktiToken, EnergyAuction } from "../typechain-types";

describe("EnergyAuction", function () {
  // Constants
  const PRICE_PRECISION = ethers.parseEther("1"); // 1e18
  const MIN_QUANTITY = 1000n; // 1 kWh in Wh
  const MAX_QUANTITY = 100000n; // 100 kWh in Wh
  const MIN_DURATION = 5 * 60; // 5 minutes
  const MAX_DURATION = 60 * 60; // 60 minutes

  // Price bounds (2-15 INR/kWh scaled to per Wh)
  // For testing: 2 INR/kWh = 0.002 INR/Wh = 2e15 wei per Wh
  const MIN_PRICE = ethers.parseEther("0.002"); // 2 INR/kWh
  const MAX_PRICE = ethers.parseEther("0.015"); // 15 INR/kWh

  // Roles
  const AUCTIONEER_ROLE = ethers.keccak256(ethers.toUtf8Bytes("AUCTIONEER_ROLE"));
  const OPERATOR_ROLE = ethers.keccak256(ethers.toUtf8Bytes("OPERATOR_ROLE"));

  // Enum values
  enum AuctionState { OPEN, CLOSED, CLEARING, SETTLED }
  enum OrderStatus { ACTIVE, MATCHED, CANCELLED, EXPIRED }

  async function deployFixture() {
    const [admin, auctioneer, operator, buyer1, buyer2, buyer3, seller1, seller2, seller3] =
      await ethers.getSigners();

    // Deploy ShaktiToken
    const ShaktiTokenFactory = await ethers.getContractFactory("ShaktiToken");
    const token = await ShaktiTokenFactory.deploy(admin.address, admin.address);
    await token.waitForDeployment();

    // Deploy EnergyAuction
    const EnergyAuctionFactory = await ethers.getContractFactory("EnergyAuction");
    const auction = await EnergyAuctionFactory.deploy(
      await token.getAddress(),
      ethers.ZeroAddress, // No registry for testing
      admin.address,
      MIN_PRICE,
      MAX_PRICE
    );
    await auction.waitForDeployment();

    // Grant roles
    await auction.connect(admin).grantRole(AUCTIONEER_ROLE, auctioneer.address);
    await auction.connect(admin).grantRole(OPERATOR_ROLE, operator.address);

    // Distribute tokens to buyers
    const tokenAmount = ethers.parseEther("100000");
    await token.connect(admin).transfer(buyer1.address, tokenAmount);
    await token.connect(admin).transfer(buyer2.address, tokenAmount);
    await token.connect(admin).transfer(buyer3.address, tokenAmount);

    // Approve auction contract
    await token.connect(buyer1).approve(await auction.getAddress(), ethers.MaxUint256);
    await token.connect(buyer2).approve(await auction.getAddress(), ethers.MaxUint256);
    await token.connect(buyer3).approve(await auction.getAddress(), ethers.MaxUint256);

    return {
      token,
      auction,
      admin,
      auctioneer,
      operator,
      buyer1,
      buyer2,
      buyer3,
      seller1,
      seller2,
      seller3
    };
  }

  async function deployWithAuctionFixture() {
    const fixture = await loadFixture(deployFixture);
    const { auction, auctioneer } = fixture;

    // Create an auction round
    await auction.connect(auctioneer).createAuctionRound(MIN_DURATION);

    return fixture;
  }

  // ============ Deployment Tests ============
  describe("Deployment", function () {
    it("should deploy with correct parameters", async function () {
      const { auction, token, admin } = await loadFixture(deployFixture);

      expect(await auction.shaktiToken()).to.equal(await token.getAddress());
      expect(await auction.minPrice()).to.equal(MIN_PRICE);
      expect(await auction.maxPrice()).to.equal(MAX_PRICE);
      expect(await auction.hasRole(AUCTIONEER_ROLE, admin.address)).to.be.true;
    });

    it("should revert if token is zero address", async function () {
      const [admin] = await ethers.getSigners();
      const EnergyAuctionFactory = await ethers.getContractFactory("EnergyAuction");

      await expect(
        EnergyAuctionFactory.deploy(
          ethers.ZeroAddress,
          ethers.ZeroAddress,
          admin.address,
          MIN_PRICE,
          MAX_PRICE
        )
      ).to.be.revertedWithCustomError(EnergyAuctionFactory, "ZeroAddress");
    });

    it("should revert if min price >= max price", async function () {
      const { token } = await loadFixture(deployFixture);
      const [admin] = await ethers.getSigners();
      const EnergyAuctionFactory = await ethers.getContractFactory("EnergyAuction");

      await expect(
        EnergyAuctionFactory.deploy(
          await token.getAddress(),
          ethers.ZeroAddress,
          admin.address,
          MAX_PRICE,
          MIN_PRICE
        )
      ).to.be.revertedWithCustomError(EnergyAuctionFactory, "InvalidPrice");
    });
  });

  // ============ Auction Round Tests ============
  describe("Auction Round Creation", function () {
    it("should create an auction round", async function () {
      const { auction, auctioneer } = await loadFixture(deployFixture);

      await expect(auction.connect(auctioneer).createAuctionRound(MIN_DURATION))
        .to.emit(auction, "AuctionRoundCreated");

      const round = await auction.getAuctionRound(1);
      expect(round.roundId).to.equal(1);
      expect(round.state).to.equal(AuctionState.OPEN);
    });

    it("should revert if duration is invalid", async function () {
      const { auction, auctioneer } = await loadFixture(deployFixture);

      await expect(
        auction.connect(auctioneer).createAuctionRound(60) // Less than 5 minutes
      ).to.be.revertedWithCustomError(auction, "InvalidDuration");

      await expect(
        auction.connect(auctioneer).createAuctionRound(3700) // More than 60 minutes
      ).to.be.revertedWithCustomError(auction, "InvalidDuration");
    });

    it("should revert if non-auctioneer tries to create", async function () {
      const { auction, buyer1 } = await loadFixture(deployFixture);

      await expect(
        auction.connect(buyer1).createAuctionRound(MIN_DURATION)
      ).to.be.revertedWithCustomError(auction, "AccessControlUnauthorizedAccount");
    });

    it("should increment round ID", async function () {
      const { auction, auctioneer, operator } = await loadFixture(deployFixture);

      await auction.connect(auctioneer).createAuctionRound(MIN_DURATION);
      expect(await auction.currentRoundId()).to.equal(1);

      // Fast forward past auction end and settle
      await time.increase(MIN_DURATION + 1);
      await auction.connect(auctioneer).closeAuction(1);
      await auction.connect(operator).clearMarket(1);

      await auction.connect(auctioneer).createAuctionRound(MIN_DURATION);
      expect(await auction.currentRoundId()).to.equal(2);
    });
  });

  // ============ Bid Submission Tests ============
  describe("Bid Submission", function () {
    it("should submit a valid bid", async function () {
      const { auction, buyer1 } = await loadFixture(deployWithAuctionFixture);

      const quantity = 10000n; // 10 kWh
      const price = ethers.parseEther("0.010"); // 10 INR/kWh

      await expect(auction.connect(buyer1).submitBid(quantity, price))
        .to.emit(auction, "BidSubmitted")
        .withArgs(1, 0, buyer1.address, quantity, price);

      const order = await auction.getOrder(1, 0);
      expect(order.trader).to.equal(buyer1.address);
      expect(order.quantity).to.equal(quantity);
      expect(order.price).to.equal(price);
      expect(order.isBid).to.be.true;
    });

    it("should lock deposit for bids", async function () {
      const { auction, token, buyer1 } = await loadFixture(deployWithAuctionFixture);

      const quantity = 10000n; // 10 kWh
      const price = ethers.parseEther("0.010");

      const balanceBefore = await token.balanceOf(buyer1.address);
      await auction.connect(buyer1).submitBid(quantity, price);
      const balanceAfter = await token.balanceOf(buyer1.address);

      const expectedDeposit = (quantity * price) / PRICE_PRECISION;
      expect(balanceBefore - balanceAfter).to.equal(expectedDeposit);
    });

    it("should revert if quantity is too low", async function () {
      const { auction, buyer1 } = await loadFixture(deployWithAuctionFixture);

      await expect(
        auction.connect(buyer1).submitBid(500n, ethers.parseEther("0.010"))
      ).to.be.revertedWithCustomError(auction, "InvalidQuantity");
    });

    it("should revert if quantity is too high", async function () {
      const { auction, buyer1 } = await loadFixture(deployWithAuctionFixture);

      await expect(
        auction.connect(buyer1).submitBid(150000n, ethers.parseEther("0.010"))
      ).to.be.revertedWithCustomError(auction, "InvalidQuantity");
    });

    it("should revert if price is out of bounds", async function () {
      const { auction, buyer1 } = await loadFixture(deployWithAuctionFixture);

      await expect(
        auction.connect(buyer1).submitBid(10000n, ethers.parseEther("0.001"))
      ).to.be.revertedWithCustomError(auction, "InvalidPrice");

      await expect(
        auction.connect(buyer1).submitBid(10000n, ethers.parseEther("0.020"))
      ).to.be.revertedWithCustomError(auction, "InvalidPrice");
    });

    it("should revert if no active auction", async function () {
      const { auction, buyer1 } = await loadFixture(deployFixture);

      await expect(
        auction.connect(buyer1).submitBid(10000n, ethers.parseEther("0.010"))
      ).to.be.revertedWithCustomError(auction, "NoActiveAuction");
    });

    it("should revert if auction has ended", async function () {
      const { auction, auctioneer, buyer1 } = await loadFixture(deployWithAuctionFixture);

      await time.increase(MIN_DURATION + 1);

      await expect(
        auction.connect(buyer1).submitBid(10000n, ethers.parseEther("0.010"))
      ).to.be.revertedWithCustomError(auction, "AuctionAlreadyEnded");
    });
  });

  // ============ Ask Submission Tests ============
  describe("Ask Submission", function () {
    it("should submit a valid ask", async function () {
      const { auction, seller1 } = await loadFixture(deployWithAuctionFixture);

      const quantity = 10000n;
      const price = ethers.parseEther("0.008");

      await expect(auction.connect(seller1).submitAsk(quantity, price))
        .to.emit(auction, "AskSubmitted")
        .withArgs(1, 0, seller1.address, quantity, price);

      const order = await auction.getOrder(1, 0);
      expect(order.trader).to.equal(seller1.address);
      expect(order.isBid).to.be.false;
    });

    it("should not require deposit for asks", async function () {
      const { auction, token, seller1, admin } = await loadFixture(deployWithAuctionFixture);

      // Give seller1 some tokens to verify no transfer happens
      await token.connect(admin).transfer(seller1.address, ethers.parseEther("1000"));
      const balanceBefore = await token.balanceOf(seller1.address);

      await auction.connect(seller1).submitAsk(10000n, ethers.parseEther("0.008"));

      const balanceAfter = await token.balanceOf(seller1.address);
      expect(balanceBefore).to.equal(balanceAfter);
    });
  });

  // ============ Order Book Sorting Tests ============
  describe("Order Book Sorting", function () {
    it("should sort bids in descending order by price", async function () {
      const { auction, buyer1, buyer2, buyer3 } = await loadFixture(deployWithAuctionFixture);

      // Submit bids out of order
      await auction.connect(buyer2).submitBid(10000n, ethers.parseEther("0.008"));
      await auction.connect(buyer1).submitBid(10000n, ethers.parseEther("0.012"));
      await auction.connect(buyer3).submitBid(10000n, ethers.parseEther("0.010"));

      const [bids] = await auction.getOrderBook(1);

      // Should be sorted: 0.012, 0.010, 0.008
      expect(bids[0].price).to.equal(ethers.parseEther("0.012"));
      expect(bids[1].price).to.equal(ethers.parseEther("0.010"));
      expect(bids[2].price).to.equal(ethers.parseEther("0.008"));
    });

    it("should sort asks in ascending order by price", async function () {
      const { auction, seller1, seller2, seller3 } = await loadFixture(deployWithAuctionFixture);

      // Submit asks out of order
      await auction.connect(seller2).submitAsk(10000n, ethers.parseEther("0.010"));
      await auction.connect(seller1).submitAsk(10000n, ethers.parseEther("0.006"));
      await auction.connect(seller3).submitAsk(10000n, ethers.parseEther("0.008"));

      const [, asks] = await auction.getOrderBook(1);

      // Should be sorted: 0.006, 0.008, 0.010
      expect(asks[0].price).to.equal(ethers.parseEther("0.006"));
      expect(asks[1].price).to.equal(ethers.parseEther("0.008"));
      expect(asks[2].price).to.equal(ethers.parseEther("0.010"));
    });
  });

  // ============ Order Cancellation Tests ============
  describe("Order Cancellation", function () {
    it("should cancel a bid and refund deposit", async function () {
      const { auction, token, buyer1 } = await loadFixture(deployWithAuctionFixture);

      const quantity = 10000n;
      const price = ethers.parseEther("0.010");

      await auction.connect(buyer1).submitBid(quantity, price);
      const balanceAfterBid = await token.balanceOf(buyer1.address);

      await expect(auction.connect(buyer1).cancelOrder(1, 0))
        .to.emit(auction, "OrderCancelled")
        .and.to.emit(auction, "DepositRefunded");

      const balanceAfterCancel = await token.balanceOf(buyer1.address);
      const expectedRefund = (quantity * price) / PRICE_PRECISION;
      expect(balanceAfterCancel - balanceAfterBid).to.equal(expectedRefund);
    });

    it("should cancel an ask", async function () {
      const { auction, seller1 } = await loadFixture(deployWithAuctionFixture);

      await auction.connect(seller1).submitAsk(10000n, ethers.parseEther("0.008"));

      await expect(auction.connect(seller1).cancelOrder(1, 0))
        .to.emit(auction, "OrderCancelled");

      const order = await auction.getOrder(1, 0);
      expect(order.status).to.equal(OrderStatus.CANCELLED);
    });

    it("should revert if not order owner", async function () {
      const { auction, buyer1, buyer2 } = await loadFixture(deployWithAuctionFixture);

      await auction.connect(buyer1).submitBid(10000n, ethers.parseEther("0.010"));

      await expect(
        auction.connect(buyer2).cancelOrder(1, 0)
      ).to.be.revertedWithCustomError(auction, "NotOrderOwner");
    });
  });

  // ============ McAfee Clearing Algorithm Tests ============
  describe("McAfee Clearing Algorithm", function () {
    it("should clear market with matching orders", async function () {
      const { auction, auctioneer, operator, buyer1, seller1 } =
        await loadFixture(deployWithAuctionFixture);

      // Buyer bids 10 INR/kWh
      await auction.connect(buyer1).submitBid(10000n, ethers.parseEther("0.010"));
      // Seller asks 8 INR/kWh
      await auction.connect(seller1).submitAsk(10000n, ethers.parseEther("0.008"));

      // Close and clear
      await time.increase(MIN_DURATION + 1);
      await auction.connect(auctioneer).closeAuction(1);

      await expect(auction.connect(operator).clearMarket(1))
        .to.emit(auction, "AuctionCleared");

      const round = await auction.getAuctionRound(1);
      expect(round.state).to.equal(AuctionState.SETTLED);
      expect(round.matchedOrders).to.equal(2);
      expect(round.clearingPrice).to.be.gt(0);
    });

    it("should calculate correct clearing price using McAfee formula", async function () {
      const { auction, auctioneer, operator, buyer1, buyer2, seller1, seller2 } =
        await loadFixture(deployWithAuctionFixture);

      // Two bids (descending): 12, 10
      await auction.connect(buyer1).submitBid(10000n, ethers.parseEther("0.012"));
      await auction.connect(buyer2).submitBid(10000n, ethers.parseEther("0.010"));

      // Two asks (ascending): 6, 8
      await auction.connect(seller1).submitAsk(10000n, ethers.parseEther("0.006"));
      await auction.connect(seller2).submitAsk(10000n, ethers.parseEther("0.008"));

      await time.increase(MIN_DURATION + 1);
      await auction.connect(auctioneer).closeAuction(1);
      await auction.connect(operator).clearMarket(1);

      const round = await auction.getAuctionRound(1);

      // With bids [12, 10] and asks [6, 8]:
      // bid[0]=12 >= ask[0]=6 ✓
      // bid[1]=10 >= ask[1]=8 ✓
      // k=1, clearing price = (bid[1] + ask[2]) / 2 or (10 + 8) / 2 = 9
      // But since there's no ask[2], it's (bid[k] + ask[k]) / 2 = (10 + 8) / 2 = 9
      expect(round.clearingPrice).to.equal(ethers.parseEther("0.009"));
    });

    it("should handle no matching orders", async function () {
      const { auction, auctioneer, operator, buyer1, seller1 } =
        await loadFixture(deployWithAuctionFixture);

      // Buyer bids 6 INR/kWh
      await auction.connect(buyer1).submitBid(10000n, ethers.parseEther("0.006"));
      // Seller asks 10 INR/kWh (higher than bid)
      await auction.connect(seller1).submitAsk(10000n, ethers.parseEther("0.010"));

      await time.increase(MIN_DURATION + 1);
      await auction.connect(auctioneer).closeAuction(1);
      await auction.connect(operator).clearMarket(1);

      const round = await auction.getAuctionRound(1);
      expect(round.matchedOrders).to.equal(0);
      expect(round.clearingPrice).to.equal(0);
    });

    it("should handle empty order book", async function () {
      const { auction, auctioneer, operator } = await loadFixture(deployWithAuctionFixture);

      await time.increase(MIN_DURATION + 1);
      await auction.connect(auctioneer).closeAuction(1);
      await auction.connect(operator).clearMarket(1);

      const round = await auction.getAuctionRound(1);
      expect(round.state).to.equal(AuctionState.SETTLED);
      expect(round.matchedOrders).to.equal(0);
    });

    it("should transfer correct amounts on match", async function () {
      const { auction, token, auctioneer, operator, buyer1, seller1, admin } =
        await loadFixture(deployWithAuctionFixture);

      // Give seller tokens to track balance
      await token.connect(admin).transfer(seller1.address, ethers.parseEther("1000"));

      const quantity = 10000n;
      const bidPrice = ethers.parseEther("0.010");
      const askPrice = ethers.parseEther("0.008");

      const buyerBalanceBefore = await token.balanceOf(buyer1.address);
      const sellerBalanceBefore = await token.balanceOf(seller1.address);

      await auction.connect(buyer1).submitBid(quantity, bidPrice);
      await auction.connect(seller1).submitAsk(quantity, askPrice);

      await time.increase(MIN_DURATION + 1);
      await auction.connect(auctioneer).closeAuction(1);
      await auction.connect(operator).clearMarket(1);

      const round = await auction.getAuctionRound(1);
      const clearingPrice = round.clearingPrice;

      // Buyer should receive refund for price difference
      const buyerBalanceAfter = await token.balanceOf(buyer1.address);
      const sellerBalanceAfter = await token.balanceOf(seller1.address);

      // Seller receives: quantity * clearingPrice / PRECISION
      const sellerPayment = (quantity * clearingPrice) / PRICE_PRECISION;
      expect(sellerBalanceAfter - sellerBalanceBefore).to.equal(sellerPayment);

      // Buyer deposited: quantity * bidPrice / PRECISION
      // Buyer spent: quantity * clearingPrice / PRECISION
      // Net cost = deposit - refund = clearingPrice * quantity / PRECISION
      const deposit = (quantity * bidPrice) / PRICE_PRECISION;
      const expectedBuyerBalance = buyerBalanceBefore - deposit + (deposit - sellerPayment);
      expect(buyerBalanceAfter).to.be.closeTo(expectedBuyerBalance, 100n);
    });
  });

  // ============ Realistic Auction Scenario Tests ============
  describe("Realistic Auction Scenarios", function () {
    it("should handle a typical V2G trading session", async function () {
      const { auction, token, auctioneer, operator, admin, buyer1, buyer2, buyer3, seller1, seller2, seller3 } =
        await loadFixture(deployWithAuctionFixture);

      // Give sellers tokens
      await token.connect(admin).transfer(seller1.address, ethers.parseEther("1000"));
      await token.connect(admin).transfer(seller2.address, ethers.parseEther("1000"));
      await token.connect(admin).transfer(seller3.address, ethers.parseEther("1000"));

      // Buyers submit bids (sorted: 12, 11, 10)
      await auction.connect(buyer1).submitBid(20000n, ethers.parseEther("0.012")); // 20 kWh at 12 INR
      await auction.connect(buyer2).submitBid(15000n, ethers.parseEther("0.011")); // 15 kWh at 11 INR
      await auction.connect(buyer3).submitBid(10000n, ethers.parseEther("0.010")); // 10 kWh at 10 INR

      // Sellers submit asks (sorted: 7, 8, 9)
      await auction.connect(seller1).submitAsk(15000n, ethers.parseEther("0.007")); // 15 kWh at 7 INR
      await auction.connect(seller2).submitAsk(20000n, ethers.parseEther("0.008")); // 20 kWh at 8 INR
      await auction.connect(seller3).submitAsk(10000n, ethers.parseEther("0.009")); // 10 kWh at 9 INR

      // Check order book
      const [bids, asks] = await auction.getOrderBook(1);
      expect(bids.length).to.equal(3);
      expect(asks.length).to.equal(3);

      // Close and clear
      await time.increase(MIN_DURATION + 1);
      await auction.connect(auctioneer).closeAuction(1);
      await auction.connect(operator).clearMarket(1);

      const round = await auction.getAuctionRound(1);

      // All pairs should match since bid[i] >= ask[i] for i = 0,1,2
      // 12 >= 7, 11 >= 8, 10 >= 9
      expect(round.matchedOrders).to.be.gt(0);
      expect(round.totalVolume).to.be.gt(0);
    });

    it("should handle partial market clearing", async function () {
      const { auction, auctioneer, operator, buyer1, buyer2, seller1, seller2 } =
        await loadFixture(deployWithAuctionFixture);

      // Bids: 12, 8 (descending)
      await auction.connect(buyer1).submitBid(10000n, ethers.parseEther("0.012"));
      await auction.connect(buyer2).submitBid(10000n, ethers.parseEther("0.008"));

      // Asks: 7, 10 (ascending)
      await auction.connect(seller1).submitAsk(10000n, ethers.parseEther("0.007"));
      await auction.connect(seller2).submitAsk(10000n, ethers.parseEther("0.010"));

      await time.increase(MIN_DURATION + 1);
      await auction.connect(auctioneer).closeAuction(1);
      await auction.connect(operator).clearMarket(1);

      const round = await auction.getAuctionRound(1);

      // Only first pair matches: 12 >= 7
      // Second pair doesn't: 8 < 10
      expect(round.matchedOrders).to.equal(2); // 1 bid + 1 ask
    });

    it("should handle multiple clearing batches", async function () {
      const { auction, token, auctioneer, operator, admin } =
        await loadFixture(deployWithAuctionFixture);

      const signers = await ethers.getSigners();

      // Create many orders (more than BATCH_SIZE)
      for (let i = 4; i < 20; i++) {
        await token.connect(admin).transfer(signers[i].address, ethers.parseEther("10000"));
        await token.connect(signers[i]).approve(await auction.getAddress(), ethers.MaxUint256);

        // Alternate between bids and asks
        if (i % 2 === 0) {
          const price = ethers.parseEther("0.010") + BigInt(i) * ethers.parseEther("0.0001");
          await auction.connect(signers[i]).submitBid(5000n, price);
        } else {
          const price = ethers.parseEther("0.005") + BigInt(i) * ethers.parseEther("0.0001");
          await auction.connect(signers[i]).submitAsk(5000n, price);
        }
      }

      await time.increase(MIN_DURATION + 1);
      await auction.connect(auctioneer).closeAuction(1);
      await auction.connect(operator).clearMarket(1);

      const round = await auction.getAuctionRound(1);
      expect(round.state).to.equal(AuctionState.SETTLED);
    });
  });

  // ============ View Functions Tests ============
  describe("View Functions", function () {
    it("should return current auction info", async function () {
      const { auction } = await loadFixture(deployWithAuctionFixture);

      const [roundId, state, endTime, totalBids, totalAsks] = await auction.getCurrentAuction();

      expect(roundId).to.equal(1);
      expect(state).to.equal(AuctionState.OPEN);
      expect(endTime).to.be.gt(0);
    });

    it("should check if market can clear", async function () {
      const { auction, buyer1, seller1 } = await loadFixture(deployWithAuctionFixture);

      // Initially no orders
      let [canClearBool, potentialMatches] = await auction.canClear(1);
      expect(canClearBool).to.be.false;
      expect(potentialMatches).to.equal(0);

      // Add matching orders
      await auction.connect(buyer1).submitBid(10000n, ethers.parseEther("0.010"));
      await auction.connect(seller1).submitAsk(10000n, ethers.parseEther("0.008"));

      [canClearBool, potentialMatches] = await auction.canClear(1);
      expect(canClearBool).to.be.true;
      expect(potentialMatches).to.equal(1);
    });

    it("should return trader orders", async function () {
      const { auction, buyer1 } = await loadFixture(deployWithAuctionFixture);

      await auction.connect(buyer1).submitBid(10000n, ethers.parseEther("0.010"));
      await auction.connect(buyer1).submitBid(20000n, ethers.parseEther("0.011"));

      const orders = await auction.getTraderOrders(buyer1.address, 1);
      expect(orders.length).to.equal(2);
    });
  });

  // ============ Refund Tests ============
  describe("Refunds", function () {
    it("should allow claiming refunds after settlement", async function () {
      const { auction, token, auctioneer, operator, buyer1, seller1 } =
        await loadFixture(deployWithAuctionFixture);

      // Buyer bids but won't match
      await auction.connect(buyer1).submitBid(10000n, ethers.parseEther("0.006"));
      // Seller asks higher
      await auction.connect(seller1).submitAsk(10000n, ethers.parseEther("0.010"));

      const balanceAfterBid = await token.balanceOf(buyer1.address);

      await time.increase(MIN_DURATION + 1);
      await auction.connect(auctioneer).closeAuction(1);
      await auction.connect(operator).clearMarket(1);

      // Claim refund
      await auction.connect(buyer1).settleRefunds(1);

      const balanceAfterRefund = await token.balanceOf(buyer1.address);
      expect(balanceAfterRefund).to.be.gt(balanceAfterBid);
    });
  });

  // ============ Admin Functions Tests ============
  describe("Admin Functions", function () {
    it("should update price bounds", async function () {
      const { auction, admin } = await loadFixture(deployFixture);

      const newMin = ethers.parseEther("0.003");
      const newMax = ethers.parseEther("0.020");

      await expect(auction.connect(admin).setPriceBounds(newMin, newMax))
        .to.emit(auction, "PriceBoundsUpdated")
        .withArgs(newMin, newMax);

      expect(await auction.minPrice()).to.equal(newMin);
      expect(await auction.maxPrice()).to.equal(newMax);
    });

    it("should pause and unpause", async function () {
      const { auction, admin, buyer1 } = await loadFixture(deployWithAuctionFixture);

      await auction.connect(admin).pause();
      expect(await auction.paused()).to.be.true;

      await expect(
        auction.connect(buyer1).submitBid(10000n, ethers.parseEther("0.010"))
      ).to.be.revertedWithCustomError(auction, "EnforcedPause");

      await auction.connect(admin).unpause();

      await expect(
        auction.connect(buyer1).submitBid(10000n, ethers.parseEther("0.010"))
      ).to.emit(auction, "BidSubmitted");
    });
  });

  // ============ Edge Cases ============
  describe("Edge Cases", function () {
    it("should handle same price bids and asks", async function () {
      const { auction, auctioneer, operator, buyer1, seller1 } =
        await loadFixture(deployWithAuctionFixture);

      const price = ethers.parseEther("0.010");

      await auction.connect(buyer1).submitBid(10000n, price);
      await auction.connect(seller1).submitAsk(10000n, price);

      await time.increase(MIN_DURATION + 1);
      await auction.connect(auctioneer).closeAuction(1);
      await auction.connect(operator).clearMarket(1);

      const round = await auction.getAuctionRound(1);
      expect(round.matchedOrders).to.equal(2);
      expect(round.clearingPrice).to.equal(price);
    });

    it("should handle minimum quantity orders", async function () {
      const { auction, buyer1, seller1 } = await loadFixture(deployWithAuctionFixture);

      await expect(auction.connect(buyer1).submitBid(MIN_QUANTITY, ethers.parseEther("0.010")))
        .to.emit(auction, "BidSubmitted");

      await expect(auction.connect(seller1).submitAsk(MIN_QUANTITY, ethers.parseEther("0.008")))
        .to.emit(auction, "AskSubmitted");
    });

    it("should handle maximum quantity orders", async function () {
      const { auction, buyer1, seller1 } = await loadFixture(deployWithAuctionFixture);

      await expect(auction.connect(buyer1).submitBid(MAX_QUANTITY, ethers.parseEther("0.010")))
        .to.emit(auction, "BidSubmitted");

      await expect(auction.connect(seller1).submitAsk(MAX_QUANTITY, ethers.parseEther("0.008")))
        .to.emit(auction, "AskSubmitted");
    });
  });

  // ============ Commit/Reveal + Batch Settlement ============
  describe("Commit-Reveal Settlement", function () {
    it("should commit, reveal, and settle via operator batch", async function () {
      const { auction, auctioneer, operator, buyer1, seller1 } =
        await loadFixture(deployWithAuctionFixture);

      const quantity = 10_000n;
      const buyPrice = ethers.parseEther("0.010");
      const sellPrice = ethers.parseEther("0.008");
      const settlementPrice = ethers.parseEther("0.009");
      const revealWindow = 600;

      const bidNonce = ethers.id("bid-nonce-1");
      const askNonce = ethers.id("ask-nonce-1");

      const bidCommitment = await auction.computeCommitment(
        1,
        buyer1.address,
        quantity,
        buyPrice,
        true,
        bidNonce
      );
      const askCommitment = await auction.computeCommitment(
        1,
        seller1.address,
        quantity,
        sellPrice,
        false,
        askNonce
      );

      await auction.connect(buyer1).commitOrder(1, bidCommitment, revealWindow);
      await auction.connect(seller1).commitOrder(1, askCommitment, revealWindow);

      await time.increase(MIN_DURATION + 1);
      await auction.connect(auctioneer).closeAuction(1);

      await auction.connect(buyer1).revealOrder(1, 0, quantity, buyPrice, true, bidNonce);
      await auction.connect(seller1).revealOrder(1, 1, quantity, sellPrice, false, askNonce);

      const buyerOrders = await auction.getTraderOrders(buyer1.address, 1);
      const sellerOrders = await auction.getTraderOrders(seller1.address, 1);

      await expect(
        auction.connect(operator).settleBatch(1, settlementPrice, [
          {
            bidOrderId: buyerOrders[0],
            askOrderId: sellerOrders[0],
            quantity,
          },
        ])
      ).to.emit(auction, "BatchSettled");

      const round = await auction.getAuctionRound(1);
      expect(round.state).to.equal(AuctionState.SETTLED);
      expect(round.matchedOrders).to.equal(2);
      expect(round.clearingPrice).to.equal(settlementPrice);
    });

    it("should reject reveal with invalid nonce/hash", async function () {
      const { auction, auctioneer, buyer1 } = await loadFixture(deployWithAuctionFixture);

      const quantity = 10_000n;
      const buyPrice = ethers.parseEther("0.010");
      const revealWindow = 600;
      const validNonce = ethers.id("bid-valid");
      const invalidNonce = ethers.id("bid-invalid");

      const commitment = await auction.computeCommitment(
        1,
        buyer1.address,
        quantity,
        buyPrice,
        true,
        validNonce
      );

      await auction.connect(buyer1).commitOrder(1, commitment, revealWindow);
      await time.increase(MIN_DURATION + 1);
      await auction.connect(auctioneer).closeAuction(1);

      await expect(
        auction.connect(buyer1).revealOrder(1, 0, quantity, buyPrice, true, invalidNonce)
      ).to.be.revertedWithCustomError(auction, "InvalidRevealData");
    });

    it("should block settlement while reveal window is open for unrevealed commits", async function () {
      const { auction, auctioneer, operator, buyer1 } = await loadFixture(deployWithAuctionFixture);

      const quantity = 10_000n;
      const buyPrice = ethers.parseEther("0.010");
      const revealWindow = 600;
      const nonce = ethers.id("pending-bid");
      const commitment = await auction.computeCommitment(
        1,
        buyer1.address,
        quantity,
        buyPrice,
        true,
        nonce
      );

      await auction.connect(buyer1).commitOrder(1, commitment, revealWindow);
      await time.increase(MIN_DURATION + 1);
      await auction.connect(auctioneer).closeAuction(1);

      await expect(
        auction.connect(operator).settleBatch(1, ethers.parseEther("0.009"), [])
      ).to.be.revertedWithCustomError(auction, "RevealWindowOpen");
    });
  });
});
