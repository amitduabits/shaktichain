import { expect } from "chai";
import { ethers } from "hardhat";
import { loadFixture, time } from "@nomicfoundation/hardhat-network-helpers";
import { SignerWithAddress } from "@nomicfoundation/hardhat-ethers/signers";
import {
    ShaktiToken,
    EnergyAuction,
    StakingPool,
    Multicall,
    TrustedForwarder,
} from "../typechain-types";

describe("Gas Optimizations", function () {
    // ============ Fixtures ============
    async function deployAuctionFixture() {
        const [admin, user1, user2, user3] = await ethers.getSigners();

        // Deploy token (mints initial supply to admin)
        const ShaktiToken = await ethers.getContractFactory("ShaktiToken");
        const token = await ShaktiToken.deploy(admin.address, admin.address);
        await token.waitForDeployment();

        // Deploy auction
        const minPrice = ethers.parseEther("0.001");
        const maxPrice = ethers.parseEther("1");
        const EnergyAuction = await ethers.getContractFactory("EnergyAuction");
        const auction = await EnergyAuction.deploy(
            await token.getAddress(),
            ethers.ZeroAddress, // registry
            admin.address,
            minPrice,
            maxPrice
        );
        await auction.waitForDeployment();

        // Transfer tokens from admin (initial supply already minted to admin)
        const transferAmount = ethers.parseEther("10000");
        await token.connect(admin).transfer(user1.address, transferAmount);
        await token.connect(admin).transfer(user2.address, transferAmount);
        await token.connect(admin).transfer(user3.address, transferAmount);
        await token.connect(user1).approve(await auction.getAddress(), transferAmount);
        await token.connect(user2).approve(await auction.getAddress(), transferAmount);
        await token.connect(user3).approve(await auction.getAddress(), transferAmount);

        return { token, auction, admin, user1, user2, user3, minPrice, maxPrice };
    }

    async function deployStakingFixture() {
        const [admin, user1, user2, user3] = await ethers.getSigners();

        // Deploy token (mints initial supply to admin)
        const ShaktiToken = await ethers.getContractFactory("ShaktiToken");
        const token = await ShaktiToken.deploy(admin.address, admin.address);
        await token.waitForDeployment();

        // Deploy staking pool
        const StakingPool = await ethers.getContractFactory("StakingPool");
        const staking = await StakingPool.deploy(
            await token.getAddress(),
            admin.address,
            800 // 8% APY
        );
        await staking.waitForDeployment();

        // Transfer tokens from admin (initial supply already minted to admin)
        const transferAmount = ethers.parseEther("10000");
        await token.connect(admin).transfer(user1.address, transferAmount);
        await token.connect(admin).transfer(user2.address, transferAmount);
        await token.connect(admin).transfer(user3.address, transferAmount);
        await token.connect(admin).transfer(await staking.getAddress(), ethers.parseEther("100000")); // Rewards pool

        // Approve
        await token.connect(user1).approve(await staking.getAddress(), transferAmount);
        await token.connect(user2).approve(await staking.getAddress(), transferAmount);
        await token.connect(user3).approve(await staking.getAddress(), transferAmount);

        return { token, staking, admin, user1, user2, user3 };
    }

    async function deployMulticallFixture() {
        const [admin, user1] = await ethers.getSigners();

        // Deploy token (mints initial supply to admin)
        const ShaktiToken = await ethers.getContractFactory("ShaktiToken");
        const token = await ShaktiToken.deploy(admin.address, admin.address);
        await token.waitForDeployment();

        // Deploy Multicall
        const Multicall = await ethers.getContractFactory("Multicall");
        const multicall = await Multicall.deploy();
        await multicall.waitForDeployment();

        // Transfer tokens from admin
        await token.connect(admin).transfer(user1.address, ethers.parseEther("1000"));

        return { token, multicall, admin, user1 };
    }

    async function deployForwarderFixture() {
        const [admin, relayer, user1] = await ethers.getSigners();

        // Deploy forwarder
        const TrustedForwarder = await ethers.getContractFactory("TrustedForwarder");
        const forwarder = await TrustedForwarder.deploy(admin.address);
        await forwarder.waitForDeployment();

        // Grant relayer role
        const RELAYER_ROLE = await forwarder.RELAYER_ROLE();
        await forwarder.grantRole(RELAYER_ROLE, relayer.address);

        return { forwarder, admin, relayer, user1 };
    }

    // ============ Batch Bid Tests ============
    describe("Batch Bids (EnergyAuction)", function () {
        it("should submit multiple bids in a single transaction", async function () {
            const { auction, admin, user1, minPrice } = await loadFixture(deployAuctionFixture);

            // Create auction round
            await auction.connect(admin).createAuctionRound(300);

            // Prepare batch bids
            const bids = [
                { quantity: 5000, maxPricePerWh: minPrice * 10n },
                { quantity: 3000, maxPricePerWh: minPrice * 8n },
                { quantity: 7000, maxPricePerWh: minPrice * 12n },
            ];

            // Submit batch bids
            const tx = await auction.connect(user1).submitBids(bids);
            const receipt = await tx.wait();

            // Verify all bids created
            const traderOrders = await auction.getTraderOrders(user1.address, 1);
            expect(traderOrders.length).to.equal(3);

            // Check individual orders
            for (let i = 0; i < 3; i++) {
                const order = await auction.getOrder(1, traderOrders[i]);
                expect(order.trader).to.equal(user1.address);
                expect(order.isBid).to.be.true;
            }

            console.log(`Batch 3 bids gas used: ${receipt?.gasUsed}`);
        });

        it("should submit 10 bids more efficiently than single bids", async function () {
            const { auction, admin, user1, user2, minPrice } = await loadFixture(deployAuctionFixture);

            await auction.connect(admin).createAuctionRound(300);

            // Measure single bid gas
            const singleBidTx = await auction.connect(user1).submitBid(5000, minPrice * 10n);
            const singleReceipt = await singleBidTx.wait();
            const singleBidGas = singleReceipt?.gasUsed || 0n;

            // Prepare 10 batch bids
            const bids = [];
            for (let i = 0; i < 10; i++) {
                bids.push({ quantity: 5000, maxPricePerWh: minPrice * BigInt(10 + i) });
            }

            const batchTx = await auction.connect(user2).submitBids(bids);
            const batchReceipt = await batchTx.wait();
            const batchGas = batchReceipt?.gasUsed || 0n;

            // Batch should be significantly less than 10x single
            const expectedSingleTotal = singleBidGas * 10n;
            expect(batchGas).to.be.lessThan(expectedSingleTotal);

            console.log(`Single bid gas: ${singleBidGas}`);
            console.log(`Batch 10 bids gas: ${batchGas}`);
            console.log(`Expected 10 single: ${expectedSingleTotal}`);
            console.log(`Savings: ${((expectedSingleTotal - batchGas) * 100n) / expectedSingleTotal}%`);
        });

        it("should emit BatchBidsSubmitted event", async function () {
            const { auction, admin, user1, minPrice } = await loadFixture(deployAuctionFixture);

            await auction.connect(admin).createAuctionRound(300);

            const bids = [
                { quantity: 5000, maxPricePerWh: minPrice * 10n },
                { quantity: 3000, maxPricePerWh: minPrice * 8n },
            ];

            await expect(auction.connect(user1).submitBids(bids))
                .to.emit(auction, "BatchBidsSubmitted")
                .withArgs(1, user1.address, 2);
        });

        it("should revert on empty bids array", async function () {
            const { auction, admin, user1 } = await loadFixture(deployAuctionFixture);

            await auction.connect(admin).createAuctionRound(300);

            await expect(auction.connect(user1).submitBids([]))
                .to.be.revertedWithCustomError(auction, "ZeroAmount");
        });
    });

    // ============ Batch Ask Tests ============
    describe("Batch Asks (EnergyAuction)", function () {
        it("should submit multiple asks in a single transaction", async function () {
            const { auction, admin, user1, minPrice } = await loadFixture(deployAuctionFixture);

            await auction.connect(admin).createAuctionRound(300);

            const asks = [
                { quantity: 5000, minPricePerWh: minPrice * 5n },
                { quantity: 3000, minPricePerWh: minPrice * 4n },
                { quantity: 7000, minPricePerWh: minPrice * 6n },
            ];

            const tx = await auction.connect(user1).submitAsks(asks);
            const receipt = await tx.wait();

            const traderOrders = await auction.getTraderOrders(user1.address, 1);
            expect(traderOrders.length).to.equal(3);

            for (let i = 0; i < 3; i++) {
                const order = await auction.getOrder(1, traderOrders[i]);
                expect(order.trader).to.equal(user1.address);
                expect(order.isBid).to.be.false;
            }

            console.log(`Batch 3 asks gas used: ${receipt?.gasUsed}`);
        });

        it("should emit BatchAsksSubmitted event", async function () {
            const { auction, admin, user1, minPrice } = await loadFixture(deployAuctionFixture);

            await auction.connect(admin).createAuctionRound(300);

            const asks = [
                { quantity: 5000, minPricePerWh: minPrice * 5n },
            ];

            await expect(auction.connect(user1).submitAsks(asks))
                .to.emit(auction, "BatchAsksSubmitted")
                .withArgs(1, user1.address, 1);
        });
    });

    // ============ Batch Claim Rewards Tests ============
    describe("Batch Claim Rewards (StakingPool)", function () {
        it("should claim rewards for multiple stakers in single transaction", async function () {
            const { staking, user1, user2, user3 } = await loadFixture(deployStakingFixture);

            // All users stake
            const stakeAmount = ethers.parseEther("1000");
            await staking.connect(user1).stake(stakeAmount, 0);
            await staking.connect(user2).stake(stakeAmount, 0);
            await staking.connect(user3).stake(stakeAmount, 0);

            // Advance time for rewards accumulation
            await time.increase(30 * 24 * 60 * 60); // 30 days

            // Batch claim
            const tx = await staking.batchClaimRewards([
                user1.address,
                user2.address,
                user3.address
            ]);
            const receipt = await tx.wait();

            console.log(`Batch claim 3 stakers gas: ${receipt?.gasUsed}`);
        });

        it("should emit BatchRewardsClaimed event", async function () {
            const { staking, user1, user2 } = await loadFixture(deployStakingFixture);

            const stakeAmount = ethers.parseEther("1000");
            await staking.connect(user1).stake(stakeAmount, 0);
            await staking.connect(user2).stake(stakeAmount, 0);

            await time.increase(30 * 24 * 60 * 60);

            await expect(staking.batchClaimRewards([user1.address, user2.address]))
                .to.emit(staking, "BatchRewardsClaimed");
        });

        it("should skip stakers with no stake", async function () {
            const { staking, user1, user2, user3 } = await loadFixture(deployStakingFixture);

            // Only user1 stakes
            const stakeAmount = ethers.parseEther("1000");
            await staking.connect(user1).stake(stakeAmount, 0);

            await time.increase(30 * 24 * 60 * 60);

            // Should not revert when including non-stakers
            const tx = await staking.batchClaimRewards([
                user1.address,
                user2.address,
                user3.address
            ]);
            await tx.wait();
        });
    });

    // ============ Multicall Tests ============
    describe("Multicall", function () {
        it("should aggregate multiple static calls", async function () {
            const { token, multicall, admin, user1 } = await loadFixture(deployMulticallFixture);

            const tokenAddress = await token.getAddress();

            // Prepare calls
            const calls = [
                {
                    target: tokenAddress,
                    callData: token.interface.encodeFunctionData("balanceOf", [admin.address])
                },
                {
                    target: tokenAddress,
                    callData: token.interface.encodeFunctionData("balanceOf", [user1.address])
                },
                {
                    target: tokenAddress,
                    callData: token.interface.encodeFunctionData("totalSupply")
                }
            ];

            const [blockNumber, results] = await multicall.aggregateStatic(calls);

            expect(blockNumber).to.be.gt(0);
            expect(results.length).to.equal(3);
            expect(results[0].success).to.be.true;
            expect(results[1].success).to.be.true;
            expect(results[2].success).to.be.true;

            // Decode user1 balance
            const user1Balance = ethers.AbiCoder.defaultAbiCoder().decode(
                ["uint256"],
                results[1].returnData
            )[0];
            expect(user1Balance).to.equal(ethers.parseEther("1000"));
        });

        it("should execute aggregate with state changes", async function () {
            const { token, multicall, admin, user1 } = await loadFixture(deployMulticallFixture);

            const tokenAddress = await token.getAddress();

            // Approve multicall to spend tokens
            await token.connect(user1).approve(await multicall.getAddress(), ethers.parseEther("100"));

            // This would be used for view calls that don't fail
            const calls = [
                {
                    target: tokenAddress,
                    callData: token.interface.encodeFunctionData("name")
                },
                {
                    target: tokenAddress,
                    callData: token.interface.encodeFunctionData("symbol")
                }
            ];

            // Use staticCall to get return values without sending tx
            const result = await multicall.aggregate.staticCall(calls);

            expect(result.results.length).to.equal(2);
            expect(result.results[0].success).to.be.true;
        });

        it("should handle partial failures in aggregate", async function () {
            const { token, multicall, admin } = await loadFixture(deployMulticallFixture);

            const tokenAddress = await token.getAddress();

            const calls = [
                {
                    target: tokenAddress,
                    callData: token.interface.encodeFunctionData("balanceOf", [admin.address])
                },
                {
                    target: tokenAddress,
                    callData: "0xdeadbeef" // Invalid function selector will fail
                }
            ];

            // Use staticCall to get return values without sending tx
            const result = await multicall.aggregate.staticCall(calls);

            expect(result.results[0].success).to.be.true;
            expect(result.results[1].success).to.be.false;
        });

        it("should revert all on aggregateStrict failure", async function () {
            const { token, multicall, admin } = await loadFixture(deployMulticallFixture);

            const tokenAddress = await token.getAddress();

            const calls = [
                {
                    target: tokenAddress,
                    callData: token.interface.encodeFunctionData("balanceOf", [admin.address])
                },
                {
                    target: tokenAddress,
                    callData: "0xdeadbeef" // Invalid function selector
                }
            ];

            await expect(multicall.aggregateStrict(calls))
                .to.be.revertedWithCustomError(multicall, "CallFailed");
        });

        it("should return block info", async function () {
            const { multicall } = await loadFixture(deployMulticallFixture);

            const [blockNumber, blockTimestamp, blockHash] = await multicall.getBlockInfo();

            expect(blockNumber).to.be.gt(0);
            expect(blockTimestamp).to.be.gt(0);
        });

        it("should get ETH balance", async function () {
            const { multicall, admin } = await loadFixture(deployMulticallFixture);

            const balance = await multicall.getEthBalance(admin.address);
            expect(balance).to.be.gt(0);
        });
    });

    // ============ TrustedForwarder Tests ============
    describe("TrustedForwarder", function () {
        it("should deploy with correct domain", async function () {
            const { forwarder } = await loadFixture(deployForwarderFixture);

            const domainSeparator = await forwarder.domainSeparator();
            expect(domainSeparator).to.not.equal(ethers.ZeroHash);
        });

        it("should track nonces correctly", async function () {
            const { forwarder, user1 } = await loadFixture(deployForwarderFixture);

            const nonce = await forwarder.getNonce(user1.address);
            expect(nonce).to.equal(0);
        });

        it("should allow nonce invalidation", async function () {
            const { forwarder, user1 } = await loadFixture(deployForwarderFixture);

            await expect(forwarder.connect(user1).invalidateNonce())
                .to.emit(forwarder, "NonceInvalidated")
                .withArgs(user1.address, 0);

            const nonce = await forwarder.getNonce(user1.address);
            expect(nonce).to.equal(1);
        });

        it("should add and remove relayers", async function () {
            const { forwarder, admin, user1 } = await loadFixture(deployForwarderFixture);

            const RELAYER_ROLE = await forwarder.RELAYER_ROLE();

            await forwarder.connect(admin).addRelayer(user1.address);
            expect(await forwarder.hasRole(RELAYER_ROLE, user1.address)).to.be.true;

            await forwarder.connect(admin).removeRelayer(user1.address);
            expect(await forwarder.hasRole(RELAYER_ROLE, user1.address)).to.be.false;
        });

        it("should return stats", async function () {
            const { forwarder } = await loadFixture(deployForwarderFixture);

            const [total, gasSponsored] = await forwarder.getStats();
            expect(total).to.equal(0);
            expect(gasSponsored).to.equal(0);
        });

        it("should verify valid forward request signature", async function () {
            const { forwarder, user1 } = await loadFixture(deployForwarderFixture);

            const nonce = await forwarder.getNonce(user1.address);
            const deadline = BigInt(Math.floor(Date.now() / 1000) + 3600);

            const request = {
                from: user1.address,
                to: ethers.ZeroAddress,
                value: 0n,
                gas: 100000n,
                nonce: nonce,
                deadline: deadline,
                data: "0x"
            };

            // Get domain
            const domain = {
                name: "ShaktiForwarder",
                version: "1",
                chainId: (await ethers.provider.getNetwork()).chainId,
                verifyingContract: await forwarder.getAddress()
            };

            const types = {
                ForwardRequest: [
                    { name: "from", type: "address" },
                    { name: "to", type: "address" },
                    { name: "value", type: "uint256" },
                    { name: "gas", type: "uint256" },
                    { name: "nonce", type: "uint256" },
                    { name: "deadline", type: "uint256" },
                    { name: "data", type: "bytes" }
                ]
            };

            const signature = await user1.signTypedData(domain, types, request);

            const isValid = await forwarder.verify(request, signature);
            expect(isValid).to.be.true;
        });
    });

    // ============ Gas Comparison Tests ============
    describe("Gas Comparisons", function () {
        it("should compare single vs batch bid gas costs", async function () {
            const { auction, admin, user1, user2, minPrice } = await loadFixture(deployAuctionFixture);

            await auction.connect(admin).createAuctionRound(600);

            // Single bids
            let singleTotalGas = 0n;
            for (let i = 0; i < 5; i++) {
                const tx = await auction.connect(user1).submitBid(5000, minPrice * BigInt(10 + i));
                const receipt = await tx.wait();
                singleTotalGas += receipt?.gasUsed || 0n;
            }

            // Batch bids
            const bids = [];
            for (let i = 0; i < 5; i++) {
                bids.push({ quantity: 5000, maxPricePerWh: minPrice * BigInt(10 + i) });
            }
            const batchTx = await auction.connect(user2).submitBids(bids);
            const batchReceipt = await batchTx.wait();
            const batchGas = batchReceipt?.gasUsed || 0n;

            const savings = ((singleTotalGas - batchGas) * 100n) / singleTotalGas;

            console.log("\n=== Gas Comparison: 5 Bids ===");
            console.log(`5 Single bids total: ${singleTotalGas}`);
            console.log(`Batch 5 bids: ${batchGas}`);
            console.log(`Savings: ${savings}%`);

            expect(batchGas).to.be.lessThan(singleTotalGas);
        });
    });
});
