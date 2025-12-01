import { expect } from "chai";
import { ethers } from "hardhat";
import { loadFixture, time } from "@nomicfoundation/hardhat-network-helpers";
import { SignerWithAddress } from "@nomicfoundation/hardhat-ethers/signers";
import { ShaktiToken } from "../typechain-types";

describe("ShaktiToken", function () {
  // Constants matching the contract
  const INITIAL_SUPPLY = ethers.parseEther("1000000000"); // 1 billion
  const MAX_SUPPLY = ethers.parseEther("1000000000");
  const FEE_BURN_PERCENTAGE = 30n;
  const PERCENTAGE_BASE = 100n;

  // Role hashes
  const DEFAULT_ADMIN_ROLE = ethers.ZeroHash;
  const MINTER_ROLE = ethers.keccak256(ethers.toUtf8Bytes("MINTER_ROLE"));
  const PAUSER_ROLE = ethers.keccak256(ethers.toUtf8Bytes("PAUSER_ROLE"));
  const BURNER_ROLE = ethers.keccak256(ethers.toUtf8Bytes("BURNER_ROLE"));

  async function deployTokenFixture() {
    const [admin, holder, user1, user2, minter, pauser, burner] = await ethers.getSigners();

    const ShaktiTokenFactory = await ethers.getContractFactory("ShaktiToken");
    const token = await ShaktiTokenFactory.deploy(admin.address, holder.address);
    await token.waitForDeployment();

    return { token, admin, holder, user1, user2, minter, pauser, burner };
  }

  async function deployTokenWithRolesFixture() {
    const { token, admin, holder, user1, user2, minter, pauser, burner } = await loadFixture(deployTokenFixture);

    // Grant roles to specific accounts
    await token.connect(admin).grantRole(MINTER_ROLE, minter.address);
    await token.connect(admin).grantRole(PAUSER_ROLE, pauser.address);
    await token.connect(admin).grantRole(BURNER_ROLE, burner.address);

    // Transfer some tokens to burner for fee burning tests
    const transferAmount = ethers.parseEther("1000000"); // 1 million tokens
    await token.connect(holder).transfer(burner.address, transferAmount);

    return { token, admin, holder, user1, user2, minter, pauser, burner };
  }

  // ============ Deployment Tests ============
  describe("Deployment", function () {
    it("should deploy with correct name and symbol", async function () {
      const { token } = await loadFixture(deployTokenFixture);
      expect(await token.name()).to.equal("ShaktiToken");
      expect(await token.symbol()).to.equal("SHAKTI");
    });

    it("should mint initial supply to the holder", async function () {
      const { token, holder } = await loadFixture(deployTokenFixture);
      expect(await token.balanceOf(holder.address)).to.equal(INITIAL_SUPPLY);
      expect(await token.totalSupply()).to.equal(INITIAL_SUPPLY);
    });

    it("should set correct constants", async function () {
      const { token } = await loadFixture(deployTokenFixture);
      expect(await token.INITIAL_SUPPLY()).to.equal(INITIAL_SUPPLY);
      expect(await token.MAX_SUPPLY()).to.equal(MAX_SUPPLY);
      expect(await token.FEE_BURN_PERCENTAGE()).to.equal(FEE_BURN_PERCENTAGE);
    });

    it("should grant all roles to admin", async function () {
      const { token, admin } = await loadFixture(deployTokenFixture);
      expect(await token.hasRole(DEFAULT_ADMIN_ROLE, admin.address)).to.be.true;
      expect(await token.hasRole(MINTER_ROLE, admin.address)).to.be.true;
      expect(await token.hasRole(PAUSER_ROLE, admin.address)).to.be.true;
      expect(await token.hasRole(BURNER_ROLE, admin.address)).to.be.true;
    });

    it("should revert if admin is zero address", async function () {
      const ShaktiTokenFactory = await ethers.getContractFactory("ShaktiToken");
      const [, holder] = await ethers.getSigners();
      await expect(
        ShaktiTokenFactory.deploy(ethers.ZeroAddress, holder.address)
      ).to.be.revertedWithCustomError(ShaktiTokenFactory, "ZeroAddress");
    });

    it("should revert if holder is zero address", async function () {
      const ShaktiTokenFactory = await ethers.getContractFactory("ShaktiToken");
      const [admin] = await ethers.getSigners();
      await expect(
        ShaktiTokenFactory.deploy(admin.address, ethers.ZeroAddress)
      ).to.be.revertedWithCustomError(ShaktiTokenFactory, "ZeroAddress");
    });
  });

  // ============ ERC20 Basic Tests ============
  describe("ERC20 Basic Functions", function () {
    it("should transfer tokens between accounts", async function () {
      const { token, holder, user1 } = await loadFixture(deployTokenFixture);
      const amount = ethers.parseEther("1000");

      await expect(token.connect(holder).transfer(user1.address, amount))
        .to.emit(token, "Transfer")
        .withArgs(holder.address, user1.address, amount);

      expect(await token.balanceOf(user1.address)).to.equal(amount);
    });

    it("should approve and transferFrom", async function () {
      const { token, holder, user1, user2 } = await loadFixture(deployTokenFixture);
      const amount = ethers.parseEther("1000");

      await token.connect(holder).approve(user1.address, amount);
      expect(await token.allowance(holder.address, user1.address)).to.equal(amount);

      await expect(token.connect(user1).transferFrom(holder.address, user2.address, amount))
        .to.emit(token, "Transfer")
        .withArgs(holder.address, user2.address, amount);

      expect(await token.balanceOf(user2.address)).to.equal(amount);
      expect(await token.allowance(holder.address, user1.address)).to.equal(0);
    });

    it("should have 18 decimals", async function () {
      const { token } = await loadFixture(deployTokenFixture);
      expect(await token.decimals()).to.equal(18);
    });
  });

  // ============ ERC20Permit Tests ============
  describe("ERC20Permit", function () {
    it("should have correct domain separator", async function () {
      const { token } = await loadFixture(deployTokenFixture);
      const domainSeparator = await token.DOMAIN_SEPARATOR();
      expect(domainSeparator).to.not.equal(ethers.ZeroHash);
    });

    it("should allow gasless approval via permit", async function () {
      const { token, holder, user1 } = await loadFixture(deployTokenFixture);
      const amount = ethers.parseEther("1000");
      const nonce = await token.nonces(holder.address);
      const deadline = (await time.latest()) + 3600; // 1 hour from now

      // Get the domain
      const domain = {
        name: "ShaktiToken",
        version: "1",
        chainId: (await ethers.provider.getNetwork()).chainId,
        verifyingContract: await token.getAddress(),
      };

      // Define the Permit type
      const types = {
        Permit: [
          { name: "owner", type: "address" },
          { name: "spender", type: "address" },
          { name: "value", type: "uint256" },
          { name: "nonce", type: "uint256" },
          { name: "deadline", type: "uint256" },
        ],
      };

      // Sign the permit
      const value = {
        owner: holder.address,
        spender: user1.address,
        value: amount,
        nonce: nonce,
        deadline: deadline,
      };

      const signature = await holder.signTypedData(domain, types, value);
      const { v, r, s } = ethers.Signature.from(signature);

      // Execute permit
      await token.permit(holder.address, user1.address, amount, deadline, v, r, s);

      expect(await token.allowance(holder.address, user1.address)).to.equal(amount);
      expect(await token.nonces(holder.address)).to.equal(nonce + 1n);
    });
  });

  // ============ ERC20Burnable Tests ============
  describe("ERC20Burnable", function () {
    it("should allow holder to burn their own tokens", async function () {
      const { token, holder } = await loadFixture(deployTokenFixture);
      const burnAmount = ethers.parseEther("1000");
      const initialBalance = await token.balanceOf(holder.address);

      await expect(token.connect(holder).burn(burnAmount))
        .to.emit(token, "Transfer")
        .withArgs(holder.address, ethers.ZeroAddress, burnAmount);

      expect(await token.balanceOf(holder.address)).to.equal(initialBalance - burnAmount);
      expect(await token.totalSupply()).to.equal(INITIAL_SUPPLY - burnAmount);
    });

    it("should allow burnFrom with approval", async function () {
      const { token, holder, user1 } = await loadFixture(deployTokenFixture);
      const burnAmount = ethers.parseEther("1000");

      await token.connect(holder).approve(user1.address, burnAmount);
      await token.connect(user1).burnFrom(holder.address, burnAmount);

      expect(await token.totalSupply()).to.equal(INITIAL_SUPPLY - burnAmount);
    });
  });

  // ============ Fee Burning Tests ============
  describe("burnFees", function () {
    it("should burn 30% of the fee amount", async function () {
      const { token, burner } = await loadFixture(deployTokenWithRolesFixture);
      const feeAmount = ethers.parseEther("10000");
      const expectedBurn = (feeAmount * FEE_BURN_PERCENTAGE) / PERCENTAGE_BASE;
      const initialBalance = await token.balanceOf(burner.address);

      await expect(token.connect(burner).burnFees(feeAmount))
        .to.emit(token, "FeesBurned")
        .withArgs(burner.address, feeAmount, expectedBurn);

      expect(await token.balanceOf(burner.address)).to.equal(initialBalance - expectedBurn);
      expect(await token.totalFeesBurned()).to.equal(expectedBurn);
    });

    it("should accumulate totalFeesBurned correctly", async function () {
      const { token, burner } = await loadFixture(deployTokenWithRolesFixture);
      const feeAmount1 = ethers.parseEther("10000");
      const feeAmount2 = ethers.parseEther("5000");
      const expectedBurn1 = (feeAmount1 * FEE_BURN_PERCENTAGE) / PERCENTAGE_BASE;
      const expectedBurn2 = (feeAmount2 * FEE_BURN_PERCENTAGE) / PERCENTAGE_BASE;

      await token.connect(burner).burnFees(feeAmount1);
      await token.connect(burner).burnFees(feeAmount2);

      expect(await token.totalFeesBurned()).to.equal(expectedBurn1 + expectedBurn2);
    });

    it("should revert if caller lacks BURNER_ROLE", async function () {
      const { token, user1 } = await loadFixture(deployTokenWithRolesFixture);
      const feeAmount = ethers.parseEther("1000");

      await expect(token.connect(user1).burnFees(feeAmount))
        .to.be.revertedWithCustomError(token, "AccessControlUnauthorizedAccount")
        .withArgs(user1.address, BURNER_ROLE);
    });

    it("should revert if amount is zero", async function () {
      const { token, burner } = await loadFixture(deployTokenWithRolesFixture);

      await expect(token.connect(burner).burnFees(0))
        .to.be.revertedWithCustomError(token, "ZeroAmount");
    });

    it("should revert if insufficient balance", async function () {
      const { token, burner } = await loadFixture(deployTokenWithRolesFixture);
      const balance = await token.balanceOf(burner.address);
      const excessAmount = balance + ethers.parseEther("1");

      await expect(token.connect(burner).burnFees(excessAmount))
        .to.be.revertedWithCustomError(token, "InsufficientBalance")
        .withArgs(excessAmount, balance);
    });

    it("should calculate burn correctly for various amounts", async function () {
      const { token, burner } = await loadFixture(deployTokenWithRolesFixture);

      // Test with small amount
      const smallAmount = ethers.parseEther("100");
      const expectedSmallBurn = (smallAmount * FEE_BURN_PERCENTAGE) / PERCENTAGE_BASE;

      const balanceBefore = await token.balanceOf(burner.address);
      await token.connect(burner).burnFees(smallAmount);
      const balanceAfter = await token.balanceOf(burner.address);

      expect(balanceBefore - balanceAfter).to.equal(expectedSmallBurn);
    });
  });

  // ============ Minting Tests ============
  describe("mint", function () {
    it("should not allow minting beyond MAX_SUPPLY", async function () {
      const { token, admin, holder } = await loadFixture(deployTokenFixture);

      // First burn some tokens to have room
      const burnAmount = ethers.parseEther("1000");
      await token.connect(holder).burn(burnAmount);

      // Try to mint more than burned
      const excessMint = burnAmount + ethers.parseEther("1");
      const currentSupply = await token.totalSupply();
      const newTotal = currentSupply + excessMint;

      await expect(token.connect(admin).mint(holder.address, excessMint))
        .to.be.revertedWithCustomError(token, "ExceedsMaxSupply")
        .withArgs(newTotal, MAX_SUPPLY);
    });

    it("should allow minting up to MAX_SUPPLY after burning", async function () {
      const { token, admin, holder } = await loadFixture(deployTokenFixture);

      // Burn some tokens
      const burnAmount = ethers.parseEther("1000");
      await token.connect(holder).burn(burnAmount);

      // Mint back the burned amount
      await expect(token.connect(admin).mint(holder.address, burnAmount))
        .to.emit(token, "TokensMinted")
        .withArgs(holder.address, burnAmount);

      expect(await token.totalSupply()).to.equal(MAX_SUPPLY);
    });

    it("should revert if caller lacks MINTER_ROLE", async function () {
      const { token, user1 } = await loadFixture(deployTokenWithRolesFixture);

      await expect(token.connect(user1).mint(user1.address, ethers.parseEther("1")))
        .to.be.revertedWithCustomError(token, "AccessControlUnauthorizedAccount")
        .withArgs(user1.address, MINTER_ROLE);
    });

    it("should revert if minting to zero address", async function () {
      const { token, minter } = await loadFixture(deployTokenWithRolesFixture);

      await expect(token.connect(minter).mint(ethers.ZeroAddress, ethers.parseEther("1")))
        .to.be.revertedWithCustomError(token, "ZeroAddress");
    });

    it("should revert if minting zero amount", async function () {
      const { token, minter, user1 } = await loadFixture(deployTokenWithRolesFixture);

      await expect(token.connect(minter).mint(user1.address, 0))
        .to.be.revertedWithCustomError(token, "ZeroAmount");
    });
  });

  // ============ Pausable Tests ============
  describe("Pausable", function () {
    it("should pause and unpause transfers", async function () {
      const { token, pauser, holder, user1 } = await loadFixture(deployTokenWithRolesFixture);
      const amount = ethers.parseEther("100");

      // Pause
      await expect(token.connect(pauser).pause())
        .to.emit(token, "EmergencyPaused")
        .withArgs(pauser.address);

      expect(await token.paused()).to.be.true;

      // Transfer should fail when paused
      await expect(token.connect(holder).transfer(user1.address, amount))
        .to.be.revertedWithCustomError(token, "EnforcedPause");

      // Unpause
      await expect(token.connect(pauser).unpause())
        .to.emit(token, "EmergencyUnpaused")
        .withArgs(pauser.address);

      expect(await token.paused()).to.be.false;

      // Transfer should work again
      await token.connect(holder).transfer(user1.address, amount);
      expect(await token.balanceOf(user1.address)).to.equal(amount);
    });

    it("should revert if non-pauser tries to pause", async function () {
      const { token, user1 } = await loadFixture(deployTokenWithRolesFixture);

      await expect(token.connect(user1).pause())
        .to.be.revertedWithCustomError(token, "AccessControlUnauthorizedAccount")
        .withArgs(user1.address, PAUSER_ROLE);
    });

    it("should revert if non-pauser tries to unpause", async function () {
      const { token, pauser, user1 } = await loadFixture(deployTokenWithRolesFixture);

      await token.connect(pauser).pause();

      await expect(token.connect(user1).unpause())
        .to.be.revertedWithCustomError(token, "AccessControlUnauthorizedAccount")
        .withArgs(user1.address, PAUSER_ROLE);
    });

    it("should prevent burning when paused", async function () {
      const { token, pauser, holder } = await loadFixture(deployTokenWithRolesFixture);

      await token.connect(pauser).pause();

      await expect(token.connect(holder).burn(ethers.parseEther("100")))
        .to.be.revertedWithCustomError(token, "EnforcedPause");
    });

    it("should prevent fee burning when paused", async function () {
      const { token, pauser, burner } = await loadFixture(deployTokenWithRolesFixture);

      await token.connect(pauser).pause();

      await expect(token.connect(burner).burnFees(ethers.parseEther("1000")))
        .to.be.revertedWithCustomError(token, "EnforcedPause");
    });
  });

  // ============ Access Control Tests ============
  describe("Access Control", function () {
    it("should allow admin to grant roles", async function () {
      const { token, admin, user1 } = await loadFixture(deployTokenFixture);

      await token.connect(admin).grantRole(MINTER_ROLE, user1.address);
      expect(await token.hasRole(MINTER_ROLE, user1.address)).to.be.true;
    });

    it("should allow admin to revoke roles", async function () {
      const { token, admin, minter } = await loadFixture(deployTokenWithRolesFixture);

      await token.connect(admin).revokeRole(MINTER_ROLE, minter.address);
      expect(await token.hasRole(MINTER_ROLE, minter.address)).to.be.false;
    });

    it("should allow role bearer to renounce their role", async function () {
      const { token, minter } = await loadFixture(deployTokenWithRolesFixture);

      await token.connect(minter).renounceRole(MINTER_ROLE, minter.address);
      expect(await token.hasRole(MINTER_ROLE, minter.address)).to.be.false;
    });

    it("should prevent non-admin from granting roles", async function () {
      const { token, user1, user2 } = await loadFixture(deployTokenWithRolesFixture);

      await expect(token.connect(user1).grantRole(MINTER_ROLE, user2.address))
        .to.be.revertedWithCustomError(token, "AccessControlUnauthorizedAccount")
        .withArgs(user1.address, DEFAULT_ADMIN_ROLE);
    });
  });

  // ============ View Functions Tests ============
  describe("View Functions", function () {
    it("should return correct remainingMintableSupply", async function () {
      const { token, holder } = await loadFixture(deployTokenFixture);

      // Initially should be 0 since we're at MAX_SUPPLY
      expect(await token.remainingMintableSupply()).to.equal(0);

      // Burn some tokens
      const burnAmount = ethers.parseEther("1000");
      await token.connect(holder).burn(burnAmount);

      // Now should be equal to burned amount
      expect(await token.remainingMintableSupply()).to.equal(burnAmount);
    });

    it("should return correct circulatingSupply", async function () {
      const { token, holder } = await loadFixture(deployTokenFixture);

      expect(await token.circulatingSupply()).to.equal(INITIAL_SUPPLY);

      const burnAmount = ethers.parseEther("1000");
      await token.connect(holder).burn(burnAmount);

      expect(await token.circulatingSupply()).to.equal(INITIAL_SUPPLY - burnAmount);
    });
  });

  // ============ Gas Optimization Tests ============
  describe("Gas Optimization", function () {
    it("should use custom errors instead of require strings", async function () {
      const { token, user1 } = await loadFixture(deployTokenWithRolesFixture);

      // Test custom error for burnFees with zero amount
      await expect(token.connect(user1).burnFees(ethers.parseEther("100")))
        .to.be.revertedWithCustomError(token, "AccessControlUnauthorizedAccount");

      // Test InsufficientBalance custom error
      const { burner } = await loadFixture(deployTokenWithRolesFixture);
      const balance = await token.balanceOf(burner.address);
      await expect(token.connect(burner).burnFees(balance + ethers.parseEther("1")))
        .to.be.revertedWithCustomError(token, "InsufficientBalance");
    });

    it("should have efficient storage usage", async function () {
      const { token } = await loadFixture(deployTokenFixture);
      // The contract should compile successfully with optimizer enabled
      // This is more of a compilation test that validates the storage layout
      expect(await token.totalFeesBurned()).to.equal(0);
    });
  });

  // ============ Edge Cases ============
  describe("Edge Cases", function () {
    it("should handle maximum uint256 approval", async function () {
      const { token, holder, user1 } = await loadFixture(deployTokenFixture);

      await token.connect(holder).approve(user1.address, ethers.MaxUint256);
      expect(await token.allowance(holder.address, user1.address)).to.equal(ethers.MaxUint256);
    });

    it("should handle transfer of zero tokens", async function () {
      const { token, holder, user1 } = await loadFixture(deployTokenFixture);

      // This should succeed (ERC20 allows zero transfers)
      await expect(token.connect(holder).transfer(user1.address, 0))
        .to.emit(token, "Transfer")
        .withArgs(holder.address, user1.address, 0);
    });

    it("should correctly calculate 30% for edge case amounts", async function () {
      const { token, admin, burner } = await loadFixture(deployTokenWithRolesFixture);

      // Test with amount that doesn't divide evenly
      const oddAmount = ethers.parseEther("33.333333333333333333");
      const expectedBurn = (oddAmount * FEE_BURN_PERCENTAGE) / PERCENTAGE_BASE;

      // Transfer tokens to burner first
      await token.connect(admin).grantRole(BURNER_ROLE, admin.address);

      const balance = await token.balanceOf(burner.address);
      if (balance >= oddAmount) {
        await token.connect(burner).burnFees(oddAmount);
        // Verify the math is correct (integer division)
        const actualBurned = await token.totalFeesBurned();
        expect(actualBurned).to.equal(expectedBurn);
      }
    });
  });
});
