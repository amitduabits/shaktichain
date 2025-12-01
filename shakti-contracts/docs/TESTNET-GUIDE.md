# SHAKTI-CHAIN Testnet Guide

This guide explains how to deploy, test, and interact with SHAKTI-CHAIN contracts on the Polygon testnet.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Getting Test MATIC](#getting-test-matic)
3. [Configuration](#configuration)
4. [Deployment](#deployment)
5. [Getting Test SHAKTI Tokens](#getting-test-shakti-tokens)
6. [Running a Test Trade](#running-a-test-trade)
7. [Transaction Costs](#transaction-costs)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software

```bash
# Node.js (v18 or higher)
node --version

# npm or yarn
npm --version

# Git
git --version
```

### Install Dependencies

```bash
cd shakti-contracts
npm install
```

### Compile Contracts

```bash
npx hardhat compile
```

---

## Getting Test MATIC

You need test MATIC tokens to pay for gas on the testnet.

### Option 1: Polygon Faucet (Mumbai)

1. Visit [Polygon Mumbai Faucet](https://faucet.polygon.technology/)
2. Select "Mumbai" network
3. Enter your wallet address
4. Complete CAPTCHA and request tokens
5. Wait 1-2 minutes for tokens to arrive

### Option 2: Alchemy Faucet (Amoy - Recommended)

1. Visit [Alchemy Polygon Amoy Faucet](https://www.alchemy.com/faucets/polygon-amoy)
2. Connect your wallet or enter address
3. Complete verification
4. Receive 0.5 MATIC (up to 3x per day)

### Option 3: Direct Request

For larger amounts (development teams), contact Polygon on Discord.

### Verify Balance

```bash
# Check your balance
npx hardhat run --network mumbai scripts/utils/check-balance.ts
```

Or use MetaMask:
1. Add Mumbai network: RPC `https://rpc-mumbai.maticvigil.com`, Chain ID `80001`
2. View balance in wallet

---

## Configuration

### Step 1: Create Environment File

```bash
cp .env.example .env
```

### Step 2: Add Your Private Key

Edit `.env` and add your wallet's private key:

```env
PRIVATE_KEY=your_private_key_without_0x_prefix
```

⚠️ **Security Warning**: Never commit `.env` to version control!

### Step 3: Add API Keys (Optional but Recommended)

```env
# Alchemy for reliable RPC
ALCHEMY_API_KEY=your_alchemy_api_key

# Polygonscan for contract verification
POLYGONSCAN_API_KEY=your_polygonscan_api_key
```

### Step 4: Verify Configuration

```bash
npx hardhat run --network mumbai scripts/utils/check-config.ts
```

---

## Deployment

### Full Deployment (All Contracts)

```bash
# Deploy all 12 contracts
npx hardhat run scripts/deploy/deploy-all.ts --network mumbai
```

Expected output:
```
╔════════════════════════════════════════════════════════════╗
║           SHAKTI-CHAIN Full Deployment                      ║
╚════════════════════════════════════════════════════════════╝

Network: mumbai
Chain ID: 80001
Deployer: 0x...

[1/12] Deploying ShaktiToken...
[2/12] Deploying StakingPool...
...
[12/12] Deploying TimelockController...

Deployment Complete!
Total Time: ~120 seconds
Gas Cost: ~0.3 MATIC
```

### Individual Contract Deployment

```bash
# Deploy contracts one by one
npx hardhat run scripts/deploy/01-deploy-token.ts --network mumbai
npx hardhat run scripts/deploy/02-deploy-staking.ts --network mumbai
# ... and so on
```

### Initialize Contracts

After deployment, run initialization to set up roles:

```bash
npx hardhat run scripts/setup/initialize-contracts.ts --network mumbai
```

### Verify Contracts on Polygonscan

```bash
npx hardhat run scripts/verify/verify-all.ts --network mumbai
```

---

## Getting Test SHAKTI Tokens

After deployment, you can get test SHAKTI tokens in several ways:

### Option 1: Admin Mint (Easiest)

If you deployed the contracts, you have MINTER_ROLE:

```javascript
// In Hardhat console
npx hardhat console --network mumbai

const [deployer] = await ethers.getSigners();
const token = await ethers.getContractAt("ShaktiToken", "DEPLOYED_ADDRESS");
await token.mint(deployer.address, ethers.parseEther("10000"));
```

### Option 2: Use the Test Script

```bash
npx hardhat run scripts/utils/mint-test-tokens.ts --network mumbai
```

### Option 3: Request from Team

Contact the SHAKTI team on Discord with your testnet address.

---

## Running a Test Trade

### Step 1: Register as Prosumer

```javascript
const registry = await ethers.getContractAt("EnergyRegistry", "REGISTRY_ADDRESS");

// Register as producer
await registry.registerProsumer(
  "EV-001",        // Vehicle ID
  10,              // Max capacity (kW)
  50,              // Battery capacity (kWh)
  1,               // Prosumer type (1 = Producer)
  "Test Location"  // Location
);
```

### Step 2: Approve Token Spending

```javascript
const token = await ethers.getContractAt("ShaktiToken", "TOKEN_ADDRESS");
const auction = await ethers.getContractAt("EnergyAuction", "AUCTION_ADDRESS");

// Approve auction to spend tokens
await token.approve(await auction.getAddress(), ethers.MaxUint256);
```

### Step 3: Submit an Ask Order (Seller)

```javascript
// Submit ask: sell 10 kWh at 0.005 SHAKTI/kWh
await auction.submitAsk(
  10,                           // quantity (kWh)
  ethers.parseEther("0.005")    // price per kWh
);

console.log("Ask submitted!");
```

### Step 4: Submit a Bid Order (Buyer)

From another account:

```javascript
// Submit bid: buy 10 kWh at 0.006 SHAKTI/kWh
await auction.submitBid(
  10,                           // quantity (kWh)
  ethers.parseEther("0.006")    // max price per kWh
);

console.log("Bid submitted!");
```

### Step 5: Clear the Market

Wait for auction round to end, then:

```javascript
// Admin clears the market
const currentRound = await auction.currentRoundId();
await auction.clearMarket(currentRound);

console.log("Market cleared!");
```

### Step 6: Verify Trade

```javascript
const round = await auction.getAuctionRound(currentRound);
console.log("Clearing Price:", ethers.formatEther(round.clearingPrice), "SHAKTI/kWh");
console.log("Total Trades:", round.tradesCount.toString());
```

---

## Transaction Costs

Estimated gas costs on Polygon Mumbai (at ~35 gwei):

| Operation | Gas Used | Cost (MATIC) | Cost (USD)* |
|-----------|----------|--------------|-------------|
| Deploy ShaktiToken | ~1,850,000 | ~0.065 | ~$0.05 |
| Deploy All Contracts | ~20,000,000 | ~0.70 | ~$0.55 |
| Submit Bid | ~180,000 | ~0.006 | ~$0.005 |
| Submit Ask | ~150,000 | ~0.005 | ~$0.004 |
| Clear Market (10 trades) | ~300,000 | ~0.010 | ~$0.008 |
| Stake Tokens | ~95,000 | ~0.003 | ~$0.002 |
| Claim Rewards | ~80,000 | ~0.003 | ~$0.002 |

*USD estimates at MATIC = $0.80

### Gas Optimization Tips

1. Use batch operations when possible
2. Deploy during off-peak hours
3. Use gas price estimation: `npx hardhat run scripts/utils/gas-price.ts`

---

## Troubleshooting

### "Insufficient funds"

- Get more test MATIC from faucets
- Check you're using the correct network
- Verify private key in `.env`

### "Nonce too low"

```bash
# Reset nonce in MetaMask: Settings > Advanced > Reset Account
# Or specify nonce manually in transaction
```

### "Transaction underpriced"

```javascript
// Increase gas price
const tx = await contract.method({
  gasPrice: ethers.parseUnits("50", "gwei")
});
```

### "Contract not verified"

```bash
# Manual verification
npx hardhat verify --network mumbai CONTRACT_ADDRESS "arg1" "arg2"
```

### RPC Connection Issues

Try alternative RPC endpoints:
- `https://rpc-mumbai.maticvigil.com`
- `https://polygon-mumbai-bor-rpc.publicnode.com`
- Alchemy/Infura with your API key

---

## Useful Links

- **Polygon Mumbai Explorer**: https://mumbai.polygonscan.com
- **Polygon Amoy Explorer**: https://amoy.polygonscan.com
- **Polygon Faucet**: https://faucet.polygon.technology
- **Alchemy Faucet**: https://www.alchemy.com/faucets/polygon-amoy
- **Polygon Docs**: https://docs.polygon.technology

---

## Contract Addresses

After deployment, contract addresses are saved in:
```
deployments/mumbai/deployments.json
```

Or individual files:
```
deployments/mumbai/ShaktiToken.json
deployments/mumbai/EnergyAuction.json
...
```

---

## Support

- **GitHub Issues**: Report bugs and feature requests
- **Discord**: Join #shakti-chain for community support
- **Documentation**: See `/docs` folder for detailed guides
