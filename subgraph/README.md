# SHAKTI-CHAIN Subgraph

The Graph Protocol subgraph for indexing SHAKTI-CHAIN V2G Energy Trading Platform.

## Overview

This subgraph indexes all on-chain events from SHAKTI-CHAIN smart contracts, enabling efficient querying of:
- Energy trading activity (auctions, orders, trades)
- Token transfers and balances
- Staking and rewards
- Reputation system
- EV registrations

## Entities

### Core Entities
- **Prosumer** - Energy market participants (EV owners, charging stations)
- **EV** - Registered electric vehicles
- **AuctionRound** - Periodic auction rounds
- **Order** - Bids and asks in auctions
- **Trade** - Matched orders

### Financial Entities
- **Settlement** - Trade settlements via escrow
- **Dispute** - Settlement disputes
- **TokenHolder** - SHAKTI token holders
- **Stake** - Staking positions

### Analytics Entities
- **DailyStats** - Daily aggregated statistics
- **HourlyStats** - Hourly statistics for charts
- **PriceCandle** - OHLCV price data
- **Protocol** - Global protocol metrics

## Setup

### Prerequisites
- Node.js 18+
- Graph CLI (`npm install -g @graphprotocol/graph-cli`)
- Access to The Graph Studio or hosted service

### Installation

```bash
cd subgraph
npm install
```

### Configuration

1. Update contract addresses in `subgraph.yaml`:
```yaml
dataSources:
  - name: ShaktiToken
    source:
      address: "0x..." # Your deployed token address
      startBlock: 12345 # Deployment block
```

2. Export ABIs from contracts:
```bash
# From shakti-contracts directory
npm run compile
cp artifacts/contracts/ShaktiToken.sol/ShaktiToken.json ../subgraph/abis/
cp artifacts/contracts/EnergyAuction.sol/EnergyAuction.json ../subgraph/abis/
# ... repeat for other contracts
```

### Build & Deploy

```bash
# Generate types from schema and ABIs
npm run codegen

# Build the subgraph
npm run build

# Deploy to The Graph Studio
npm run deploy

# Or deploy locally
npm run create-local
npm run deploy:local
```

## Querying

### GraphQL Endpoint
- **The Graph Studio**: `https://api.studio.thegraph.com/query/<id>/shakti-chain/v1`
- **Local**: `http://localhost:8000/subgraphs/name/shakti-chain/shakti-chain`

### Example Queries

**Recent Trades:**
```graphql
{
  trades(first: 10, orderBy: executedAt, orderDirection: desc) {
    id
    buyer { address tier }
    seller { address tier }
    quantity
    price
    totalValue
    status
  }
}
```

**Prosumer Profile:**
```graphql
{
  prosumer(id: "0x...") {
    address
    reputation
    tier
    totalTrades
    totalVolume
    evs { vehicleId batteryCapacity }
  }
}
```

**Price History:**
```graphql
{
  priceCandles(
    where: { period: 3600 }
    first: 24
    orderBy: timestamp
    orderDirection: desc
  ) {
    timestamp
    open high low close
    volume
  }
}
```

See `queries.graphql` for more example queries.

## Testing

```bash
# Run tests
npm test

# Run with coverage
npm run test:coverage
```

## Directory Structure

```
subgraph/
├── schema.graphql       # GraphQL schema definitions
├── subgraph.yaml       # Subgraph manifest
├── package.json
├── tsconfig.json
├── queries.graphql     # Example queries for frontend
├── src/
│   ├── helpers.ts      # Utility functions
│   ├── shakti-token.ts # Token event handlers
│   ├── energy-auction.ts
│   ├── energy-escrow.ts
│   ├── staking-pool.ts
│   ├── reputation.ts
│   └── energy-registry.ts
├── tests/
│   ├── utils.ts        # Test utilities
│   └── shakti-token.test.ts
└── abis/               # Contract ABIs
```

## Networks

| Network | Status | Endpoint |
|---------|--------|----------|
| Polygon Mainnet | Planned | TBD |
| Polygon Mumbai | Testing | TBD |

## License

MIT
