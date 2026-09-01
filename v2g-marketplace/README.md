# V2G Marketplace

A comprehensive Vehicle-to-Grid (V2G) energy trading platform designed for the Indian energy market, featuring blockchain integration, incentive-compatible auctions, and intelligent agent-based trading.

![License](https://img.shields.io/badge/license-BITS%20Pilani%20All%20Rights%20Reserved-red.svg)
![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![React](https://img.shields.io/badge/react-19.2.0-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)

## Overview

V2G Marketplace enables electric vehicle (EV) owners to participate in India's energy ecosystem by allowing bidirectional energy flow between EVs and the power grid. The platform implements a **McAfee double auction mechanism** for fair price discovery, integrates with blockchain for transparent transactions, and uses **SHAKTI tokens** with velocity-based pricing economics.

### Key Highlights

- **Incentive-Compatible Trading**: McAfee auction mechanism ensures truthful bidding is the dominant strategy
- **Realistic Indian Grid Modeling**: Incorporates authentic demand profiles from 8 major Indian cities
- **Blockchain Integration**: Smart contracts for transparent, tamper-proof energy trading
- **Token Economics**: SHAKTI tokens with velocity-based pricing and staking mechanisms
- **ML-Powered Agents**: Three agent types (residential, commercial, fleet) with SOC-based decision making
- **Production-Ready**: Complete Docker deployment, monitoring, and testing infrastructure

## Quick Start

Get the platform running in 3 commands:

```bash
# 1. Clone and navigate
git clone <repository-url>
cd v2g-marketplace

# 2. Start with Docker Compose
docker-compose up -d

# 3. Access the application
# Frontend:  http://localhost
# API:       http://localhost:8000
# API Docs:  http://localhost:8000/docs
```

That's it! The platform is now running with:
- Frontend React app on port 80
- Backend FastAPI server on port 8000
- SQLite database with initial schema
- Nginx reverse proxy configured

## Demo Mode Runbook

Use this flow for a no-wallet, presentation-quality demo with interactive buy/sell/staking.

1. Start backend and frontend (Docker or manual setup above).
2. Ensure demo mode env flags are enabled:
   - Frontend: `VITE_DEMO_ONLY=true`
   - Backend: `ENVIRONMENT=development` (or `ENABLE_DEMO_LOGIN=true`)
3. Open the app login page and click `Enter Demo`.
4. On the dashboard:
   - Place buy and sell orders from the order form.
   - Stake, unstake, and claim rewards from the staking panel.
   - Review filled orders and fee burn/staker allocation in `Demo Activity`.
5. Refresh the browser to confirm demo state persistence.
6. Click `Reset Demo Data` to return to seeded demo values.

## Screenshots

```
+------------------------------------------------------------------+
|  V2G MARKETPLACE DASHBOARD                     [Connect Wallet]  |
+------------------------------------------------------------------+
|                                                                  |
|  Current Market Price: 4.85 INR/kWh                             |
|  Token Balance: 1,250 SHAKTI                                    |
|  Active Traders: 347                                            |
|                                                                  |
|  [Price Chart - 24h History]                                    |
|  6.0 |                                    *                      |
|      |                               *   * *                     |
|  5.0 |                          *   *       *                    |
|      |                     *   *                                 |
|  4.0 |  *    *    *    *                       *    *           |
|      +-------------------------------------------------------    |
|      00:00  04:00  08:00  12:00  16:00  20:00  00:00           |
|                                                                  |
|  [Simulation Panel]              [My Bids]      [Staking]      |
|  Agents: 300  [========]         Buy: 5.2 INR   Staked: 500    |
|  Duration: 7 days                Sell: 4.8 INR  APY: 8%        |
|  Region: Delhi                   Status: Active  Rewards: 2.3  |
|  [Run Simulation]                                               |
|                                                                  |
+------------------------------------------------------------------+
```

## Architecture Diagram (ASCII)

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │  Dashboard   │  │ Simulation   │  │   Web3 Integration   │ │
│  │   (Charts)   │  │    Panel     │  │  (RainbowKit/wagmi)  │ │
│  └──────────────┘  └──────────────┘  └──────────────────────┘ │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTPS (Nginx)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      BACKEND (FastAPI)                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    REST API Layer                        │  │
│  │  /auth  /simulations  /market  /blockchain  /metrics    │  │
│  └───────────────────┬──────────────────────────────────────┘  │
│                      │                                          │
│  ┌──────────────────┴──────────────────────────────────────┐  │
│  │                   CORE LOGIC                            │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │  │
│  │  │   McAfee     │  │   Prosumer   │  │    SHAKTI    │ │  │
│  │  │   Auction    │  │    Agents    │  │    Token     │ │  │
│  │  │   Engine     │  │   (EV SOC)   │  │  Economics   │ │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘ │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │  │
│  │  │  India Grid  │  │  Simulation  │  │   Reports    │ │  │
│  │  │   Demand     │  │    Runner    │  │  Generator   │ │  │
│  │  │   Profiles   │  │              │  │              │ │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘ │  │
│  └─────────────────────────────────────────────────────────┘  │
│                      │                                          │
│  ┌──────────────────┴──────────────────────────────────────┐  │
│  │              BLOCKCHAIN SERVICE                         │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │  │
│  │  │ Provider │  │Contracts │  │  Events  │  │  Sync  │ │  │
│  │  │  (Web3)  │  │ Manager  │  │ Listener │  │ Engine │ │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └────────┘ │  │
│  └─────────────────────────────────────────────────────────┘  │
└─────────────────────┬────────────────────┬─────────────────────┘
                      │                    │
                      ▼                    ▼
        ┌──────────────────────┐  ┌──────────────────────┐
        │   SQLite Database    │  │  Blockchain Network  │
        │  - Users             │  │  - ShaktiToken       │
        │  - Simulations       │  │  - EnergyAuction     │
        │  - Market Periods    │  │  - StakingPool       │
        │  - Price History     │  │  - Reputation        │
        └──────────────────────┘  └──────────────────────┘
```

## Key Features

### 1. McAfee Double Auction Mechanism

The platform implements the **incentive-compatible McAfee auction**:
- Truthful bidding is a dominant strategy (no benefit from lying)
- Budget balanced (auctioneer never loses money)
- Efficient market clearing at uniform price
- See [docs/MATH.md](docs/MATH.md) for detailed algorithm explanation

### 2. Intelligent Prosumer Agents

Three types of EV agents with autonomous trading:

| Agent Type | Characteristics | Battery | Charging Pattern |
|------------|----------------|---------|------------------|
| **Residential** | Home charging, peak-aware | 60 kWh | Night + evening discharge |
| **Commercial** | Fleet operations | 80 kWh | Business hours priority |
| **Fleet** | Large-scale coordination | 100 kWh | Optimized 24/7 |

Agents make decisions based on:
- State of Charge (SOC)
- Time of day (peak vs off-peak)
- Grid demand signals
- Price forecasts

### 3. SHAKTI Token Economics

Novel velocity-based pricing model:

```
Velocity: V = V₀ × (1-σ)^0.5 × exp(-0.1 × Q/Qmax)
Price:    P_T = (P_E × Q × 24) / (M × (1-σ) × V)
```

Features:
- 2% transaction fee (30% burned, 70% to stakers)
- 8% APY for stakers
- Deflationary pressure from burning
- Price smoothing (max 10% change per period)

### 4. Realistic Indian Grid Modeling

Authentic demand profiles for 8 major cities:
- Delhi, Mumbai, Bangalore, Chennai, Hyderabad, Kolkata, Pune, Ahmedabad
- Seasonal variations (summer AC load, monsoon, winter)
- Day-of-week patterns (weekday vs weekend)
- Hourly multipliers (peak at 7 PM = 1.4x)

### 5. Blockchain Integration

Smart contracts for:
- **ShaktiToken**: ERC20 with staking functionality
- **EnergyAuction**: Market clearing and trade execution
- **StakingPool**: Reward distribution (8% APY)
- **ReputationSystem**: Trader reliability scores

Supports:
- Hardhat (local development)
- Polygon Amoy (testnet)
- Polygon (mainnet)

## Project Structure

```
v2g-marketplace/
├── backend/                          # FastAPI backend
│   ├── api/                          # REST API endpoints
│   │   ├── main.py                   # FastAPI app, middleware, routes
│   │   ├── auth.py                   # JWT authentication
│   │   ├── schemas.py                # Pydantic request/response models
│   │   ├── simulation_service.py     # Simulation business logic
│   │   └── routes/
│   │       └── blockchain.py         # Blockchain API routes
│   ├── core/                         # Core business logic
│   │   ├── database.py               # SQLite operations
│   │   ├── agents/
│   │   │   └── prosumer.py           # EV agent model (SOC, bids)
│   │   ├── auction/
│   │   │   └── mcafee.py             # McAfee auction mechanism
│   │   ├── token/
│   │   │   └── shakti.py             # Token economics & pricing
│   │   ├── demand/
│   │   │   └── india_load.py         # Indian grid demand profiles
│   │   ├── reports/
│   │   │   └── generator.py          # Report generation
│   │   ├── logging.py                # Structured logging
│   │   └── metrics.py                # Prometheus metrics
│   ├── services/                     # External integrations
│   │   └── blockchain/
│   │       ├── service.py            # Main blockchain service
│   │       ├── contracts.py          # Contract management
│   │       ├── provider.py           # Web3 provider setup
│   │       ├── transactions.py       # Transaction handling
│   │       ├── events.py             # Event listening
│   │       └── sync.py               # Blockchain state sync
│   ├── tests/                        # Comprehensive test suite
│   │   ├── test_agents.py
│   │   ├── test_auction.py
│   │   ├── test_shakti_token.py
│   │   ├── test_india_load.py
│   │   ├── test_simulation_runner.py
│   │   ├── test_api.py
│   │   └── test_integration.py
│   └── requirements.txt              # Python dependencies
├── frontend/                         # React + Vite application
│   ├── src/
│   │   ├── components/               # React components
│   │   │   ├── Dashboard.jsx         # Main dashboard
│   │   │   ├── SimulationPanel.jsx   # Simulation controls
│   │   │   ├── PriceChart.jsx        # Recharts visualization
│   │   │   ├── AgentMixSlider.jsx    # Agent distribution control
│   │   │   └── web3/                 # Web3 UI components
│   │   ├── pages/
│   │   │   ├── Login.jsx
│   │   │   └── Register.jsx
│   │   ├── context/
│   │   │   └── AuthContext.jsx       # JWT token management
│   │   ├── hooks/
│   │   │   └── useApi.js             # API client hook
│   │   ├── services/
│   │   │   └── api.js                # Axios instance
│   │   ├── providers/
│   │   │   └── Web3Provider.jsx      # wagmi/RainbowKit setup
│   │   ├── contracts/
│   │   │   └── abis/                 # Smart contract ABIs
│   │   └── App.jsx                   # Root component
│   ├── package.json                  # NPM dependencies
│   ├── vite.config.js                # Vite configuration
│   └── vitest.config.js              # Test configuration
├── simulation/                       # Simulation framework
│   └── runner.py                     # Complete simulation executor
├── docs/                             # Documentation
│   ├── API.md                        # Complete API reference
│   ├── ARCHITECTURE.md               # System design
│   ├── DEPLOYMENT.md                 # Deployment guide
│   ├── MATH.md                       # Algorithms & economics
│   ├── ROADMAP.md                    # Features & roadmap
│   └── LAUNCH_CHECKLIST.md           # Production checklist
├── data/                             # Persistent data
│   └── v2g.db                        # SQLite database
├── docker-compose.yml                # Production Docker setup
├── docker-compose.dev.yml            # Development Docker setup
└── README.md                         # This file
```

## Technology Stack

### Backend
- **Framework**: FastAPI 0.104+ (async Python web framework)
- **Server**: Uvicorn 0.24+ (ASGI server)
- **Database**: SQLite (zero-config, production-ready for MVP scale)
- **Authentication**: JWT (PyJWT 2.8+) + bcrypt (4.1+)
- **Blockchain**: Web3.py 6.0+
- **Monitoring**: Prometheus Client 0.19+
- **Testing**: pytest 7.4+, pytest-asyncio, pytest-cov
- **Logging**: structlog 23.2+ (structured JSON logs)

### Frontend
- **Framework**: React 19.2.0 + Vite 7.2.4
- **HTTP Client**: axios 1.13.2
- **Charts**: Recharts 3.5.0
- **Web3**: wagmi 2.14.6, viem 2.21.54, RainbowKit 2.2.2
- **Testing**: Vitest, Playwright, @testing-library/react

### Infrastructure
- **Containers**: Docker + Docker Compose
- **Reverse Proxy**: Nginx
- **Blockchain Networks**: Hardhat, Polygon Amoy, Polygon

## Installation

### Prerequisites

- Python 3.9+
- Node.js 18+
- Docker & Docker Compose (optional, recommended)

### Docker Deployment (Recommended)

**Production Mode:**
```bash
docker-compose up -d
```

**Development Mode (Hot Reload):**
```bash
docker-compose -f docker-compose.dev.yml up -d
```

**Access Points:**
- Frontend: http://localhost (production) or http://localhost:3000 (dev)
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

### Manual Installation

**Backend Setup:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run tests
pytest tests/ -v --cov

# Start server
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

**Frontend Setup:**
```bash
cd frontend
npm install
npm run dev    # Development server (port 5173)
npm run build  # Production build
npm test       # Run tests
```

### Environment Configuration

Create `.env` file in the backend directory:

```env
# Database
DATABASE_URL=sqlite:///./data/v2g.db

# JWT Authentication
JWT_SECRET_KEY=your-secret-key-here-change-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Blockchain
BLOCKCHAIN_NETWORK=hardhat  # or polygon_amoy, polygon
HARDHAT_RPC_URL=http://127.0.0.1:8545
POLYGON_RPC_URL=https://rpc-amoy.polygon.technology/
PRIVATE_KEY=0x...  # For backend signing

# Synchronization
SYNC_POLL_INTERVAL=12
SYNC_BATCH_SIZE=1000

# Server
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO
```

## Running Simulations

### Via API

```bash
# Start a simulation
curl -X POST http://localhost:8000/simulation/start \
  -H "Content-Type: application/json" \
  -d '{
    "n_agents": 300,
    "n_days": 7,
    "agent_mix": {"residential": 60, "commercial": 30, "fleet": 10},
    "region": "Delhi"
  }'

# Check status
curl http://localhost:8000/simulation/status/{job_id}

# Download results
curl http://localhost:8000/simulation/download/{job_id} -o results.csv
```

### Via CLI

```bash
python cli.py simulate \
  --agents 300 \
  --days 7 \
  --region Delhi \
  --output results.csv
```

### Via Web UI

1. Navigate to http://localhost
2. Go to Dashboard > Simulation Panel
3. Configure parameters:
   - Agents: 50-500
   - Duration: 1/7/30 days
   - Agent mix: Residential/Commercial/Fleet %
   - Region: Delhi/Mumbai/Bangalore/Chennai
4. Click "Run Simulation"
5. View results and download CSV

## API Overview

### Authentication

```bash
# Register
POST /auth/register
{
  "email": "user@example.com",
  "password": "secure_password"
}

# Login
POST /auth/login
{
  "email": "user@example.com",
  "password": "secure_password"
}
# Returns: { "access_token": "eyJ...", "token_type": "bearer" }

# Use token in subsequent requests
Authorization: Bearer eyJ...
```

### Market Data

```bash
# Get current price
GET /market/price

# Get price history
GET /market/price/history?limit=100

# Create simulation
POST /simulations
{
  "n_agents": 300,
  "n_days": 7,
  "agent_mix": {"residential": 60, "commercial": 30, "fleet": 10}
}
```

### Blockchain Operations

```bash
# Get token balance
GET /api/blockchain/tokens/balance/{address}

# Submit auction bid
POST /api/blockchain/auction/bid
{
  "is_buy": true,
  "quantity": 10.0,
  "price": 5.2
}

# Stake tokens
POST /api/blockchain/staking/stake
{
  "amount": 1000
}
```

See [docs/API.md](docs/API.md) for complete API documentation.

## Testing

### Backend Tests

```bash
cd backend
pytest tests/ -v --cov --cov-report=html

# Run specific test file
pytest tests/test_auction.py -v

# Run with coverage
pytest tests/ --cov=core --cov=api --cov-report=term-missing
```

### Frontend Tests

```bash
cd frontend
npm test              # Unit tests
npm run test:e2e      # End-to-end tests
npm run test:coverage # Coverage report
```

## Monitoring

### Prometheus Metrics

Access metrics at: http://localhost:8000/metrics

Available metrics:
- `api_requests_total` - Total API requests
- `api_request_duration_seconds` - Request latency
- `simulation_runs_total` - Total simulations
- `auction_clearing_duration_seconds` - Auction performance
- `active_agents_count` - Current active agents

### Health Checks

```bash
# Liveness check
GET /health

# Readiness check (includes DB)
GET /health/ready
```

### Structured Logging

Logs are output in JSON format for easy parsing:

```json
{
  "timestamp": "2025-12-03T10:30:00Z",
  "level": "INFO",
  "event": "auction_cleared",
  "clearing_price": 4.85,
  "volume": 1250.5,
  "n_buyers": 145,
  "n_sellers": 132
}
```

## Contributing

We welcome contributions! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Write tests for new functionality
4. Ensure all tests pass (`pytest tests/`)
5. Follow code style guidelines (black, flake8)
6. Commit changes (`git commit -m 'Add amazing feature'`)
7. Push to branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

### Code Style

- Python: Follow PEP 8, use black formatter
- JavaScript: Follow Airbnb style guide, use prettier
- Commit messages: Use conventional commits format

### Testing Requirements

- Minimum 80% code coverage
- All unit tests passing
- Integration tests for new features
- E2E tests for UI changes

## License

Copyright BITS Pilani. All rights reserved. The root [LICENSE](../LICENSE) governs this tree. Nested MIT badges in older drafts are not a grant of rights.

## Documentation

- [API Reference](docs/API.md) - Complete API documentation
- [Architecture Guide](docs/ARCHITECTURE.md) - System design and data flow
- [Deployment Guide](docs/DEPLOYMENT.md) - Infrastructure setup
- [Mathematics & Economics](docs/MATH.md) - Algorithms and token model
- [Roadmap](docs/ROADMAP.md) - Features and future plans
- [Launch Checklist](docs/LAUNCH_CHECKLIST.md) - Production deployment checklist

## Contact & Support

- **Issues**: https://github.com/your-org/v2g-marketplace/issues
- **Discussions**: https://github.com/your-org/v2g-marketplace/discussions
- **Email**: support@v2g-marketplace.com

## Acknowledgments

This platform is designed to support:
- India's National Electric Mobility Mission Plan (NEMMP)
- FAME (Faster Adoption and Manufacturing of Electric Vehicles) initiatives
- CERC (Central Electricity Regulatory Commission) guidelines
- Integration with state-level DISCOMs

---

**Built with ❤️ for India's sustainable energy future**

