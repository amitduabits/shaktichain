import { expect } from "chai";
import { ethers } from "hardhat";
import { time } from "@nomicfoundation/hardhat-network-helpers";
import { EnergyAuction, ShaktiToken } from "../../typechain-types";

describe("Integration: Full Trade Flow", function () {
  let token: ShaktiToken;
  let auction: EnergyAuction;

  const ROUND_DURATION = 5 * 60;
  const MIN_PRICE = ethers.parseEther("0.002");
  const MAX_PRICE = ethers.parseEther("0.015");
  const QUANTITY = 10_000n; // Wh
  const BID_PRICE = ethers.parseEther("0.010");
  const ASK_PRICE = ethers.parseEther("0.008");

  beforeEach(async function () {
    const [admin, auctioneer, operator, buyer] = await ethers.getSigners();

    const TokenFactory = await ethers.getContractFactory("ShaktiToken");
    token = await TokenFactory.deploy(admin.address, admin.address);
    await token.waitForDeployment();

    const AuctionFactory = await ethers.getContractFactory("EnergyAuction");
    auction = await AuctionFactory.deploy(
      await token.getAddress(),
      ethers.ZeroAddress,
      admin.address,
      MIN_PRICE,
      MAX_PRICE
    );
    await auction.waitForDeployment();

    const AUCTIONEER_ROLE = await auction.AUCTIONEER_ROLE();
    const OPERATOR_ROLE = await auction.OPERATOR_ROLE();
    await auction.grantRole(AUCTIONEER_ROLE, auctioneer.address);
    await auction.grantRole(OPERATOR_ROLE, operator.address);

    await token.transfer(buyer.address, ethers.parseEther("100000"));
    await token.connect(buyer).approve(await auction.getAddress(), ethers.MaxUint256);

    await auction.connect(auctioneer).createAuctionRound(ROUND_DURATION);
  });

  it("clears and settles a round with matched bid/ask", async function () {
    const [, , operator, buyer, seller] = await ethers.getSigners();

    await auction.connect(buyer).submitBid(QUANTITY, BID_PRICE);
    await auction.connect(seller).submitAsk(QUANTITY, ASK_PRICE);

    await time.increase(ROUND_DURATION + 1);
    await auction.closeAuction(1);
    await auction.connect(operator).clearMarket(1);

    const round = await auction.getAuctionRound(1);
    expect(round.state).to.equal(3n); // SETTLED
    expect(round.matchedOrders).to.be.gt(0n);
  });
});
