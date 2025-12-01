import { expect } from "chai";
import { ethers } from "hardhat";
import { time } from "@nomicfoundation/hardhat-network-helpers";
import { HardhatEthersSigner } from "@nomicfoundation/hardhat-ethers/signers";
import { EnergyVerification } from "../typechain-types";

describe("EnergyVerification", function () {
    let verification: EnergyVerification;

    let admin: HardhatEthersSigner;
    let escrow: HardhatEthersSigner;
    let oracle: HardhatEthersSigner;
    let arbiter: HardhatEthersSigner;
    let discom: HardhatEthersSigner;
    let seller: HardhatEthersSigner;
    let buyer: HardhatEthersSigner;
    let other: HardhatEthersSigner;

    const DELIVERY_WINDOW = 4 * 60 * 60; // 4 hours
    const QUANTITY_TOLERANCE = 500; // 5%
    const PEER_THRESHOLD = ethers.parseEther("10"); // 10 kWh

    const TRADE_ID = 1;
    const QUANTITY = ethers.parseEther("50"); // 50 kWh
    const VALUE = ethers.parseEther("500"); // 500 SHAKTI
    const SMALL_QUANTITY = ethers.parseEther("5"); // 5 kWh for peer attestation

    beforeEach(async function () {
        [admin, escrow, oracle, arbiter, discom, seller, buyer, other] = await ethers.getSigners();

        // Deploy EnergyVerification
        const EnergyVerification = await ethers.getContractFactory("EnergyVerification");
        verification = await EnergyVerification.deploy(admin.address);
        await verification.waitForDeployment();

        // Setup roles
        await verification.connect(admin).grantRole(await verification.ESCROW_ROLE(), escrow.address);
        await verification.connect(admin).grantRole(await verification.ORACLE_ROLE(), oracle.address);
        await verification.connect(admin).grantRole(await verification.ARBITER_ROLE(), arbiter.address);

        // Trust DISCOM
        await verification.connect(admin).setDISCOMTrust(discom.address, true);
    });

    // Helper function to create DISCOM signature
    async function createDISCOMSignature(
        tradeId: number,
        sellerAddr: string,
        buyerAddr: string,
        quantity: bigint
    ): Promise<string> {
        const chainId = (await ethers.provider.getNetwork()).chainId;
        const messageHash = ethers.solidityPackedKeccak256(
            ["uint256", "address", "address", "uint256", "uint256"],
            [tradeId, sellerAddr, buyerAddr, quantity, chainId]
        );
        return discom.signMessage(ethers.getBytes(messageHash));
    }

    // ============ Deployment Tests ============

    describe("Deployment", function () {
        it("should deploy with correct admin", async function () {
            expect(await verification.hasRole(await verification.DEFAULT_ADMIN_ROLE(), admin.address)).to.be.true;
        });

        it("should revert if admin is zero address", async function () {
            const EnergyVerification = await ethers.getContractFactory("EnergyVerification");
            await expect(EnergyVerification.deploy(ethers.ZeroAddress))
                .to.be.revertedWithCustomError(verification, "ZeroAddress");
        });

        it("should set correct constants", async function () {
            expect(await verification.DELIVERY_WINDOW()).to.equal(4 * 60 * 60);
            expect(await verification.QUANTITY_TOLERANCE()).to.equal(500);
            expect(await verification.PEER_ATTESTATION_THRESHOLD()).to.equal(ethers.parseEther("10"));
            expect(await verification.NON_DELIVERY_SLASH()).to.equal(1000);
            expect(await verification.FALSE_DISPUTE_SLASH()).to.equal(500);
        });
    });

    // ============ Trade Registration Tests ============

    describe("Trade Registration", function () {
        it("should register a new trade", async function () {
            await verification.connect(escrow).registerTrade(
                TRADE_ID,
                seller.address,
                buyer.address,
                QUANTITY,
                VALUE,
                discom.address
            );

            const trade = await verification.getTrade(TRADE_ID);
            expect(trade.seller).to.equal(seller.address);
            expect(trade.buyer).to.equal(buyer.address);
            expect(trade.quantity).to.equal(QUANTITY);
            expect(trade.value).to.equal(VALUE);
            expect(trade.status).to.equal(0); // Pending
        });

        it("should emit TradeRegistered event", async function () {
            const tx = await verification.connect(escrow).registerTrade(
                TRADE_ID,
                seller.address,
                buyer.address,
                QUANTITY,
                VALUE,
                discom.address
            );

            await expect(tx)
                .to.emit(verification, "TradeRegistered")
                .withArgs(
                    TRADE_ID,
                    seller.address,
                    buyer.address,
                    QUANTITY,
                    VALUE,
                    await time.latest() + DELIVERY_WINDOW
                );
        });

        it("should update user stats", async function () {
            await verification.connect(escrow).registerTrade(
                TRADE_ID,
                seller.address,
                buyer.address,
                QUANTITY,
                VALUE,
                discom.address
            );

            const sellerStats = await verification.getUserStats(seller.address);
            const buyerStats = await verification.getUserStats(buyer.address);

            expect(sellerStats.totalTrades).to.equal(1);
            expect(buyerStats.totalTrades).to.equal(1);
        });

        it("should revert if not escrow", async function () {
            await expect(verification.connect(other).registerTrade(
                TRADE_ID,
                seller.address,
                buyer.address,
                QUANTITY,
                VALUE,
                discom.address
            )).to.be.reverted;
        });

        it("should revert for zero addresses", async function () {
            await expect(verification.connect(escrow).registerTrade(
                TRADE_ID,
                ethers.ZeroAddress,
                buyer.address,
                QUANTITY,
                VALUE,
                discom.address
            )).to.be.revertedWithCustomError(verification, "ZeroAddress");
        });

        it("should revert for zero quantity", async function () {
            await expect(verification.connect(escrow).registerTrade(
                TRADE_ID,
                seller.address,
                buyer.address,
                0,
                VALUE,
                discom.address
            )).to.be.revertedWithCustomError(verification, "ZeroAmount");
        });

        it("should revert for duplicate trade ID", async function () {
            await verification.connect(escrow).registerTrade(
                TRADE_ID,
                seller.address,
                buyer.address,
                QUANTITY,
                VALUE,
                discom.address
            );

            await expect(verification.connect(escrow).registerTrade(
                TRADE_ID,
                seller.address,
                buyer.address,
                QUANTITY,
                VALUE,
                discom.address
            )).to.be.revertedWithCustomError(verification, "TradeAlreadyExists");
        });
    });

    // ============ DISCOM Attestation Tests ============

    describe("DISCOM Attestation", function () {
        beforeEach(async function () {
            await verification.connect(escrow).registerTrade(
                TRADE_ID,
                seller.address,
                buyer.address,
                QUANTITY,
                VALUE,
                discom.address
            );
        });

        it("should report delivery with valid DISCOM signature", async function () {
            const signature = await createDISCOMSignature(
                TRADE_ID,
                seller.address,
                buyer.address,
                QUANTITY
            );

            await verification.reportDeliveryWithDISCOM(TRADE_ID, QUANTITY, signature);

            const trade = await verification.getTrade(TRADE_ID);
            expect(trade.status).to.equal(2); // Confirmed (auto-confirmed within tolerance)
            expect(trade.deliveredQuantity).to.equal(QUANTITY);
            expect(trade.method).to.equal(1); // DISCOMAttestation
        });

        it("should emit DeliveryReported and DeliveryConfirmed events", async function () {
            const signature = await createDISCOMSignature(
                TRADE_ID,
                seller.address,
                buyer.address,
                QUANTITY
            );

            await expect(verification.reportDeliveryWithDISCOM(TRADE_ID, QUANTITY, signature))
                .to.emit(verification, "DeliveryReported")
                .and.to.emit(verification, "DeliveryConfirmed");
        });

        it("should accept delivery within tolerance", async function () {
            // 5% tolerance means 47.5 - 52.5 kWh is acceptable for 50 kWh
            const deliveredQuantity = ethers.parseEther("48"); // Within tolerance

            const signature = await createDISCOMSignature(
                TRADE_ID,
                seller.address,
                buyer.address,
                deliveredQuantity
            );

            await verification.reportDeliveryWithDISCOM(TRADE_ID, deliveredQuantity, signature);

            const trade = await verification.getTrade(TRADE_ID);
            expect(trade.status).to.equal(2); // Confirmed
        });

        it("should revert for untrusted DISCOM", async function () {
            // Create signature from untrusted signer
            const chainId = (await ethers.provider.getNetwork()).chainId;
            const messageHash = ethers.solidityPackedKeccak256(
                ["uint256", "address", "address", "uint256", "uint256"],
                [TRADE_ID, seller.address, buyer.address, QUANTITY, chainId]
            );
            const signature = await other.signMessage(ethers.getBytes(messageHash));

            await expect(verification.reportDeliveryWithDISCOM(TRADE_ID, QUANTITY, signature))
                .to.be.revertedWithCustomError(verification, "UntrustedDISCOM");
        });

        it("should revert for quantity outside tolerance", async function () {
            // More than 5% deviation
            const deliveredQuantity = ethers.parseEther("40"); // 20% under

            const signature = await createDISCOMSignature(
                TRADE_ID,
                seller.address,
                buyer.address,
                deliveredQuantity
            );

            await expect(verification.reportDeliveryWithDISCOM(TRADE_ID, deliveredQuantity, signature))
                .to.be.revertedWithCustomError(verification, "QuantityMismatch");
        });

        it("should revert after delivery window expires", async function () {
            await time.increase(DELIVERY_WINDOW + 1);

            const signature = await createDISCOMSignature(
                TRADE_ID,
                seller.address,
                buyer.address,
                QUANTITY
            );

            await expect(verification.reportDeliveryWithDISCOM(TRADE_ID, QUANTITY, signature))
                .to.be.revertedWithCustomError(verification, "DeliveryWindowExpired");
        });

        it("should store DISCOM signature", async function () {
            const signature = await createDISCOMSignature(
                TRADE_ID,
                seller.address,
                buyer.address,
                QUANTITY
            );

            await verification.reportDeliveryWithDISCOM(TRADE_ID, QUANTITY, signature);

            const storedSig = await verification.discomSignatures(TRADE_ID);
            expect(storedSig).to.equal(signature);
        });
    });

    // ============ Oracle Report Tests ============

    describe("Smart Meter Oracle", function () {
        beforeEach(async function () {
            await verification.connect(escrow).registerTrade(
                TRADE_ID,
                seller.address,
                buyer.address,
                QUANTITY,
                VALUE,
                discom.address
            );
        });

        it("should accept oracle delivery report", async function () {
            const meterHash = ethers.keccak256(ethers.toUtf8Bytes("meter-reading-123"));

            await verification.connect(oracle).reportDeliveryFromOracle(
                TRADE_ID,
                QUANTITY,
                meterHash
            );

            const trade = await verification.getTrade(TRADE_ID);
            expect(trade.status).to.equal(2); // Confirmed
            expect(trade.method).to.equal(2); // SmartMeterOracle
            expect(trade.meterReadingHash).to.equal(meterHash);
        });

        it("should emit OracleReportReceived event", async function () {
            const meterHash = ethers.keccak256(ethers.toUtf8Bytes("meter-reading-123"));

            await expect(verification.connect(oracle).reportDeliveryFromOracle(
                TRADE_ID,
                QUANTITY,
                meterHash
            ))
                .to.emit(verification, "OracleReportReceived")
                .withArgs(TRADE_ID, QUANTITY, meterHash);
        });

        it("should revert if not oracle", async function () {
            const meterHash = ethers.keccak256(ethers.toUtf8Bytes("meter-reading"));

            await expect(verification.connect(other).reportDeliveryFromOracle(
                TRADE_ID,
                QUANTITY,
                meterHash
            )).to.be.reverted;
        });
    });

    // ============ Peer Attestation Tests ============

    describe("Peer Attestation", function () {
        beforeEach(async function () {
            // Register small trade for peer attestation
            await verification.connect(escrow).registerTrade(
                TRADE_ID,
                seller.address,
                buyer.address,
                SMALL_QUANTITY,
                VALUE,
                discom.address
            );
        });

        it("should allow buyer to confirm receipt for small trades", async function () {
            await verification.connect(buyer).confirmReceipt(TRADE_ID);

            const trade = await verification.getTrade(TRADE_ID);
            expect(trade.status).to.equal(2); // Confirmed
            expect(trade.method).to.equal(3); // PeerAttestation
        });

        it("should emit DeliveryConfirmed event", async function () {
            await expect(verification.connect(buyer).confirmReceipt(TRADE_ID))
                .to.emit(verification, "DeliveryConfirmed")
                .withArgs(TRADE_ID, buyer.address, 3);
        });

        it("should revert for non-buyer", async function () {
            await expect(verification.connect(seller).confirmReceipt(TRADE_ID))
                .to.be.revertedWithCustomError(verification, "NotBuyer");
        });

        it("should revert for large trades", async function () {
            // Register large trade
            await verification.connect(escrow).registerTrade(
                2,
                seller.address,
                buyer.address,
                QUANTITY, // 50 kWh > 10 kWh threshold
                VALUE,
                discom.address
            );

            await expect(verification.connect(buyer).confirmReceipt(2))
                .to.be.revertedWithCustomError(verification, "PeerAttestationNotAllowed");
        });

        it("should update successful deliveries", async function () {
            await verification.connect(buyer).confirmReceipt(TRADE_ID);

            const stats = await verification.getUserStats(seller.address);
            expect(stats.successfulDeliveries).to.equal(1);
        });
    });

    // ============ Dispute Tests ============

    describe("Disputes", function () {
        beforeEach(async function () {
            await verification.connect(escrow).registerTrade(
                TRADE_ID,
                seller.address,
                buyer.address,
                QUANTITY,
                VALUE,
                discom.address
            );
        });

        it("should allow buyer to raise non-delivery after deadline", async function () {
            await time.increase(DELIVERY_WINDOW + 1);

            await verification.connect(buyer).raiseNonDelivery(TRADE_ID);

            const trade = await verification.getTrade(TRADE_ID);
            expect(trade.status).to.equal(3); // Disputed
        });

        it("should emit DeliveryDisputed event", async function () {
            await time.increase(DELIVERY_WINDOW + 1);

            await expect(verification.connect(buyer).raiseNonDelivery(TRADE_ID))
                .to.emit(verification, "DeliveryDisputed")
                .withArgs(TRADE_ID, buyer.address, "Non-delivery claimed by buyer");
        });

        it("should increment disputes raised", async function () {
            await time.increase(DELIVERY_WINDOW + 1);
            await verification.connect(buyer).raiseNonDelivery(TRADE_ID);

            const stats = await verification.getUserStats(buyer.address);
            expect(stats.disputesRaised).to.equal(1);
        });

        it("should revert if not buyer", async function () {
            await time.increase(DELIVERY_WINDOW + 1);

            await expect(verification.connect(seller).raiseNonDelivery(TRADE_ID))
                .to.be.revertedWithCustomError(verification, "NotBuyer");
        });

        it("should revert before deadline", async function () {
            await expect(verification.connect(buyer).raiseNonDelivery(TRADE_ID))
                .to.be.revertedWithCustomError(verification, "DeliveryWindowNotExpired");
        });

        it("should revert for confirmed trade", async function () {
            const signature = await createDISCOMSignature(
                TRADE_ID,
                seller.address,
                buyer.address,
                QUANTITY
            );

            await verification.reportDeliveryWithDISCOM(TRADE_ID, QUANTITY, signature);

            await expect(verification.connect(buyer).raiseNonDelivery(TRADE_ID))
                .to.be.revertedWithCustomError(verification, "DeliveryAlreadyConfirmed");
        });
    });

    // ============ Dispute Resolution Tests ============

    describe("Dispute Resolution", function () {
        beforeEach(async function () {
            await verification.connect(escrow).registerTrade(
                TRADE_ID,
                seller.address,
                buyer.address,
                QUANTITY,
                VALUE,
                discom.address
            );

            await time.increase(DELIVERY_WINDOW + 1);
            await verification.connect(buyer).raiseNonDelivery(TRADE_ID);
        });

        it("should resolve in favor of delivery (false dispute)", async function () {
            await verification.connect(arbiter).resolveDelivery(TRADE_ID, 1, 0); // DeliveryConfirmed

            const trade = await verification.getTrade(TRADE_ID);
            expect(trade.status).to.equal(4); // Resolved
            expect(trade.resolution).to.equal(1); // DeliveryConfirmed
            expect(trade.buyerSlashed).to.be.true;
        });

        it("should resolve as non-delivery", async function () {
            await verification.connect(arbiter).resolveDelivery(TRADE_ID, 2, 0); // NonDelivery

            const trade = await verification.getTrade(TRADE_ID);
            expect(trade.status).to.equal(4); // Resolved
            expect(trade.resolution).to.equal(2); // NonDelivery
            expect(trade.sellerSlashed).to.be.true;
        });

        it("should resolve as partial delivery", async function () {
            const partialQty = ethers.parseEther("30"); // 30 kWh of 50 kWh

            await verification.connect(arbiter).resolveDelivery(TRADE_ID, 3, partialQty); // PartialDelivery

            const trade = await verification.getTrade(TRADE_ID);
            expect(trade.status).to.equal(4); // Resolved
            expect(trade.resolution).to.equal(3); // PartialDelivery
            expect(trade.deliveredQuantity).to.equal(partialQty);
        });

        it("should emit DeliveryResolved event", async function () {
            await expect(verification.connect(arbiter).resolveDelivery(TRADE_ID, 2, 0))
                .to.emit(verification, "DeliveryResolved")
                .withArgs(TRADE_ID, 2, arbiter.address);
        });

        it("should revert if not arbiter", async function () {
            await expect(verification.connect(other).resolveDelivery(TRADE_ID, 2, 0))
                .to.be.reverted;
        });

        it("should revert if not disputed", async function () {
            await verification.connect(escrow).registerTrade(
                2,
                seller.address,
                buyer.address,
                QUANTITY,
                VALUE,
                discom.address
            );

            await expect(verification.connect(arbiter).resolveDelivery(2, 2, 0))
                .to.be.revertedWithCustomError(verification, "TradeNotDisputed");
        });
    });

    // ============ Slashing Tests ============

    describe("Slashing", function () {
        beforeEach(async function () {
            await verification.connect(escrow).registerTrade(
                TRADE_ID,
                seller.address,
                buyer.address,
                QUANTITY,
                VALUE,
                discom.address
            );
        });

        it("should slash seller for non-delivery", async function () {
            await time.increase(DELIVERY_WINDOW + 1);
            await verification.connect(buyer).raiseNonDelivery(TRADE_ID);
            await verification.connect(arbiter).resolveDelivery(TRADE_ID, 2, 0); // NonDelivery

            const stats = await verification.getUserStats(seller.address);
            const expectedSlash = (VALUE * 1000n) / 10000n; // 10%
            expect(stats.totalSlashed).to.equal(expectedSlash);
        });

        it("should slash buyer for false dispute", async function () {
            await time.increase(DELIVERY_WINDOW + 1);
            await verification.connect(buyer).raiseNonDelivery(TRADE_ID);
            await verification.connect(arbiter).resolveDelivery(TRADE_ID, 1, 0); // DeliveryConfirmed

            const stats = await verification.getUserStats(buyer.address);
            const expectedSlash = (VALUE * 500n) / 10000n; // 5%
            expect(stats.totalSlashed).to.equal(expectedSlash);
        });

        it("should emit SlashApplied event", async function () {
            await time.increase(DELIVERY_WINDOW + 1);
            await verification.connect(buyer).raiseNonDelivery(TRADE_ID);

            const expectedSlash = (VALUE * 1000n) / 10000n;

            await expect(verification.connect(arbiter).resolveDelivery(TRADE_ID, 2, 0))
                .to.emit(verification, "SlashApplied")
                .withArgs(TRADE_ID, seller.address, expectedSlash, "Non-delivery");
        });

        it("should record slash in history", async function () {
            await time.increase(DELIVERY_WINDOW + 1);
            await verification.connect(buyer).raiseNonDelivery(TRADE_ID);
            await verification.connect(arbiter).resolveDelivery(TRADE_ID, 2, 0);

            expect(await verification.getSlashHistoryLength()).to.equal(1);

            const record = await verification.getSlashRecord(0);
            expect(record.user).to.equal(seller.address);
            expect(record.tradeId).to.equal(TRADE_ID);
        });

        it("should update total slashed", async function () {
            await time.increase(DELIVERY_WINDOW + 1);
            await verification.connect(buyer).raiseNonDelivery(TRADE_ID);
            await verification.connect(arbiter).resolveDelivery(TRADE_ID, 2, 0);

            const stats = await verification.getVerificationStats();
            const expectedSlash = (VALUE * 1000n) / 10000n;
            expect(stats.slashed).to.equal(expectedSlash);
        });
    });

    // ============ Banning Tests ============

    describe("Banning", function () {
        it("should temp ban after 3 offenses", async function () {
            // Create and fail 3 trades
            for (let i = 1; i <= 3; i++) {
                await verification.connect(escrow).registerTrade(
                    i,
                    seller.address,
                    buyer.address,
                    QUANTITY,
                    VALUE,
                    discom.address
                );

                await time.increase(DELIVERY_WINDOW + 1);
                await verification.markDeliveryFailed(i);
            }

            const [banned, permanent, expiry] = await verification.isBanned(seller.address);
            expect(banned).to.be.true;
            expect(permanent).to.be.false;
            expect(expiry).to.be.gt(0);
        });

        it("should perm ban after 5 offenses", async function () {
            // Create and fail 5 trades
            // After 3 offenses user gets temp-banned, so we need to lift the ban to continue
            for (let i = 1; i <= 5; i++) {
                // Lift ban before trade 4 and 5 since temp ban triggers at 3
                if (i >= 4) {
                    await verification.connect(admin).liftBan(seller.address);
                }

                await verification.connect(escrow).registerTrade(
                    i,
                    seller.address,
                    buyer.address,
                    QUANTITY,
                    VALUE,
                    discom.address
                );

                await time.increase(DELIVERY_WINDOW + 1);
                await verification.markDeliveryFailed(i);
            }

            const [banned, permanent] = await verification.isBanned(seller.address);
            expect(banned).to.be.true;
            expect(permanent).to.be.true;
        });

        it("should emit UserBanned event", async function () {
            // Fail 3 trades to trigger temp ban
            for (let i = 1; i <= 2; i++) {
                await verification.connect(escrow).registerTrade(
                    i,
                    seller.address,
                    buyer.address,
                    QUANTITY,
                    VALUE,
                    discom.address
                );

                await time.increase(DELIVERY_WINDOW + 1);
                await verification.markDeliveryFailed(i);
            }

            await verification.connect(escrow).registerTrade(
                3,
                seller.address,
                buyer.address,
                QUANTITY,
                VALUE,
                discom.address
            );

            await time.increase(DELIVERY_WINDOW + 1);

            await expect(verification.markDeliveryFailed(3))
                .to.emit(verification, "UserBanned");
        });

        it("should prevent banned users from trading", async function () {
            // Permanently ban seller
            for (let i = 1; i <= 5; i++) {
                // Lift ban before trade 4 and 5 to continue accumulating offenses
                if (i >= 4) {
                    await verification.connect(admin).liftBan(seller.address);
                }

                await verification.connect(escrow).registerTrade(
                    i,
                    seller.address,
                    buyer.address,
                    QUANTITY,
                    VALUE,
                    discom.address
                );

                await time.increase(DELIVERY_WINDOW + 1);
                await verification.markDeliveryFailed(i);
            }

            await expect(verification.connect(escrow).registerTrade(
                6,
                seller.address,
                buyer.address,
                QUANTITY,
                VALUE,
                discom.address
            )).to.be.revertedWithCustomError(verification, "UserIsBanned");
        });

        it("should allow admin to lift temp ban", async function () {
            // Create temp ban
            for (let i = 1; i <= 3; i++) {
                await verification.connect(escrow).registerTrade(
                    i,
                    seller.address,
                    buyer.address,
                    QUANTITY,
                    VALUE,
                    discom.address
                );

                await time.increase(DELIVERY_WINDOW + 1);
                await verification.markDeliveryFailed(i);
            }

            await verification.connect(admin).liftBan(seller.address);

            const [banned] = await verification.isBanned(seller.address);
            expect(banned).to.be.false;
        });
    });

    // ============ Mark Delivery Failed Tests ============

    describe("Mark Delivery Failed", function () {
        beforeEach(async function () {
            await verification.connect(escrow).registerTrade(
                TRADE_ID,
                seller.address,
                buyer.address,
                QUANTITY,
                VALUE,
                discom.address
            );
        });

        it("should mark delivery as failed after deadline", async function () {
            await time.increase(DELIVERY_WINDOW + 1);
            await verification.markDeliveryFailed(TRADE_ID);

            const trade = await verification.getTrade(TRADE_ID);
            expect(trade.status).to.equal(5); // Failed
        });

        it("should slash seller on failed delivery", async function () {
            await time.increase(DELIVERY_WINDOW + 1);
            await verification.markDeliveryFailed(TRADE_ID);

            const trade = await verification.getTrade(TRADE_ID);
            expect(trade.sellerSlashed).to.be.true;
        });

        it("should revert before deadline", async function () {
            await expect(verification.markDeliveryFailed(TRADE_ID))
                .to.be.revertedWithCustomError(verification, "DeliveryWindowNotExpired");
        });

        it("should revert if not pending", async function () {
            const signature = await createDISCOMSignature(
                TRADE_ID,
                seller.address,
                buyer.address,
                QUANTITY
            );

            await verification.reportDeliveryWithDISCOM(TRADE_ID, QUANTITY, signature);

            await time.increase(DELIVERY_WINDOW + 1);

            await expect(verification.markDeliveryFailed(TRADE_ID))
                .to.be.revertedWithCustomError(verification, "DeliveryNotPending");
        });
    });

    // ============ View Functions Tests ============

    describe("View Functions", function () {
        beforeEach(async function () {
            await verification.connect(escrow).registerTrade(
                TRADE_ID,
                seller.address,
                buyer.address,
                QUANTITY,
                VALUE,
                discom.address
            );
        });

        it("should return delivery status", async function () {
            expect(await verification.getDeliveryStatus(TRADE_ID)).to.equal(0); // Pending
        });

        it("should return delivery time remaining", async function () {
            const remaining = await verification.getDeliveryTimeRemaining(TRADE_ID);
            expect(remaining).to.be.closeTo(BigInt(DELIVERY_WINDOW), 10n);
        });

        it("should return 0 time remaining after deadline", async function () {
            await time.increase(DELIVERY_WINDOW + 1);
            expect(await verification.getDeliveryTimeRemaining(TRADE_ID)).to.equal(0);
        });

        it("should return user reputation", async function () {
            // New user starts at 100%
            expect(await verification.getUserReputation(seller.address)).to.equal(100);
        });

        it("should return verification stats", async function () {
            const stats = await verification.getVerificationStats();
            expect(stats.total).to.equal(1);
            expect(stats.successful).to.equal(0);
            expect(stats.failed).to.equal(0);
        });

        it("should return all trade IDs", async function () {
            const ids = await verification.getAllTradeIds();
            expect(ids.length).to.equal(1);
            expect(ids[0]).to.equal(TRADE_ID);
        });

        it("should return trades by user", async function () {
            const sellerTrades = await verification.getTradesByUser(seller.address);
            const buyerTrades = await verification.getTradesByUser(buyer.address);

            expect(sellerTrades.length).to.equal(1);
            expect(buyerTrades.length).to.equal(1);
        });

        it("should return pending trades count", async function () {
            expect(await verification.getPendingTradesCount()).to.equal(1);

            const signature = await createDISCOMSignature(
                TRADE_ID,
                seller.address,
                buyer.address,
                QUANTITY
            );
            await verification.reportDeliveryWithDISCOM(TRADE_ID, QUANTITY, signature);

            expect(await verification.getPendingTradesCount()).to.equal(0);
        });

        it("should check DISCOM trust status", async function () {
            expect(await verification.isDISCOMTrusted(discom.address)).to.be.true;
            expect(await verification.isDISCOMTrusted(other.address)).to.be.false;
        });
    });

    // ============ Admin Functions Tests ============

    describe("Admin Functions", function () {
        it("should set DISCOM trust", async function () {
            await verification.connect(admin).setDISCOMTrust(other.address, true);
            expect(await verification.isDISCOMTrusted(other.address)).to.be.true;

            await verification.connect(admin).setDISCOMTrust(other.address, false);
            expect(await verification.isDISCOMTrusted(other.address)).to.be.false;
        });

        it("should emit DISCOMTrustUpdated event", async function () {
            await expect(verification.connect(admin).setDISCOMTrust(other.address, true))
                .to.emit(verification, "DISCOMTrustUpdated")
                .withArgs(other.address, true);
        });

        it("should set escrow contract", async function () {
            await verification.connect(admin).setEscrowContract(other.address);
            expect(await verification.escrowContract()).to.equal(other.address);
        });

        it("should set staking contract", async function () {
            await verification.connect(admin).setStakingContract(other.address);
            expect(await verification.stakingContract()).to.equal(other.address);
        });

        it("should pause and unpause", async function () {
            await verification.connect(admin).pause();
            expect(await verification.paused()).to.be.true;

            await verification.connect(admin).unpause();
            expect(await verification.paused()).to.be.false;
        });
    });

    // ============ Reputation Tests ============

    describe("Reputation", function () {
        it("should decrease reputation with failed deliveries", async function () {
            // Complete one successful trade
            await verification.connect(escrow).registerTrade(
                1,
                seller.address,
                buyer.address,
                SMALL_QUANTITY,
                VALUE,
                discom.address
            );
            await verification.connect(buyer).confirmReceipt(1);

            // Fail one trade
            await verification.connect(escrow).registerTrade(
                2,
                seller.address,
                buyer.address,
                QUANTITY,
                VALUE,
                discom.address
            );
            await time.increase(DELIVERY_WINDOW + 1);
            await verification.markDeliveryFailed(2);

            // Reputation should be 50% (1 success out of 2 total)
            const reputation = await verification.getUserReputation(seller.address);
            expect(reputation).to.equal(50);
        });

        it("should penalize lost disputes", async function () {
            // First, establish buyer's reputation with a successful delivery as seller
            // This gives them completed trades so the penalty can apply
            await verification.connect(escrow).registerTrade(
                100, // Different trade ID
                buyer.address, // buyer acts as seller here
                other.address,
                SMALL_QUANTITY,
                VALUE,
                discom.address
            );
            await verification.connect(other).confirmReceipt(100);

            // Now register original trade
            await verification.connect(escrow).registerTrade(
                TRADE_ID,
                seller.address,
                buyer.address,
                QUANTITY,
                VALUE,
                discom.address
            );

            await time.increase(DELIVERY_WINDOW + 1);
            await verification.connect(buyer).raiseNonDelivery(TRADE_ID);

            // Resolve in favor of seller (buyer loses dispute)
            await verification.connect(arbiter).resolveDelivery(TRADE_ID, 1, 0);

            // Buyer reputation should be penalized: 100% success rate - 5% penalty = 95%
            const reputation = await verification.getUserReputation(buyer.address);
            expect(reputation).to.equal(95); // 100 - 5 (one lost dispute)
        });
    });

    // ============ Integration Tests ============

    describe("Integration", function () {
        it("should complete full successful verification flow", async function () {
            // 1. Register trade
            await verification.connect(escrow).registerTrade(
                TRADE_ID,
                seller.address,
                buyer.address,
                QUANTITY,
                VALUE,
                discom.address
            );

            // 2. DISCOM reports delivery
            const signature = await createDISCOMSignature(
                TRADE_ID,
                seller.address,
                buyer.address,
                QUANTITY
            );

            await verification.reportDeliveryWithDISCOM(TRADE_ID, QUANTITY, signature);

            // 3. Verify final state
            const trade = await verification.getTrade(TRADE_ID);
            expect(trade.status).to.equal(2); // Confirmed
            expect(trade.method).to.equal(1); // DISCOMAttestation

            // 4. Check stats
            const stats = await verification.getVerificationStats();
            expect(stats.successful).to.equal(1);
        });

        it("should handle complete dispute flow", async function () {
            // 1. Register trade
            await verification.connect(escrow).registerTrade(
                TRADE_ID,
                seller.address,
                buyer.address,
                QUANTITY,
                VALUE,
                discom.address
            );

            // 2. Deadline passes
            await time.increase(DELIVERY_WINDOW + 1);

            // 3. Buyer raises dispute
            await verification.connect(buyer).raiseNonDelivery(TRADE_ID);

            // 4. Arbiter resolves
            await verification.connect(arbiter).resolveDelivery(TRADE_ID, 2, 0);

            // 5. Verify final state
            const trade = await verification.getTrade(TRADE_ID);
            expect(trade.status).to.equal(4); // Resolved
            expect(trade.sellerSlashed).to.be.true;

            const stats = await verification.getVerificationStats();
            expect(stats.failed).to.equal(1);
        });
    });
});
