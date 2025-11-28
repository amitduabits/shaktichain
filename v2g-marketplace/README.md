# V2G Marketplace 🔋⚡

A Vehicle-to-Grid (V2G) energy trading platform designed for the Indian energy market. Enable EV owners to participate in bidirectional energy trading through an auction-based marketplace with autonomous trading agents and blockchain-based SHAKTI tokens.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![React 19](https://img.shields.io/badge/react-19-blue.svg)](https://reactjs.org/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)

---

## Quick Start

Get the marketplace running in 3 commands:

```bash
# 1. Clone and navigate
git clone https://github.com/amitduabits/shaktichain.git && cd shaktichain/v2g-marketplace

# 2. Build containers
docker-compose build

# 3. Run the application
docker-compose up -d
```

**Access the application:**
- 🌐 Frontend: http://localhost
- 🔧 Backend API: http://localhost:8000
- 📚 API Docs: http://localhost:8000/docs

---

## Screenshots

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  V2G MARKETPLACE DASHBOARD                                    [User ▼] [⚙]  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │  Current Price  │  │  Energy Traded  │  │   Grid Demand   │             │
│  │   ₹ 8.50/kWh   │  │    2,450 kWh    │  │   1.4x Peak     │             │
│  │   ▲ +2.3%      │  │   ▲ +15.2%      │  │   Evening Peak  │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │  PRICE & DEMAND CHART                                    [24h ▼]      │ │
│  │                                                                       │ │
│  │  ₹12 ┤                                            ▄▄▄                 │ │
│  │      │                                         ▄▄█████▄               │ │
│  │  ₹10 ┤                    ▄▄▄▄                ██████████▄             │ │
│  │      │                 ▄▄██████▄            ▄██████████████           │ │
│  │  ₹8  ┤▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄███████████▄▄▄▄▄▄▄▄▄▄███████████████▄▄▄▄▄▄▄    │ │
│  │      │                                                                │ │
│  │  ₹6  ┤                                                                │ │
│  │      └────────────────────────────────────────────────────────────    │ │
│  │       00:00  04:00  08:00  12:00  16:00  20:00  24:00                 │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  ┌─────────────────────────────────────────┐  ┌────────────────────────┐   │
│  │  RUN SIMULATION                         │  │  AGENT DISTRIBUTION    │   │
│  │                                         │  │                        │   │
│  │  Agents: [====●============] 200        │  │  Residential: 60%      │   │
│  │  Duration: [1 day ▼]                    │  │  Commercial:  25%      │   │
│  │  Region: [Delhi NCR ▼]                  │  │  Fleet:       15%      │   │
│  │                                         │  │                        │   │
│  │  [▶ Run Simulation]                     │  │  [Apply Mix]           │   │
│  └─────────────────────────────────────────┘  └────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              V2G MARKETPLACE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐      ┌─────────────┐      ┌─────────────┐                 │
│  │   BROWSER   │      │   NGINX     │      │   REACT     │                 │
│  │   Client    │─────▶│   Reverse   │─────▶│   Frontend  │                 │
│  │             │      │   Proxy     │      │   (Vite)    │                 │
│  └─────────────┘      └──────┬──────┘      └─────────────┘                 │
│                              │                                              │
│                              │ /api/*                                       │
│                              ▼                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                         FASTAPI BACKEND                               │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │ │
│  │  │  Auth API   │  │ Simulation  │  │  Periods    │  │   Prices    │  │ │
│  │  │  /auth/*    │  │  /simul*    │  │  /periods   │  │   /prices   │  │ │
│  │  │             │  │             │  │             │  │             │  │ │
│  │  │ • Register  │  │ • Create    │  │ • Create    │  │ • Add       │  │ │
│  │  │ • Login     │  │ • List      │  │ • Get       │  │ • List      │  │ │
│  │  │ • Me        │  │ • Get       │  │             │  │             │  │ │
│  │  │             │  │ • Update    │  │             │  │             │  │ │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  │ │
│  │         │                │                │                │         │ │
│  │         └────────────────┴────────────────┴────────────────┘         │ │
│  │                                   │                                   │ │
│  │                                   ▼                                   │ │
│  │  ┌───────────────────────────────────────────────────────────────┐   │ │
│  │  │                      CORE MODULES                             │   │ │
│  │  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │   │ │
│  │  │  │   MCAFEE     │  │   SHAKTI     │  │   PROSUMER   │        │   │ │
│  │  │  │   AUCTION    │  │   TOKEN      │  │   AGENTS     │        │   │ │
│  │  │  │              │  │              │  │              │        │   │ │
│  │  │  │ Double-sided │  │ Velocity-    │  │ EV Owner     │        │   │ │
│  │  │  │ auction with │  │ based price  │  │ trading      │        │   │ │
│  │  │  │ incentive    │  │ model with   │  │ decisions    │        │   │ │
│  │  │  │ compatibility│  │ burn/mint    │  │ & battery    │        │   │ │
│  │  │  └──────────────┘  └──────────────┘  └──────────────┘        │   │ │
│  │  │  ┌──────────────┐  ┌──────────────┐                          │   │ │
│  │  │  │   INDIA      │  │  SIMULATION  │                          │   │ │
│  │  │  │   DEMAND     │  │  RUNNER      │                          │   │ │
│  │  │  │              │  │              │                          │   │ │
│  │  │  │ Regional     │  │ Full day     │                          │   │ │
│  │  │  │ load curves  │  │ simulation   │                          │   │ │
│  │  │  │ by season    │  │ engine       │                          │   │ │
│  │  │  └──────────────┘  └──────────────┘                          │   │ │
│  │  └───────────────────────────────────────────────────────────────┘   │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                   │                                         │
│                                   ▼                                         │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                           SQLITE DATABASE                             │ │
│  │  ┌─────────┐  ┌─────────────┐  ┌───────────────┐  ┌──────────────┐   │ │
│  │  │  users  │  │ simulations │  │ market_periods│  │ price_history│   │ │
│  │  └─────────┘  └─────────────┘  └───────────────┘  └──────────────┘   │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Features

### Energy Trading
- **McAfee Double Auction**: Incentive-compatible mechanism ensuring fair price discovery
- **Real-time Pricing**: Dynamic prices based on grid demand and supply
- **V2G Opportunity Detection**: Identifies optimal times for grid discharge

### Token Economics
- **SHAKTI Token**: Velocity-based pricing model for marketplace transactions
- **Deflationary Mechanics**: 30% of transaction fees burned
- **Staking Rewards**: 8% APY for token stakers

### Smart Agents
- **Autonomous Trading**: Agents make buy/sell decisions based on battery SOC and time
- **Regional Optimization**: Configured for 8 major Indian cities
- **Fleet Support**: Residential, commercial, and fleet vehicle types

### Indian Market Integration
- Compliant with CERC guidelines
- Supports state-level DISCOM integration
- Aligned with NEMMP and FAME initiatives
- Realistic demand profiles for all major Indian regions

---

## Documentation

| Document | Description |
|----------|-------------|
| [API Reference](docs/API.md) | Complete API endpoint documentation |
| [Deployment Guide](docs/DEPLOYMENT.md) | Local, Docker, and cloud deployment |
| [Architecture](docs/ARCHITECTURE.md) | System design and component details |
| [Math & Economics](docs/MATH.md) | Auction mechanism and token model |
| [Roadmap](docs/ROADMAP.md) | Features, plans, and contribution guide |
| [Launch Checklist](docs/LAUNCH_CHECKLIST.md) | Pre-production checklist |

---

## Project Structure

```
v2g-marketplace/
├── backend/
│   ├── api/
│   │   ├── main.py              # FastAPI application
│   │   ├── auth.py              # JWT authentication
│   │   └── schemas.py           # Pydantic models
│   ├── core/
│   │   ├── auction/mcafee.py    # Double auction mechanism
│   │   ├── agents/prosumer.py   # EV trading agents
│   │   ├── token/shakti.py      # Token economics
│   │   ├── demand/india_load.py # Indian load profiles
│   │   └── reports/generator.py # Report generation
│   ├── tests/                   # Comprehensive test suite
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/          # React components
│   │   ├── pages/               # Login, Register pages
│   │   ├── services/api.js      # Axios API client
│   │   └── context/AuthContext.jsx
│   ├── Dockerfile
│   └── package.json
├── simulation/
│   └── runner.py                # Simulation engine
├── scripts/
│   ├── docker-build.sh
│   ├── docker-run.sh
│   └── docker-stop.sh
├── docs/                        # Documentation
├── docker-compose.yml           # Production config
├── docker-compose.dev.yml       # Development config
└── README.md
```

---

## Technology Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | React 19, Vite, Recharts, Axios |
| **Backend** | Python 3.11, FastAPI, Uvicorn |
| **Database** | SQLite |
| **Auth** | JWT with bcrypt |
| **Container** | Docker, Docker Compose |
| **Web Server** | Nginx (reverse proxy) |
| **Testing** | Pytest, Vitest, Playwright |

---

## Development

### Prerequisites
- Python 3.11+
- Node.js 18+
- Docker & Docker Compose

### Local Development

```bash
# Backend setup
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn api.main:app --reload

# Frontend setup (new terminal)
cd frontend
npm install
npm run dev
```

### Running Tests

```bash
# Backend tests
cd backend && pytest tests/ -v

# Frontend tests
cd frontend && npm test

# E2E tests
cd frontend && npx playwright test
```

---

## Contributing

We welcome contributions! Please follow these steps:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

### Code Style
- Backend: Follow PEP 8, use type hints
- Frontend: ESLint configuration included
- Tests: Maintain >80% coverage

### Reporting Issues
- Use GitHub Issues for bug reports
- Include steps to reproduce
- Attach relevant logs or screenshots

---

## License

This project is licensed under the MIT License - see below for details:

```
MIT License

Copyright (c) 2024 ShaktiChain

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## Contact

- **Issues**: [GitHub Issues](https://github.com/amitduabits/shaktichain/issues)
- **Discussions**: [GitHub Discussions](https://github.com/amitduabits/shaktichain/discussions)

---

<p align="center">
  Made with ❤️ for India's clean energy future
</p>
