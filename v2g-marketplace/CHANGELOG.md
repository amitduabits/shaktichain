# Changelog

All notable changes to V2G Marketplace will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-01-15

### Added

#### Core Platform
- **McAfee Double Auction Engine**: Incentive-compatible mechanism for energy trading
  - Fair price discovery through sorted bid matching
  - Multi-unit trading support
  - Budget-balanced clearing

- **SHAKTI Token Model**: Native marketplace token
  - Velocity-based pricing formula
  - Deflationary burn mechanism (30% of transaction fees)
  - Staking rewards (8% APY)
  - Supply and price history tracking

- **Prosumer Agent System**: Autonomous trading agents
  - Three agent types: residential, commercial, fleet
  - SOC-based decision making
  - Time-of-use optimization
  - Bid generation with valuation noise

- **Indian Demand Modeling**: Realistic grid demand profiles
  - Hourly load curves (morning/evening peaks)
  - Day-of-week variations (weekday/weekend)
  - Seasonal adjustments (summer peak at 1.3x)
  - 8 regional profiles (Delhi, Mumbai, Bangalore, Chennai, etc.)

#### Backend API
- **Authentication**: JWT-based auth with bcrypt password hashing
  - POST /auth/register - User registration
  - POST /auth/login - User authentication
  - GET /auth/me - Current user info

- **Simulations**: Market simulation management
  - POST /simulations - Create simulation
  - GET /simulations - List simulations
  - GET /simulations/{id} - Get simulation details
  - PATCH /simulations/{id} - Update simulation

- **Market Data**:
  - POST /periods - Record market period
  - GET /simulations/{id}/periods - Get simulation periods
  - POST /prices - Add price history
  - GET /prices - Get price history

- **Health Check**: GET /health endpoint

#### Frontend
- **Dashboard**: Main interface with real-time stats
  - Current price display (30s refresh)
  - Market statistics cards
  - Price/demand chart

- **Simulation Panel**: Simulation configuration UI
  - Agent count slider (50-1000)
  - Duration selection (1/7/30 days)
  - Agent mix configuration (residential/commercial/fleet)
  - Region selector (8 Indian cities)
  - Progress tracking with ETA
  - Results display with CSV export

- **Authentication UI**:
  - Login page with validation
  - Registration page with password confirmation
  - Session management with auto-logout

#### Infrastructure
- **Docker Support**:
  - Multi-stage Dockerfile for backend
  - Multi-stage Dockerfile for frontend
  - docker-compose.yml for production
  - docker-compose.dev.yml for development
  - Health checks for all services

- **Helper Scripts**:
  - docker-build.sh (prod/dev/no-cache)
  - docker-run.sh (prod/dev/foreground)
  - docker-stop.sh (prod/dev/volumes)

#### Testing
- Comprehensive pytest test suite for backend
- Vitest component tests for frontend
- Playwright E2E tests
- Test coverage > 80%

#### Documentation
- README.md with quick start guide
- API.md - Complete API documentation
- DEPLOYMENT.md - Deployment guide (local, Docker, cloud)
- ARCHITECTURE.md - System design documentation
- MATH.md - Mathematical foundations
- ROADMAP.md - Feature roadmap
- LAUNCH_CHECKLIST.md - Production checklist

### Security
- JWT authentication with 24-hour expiration
- bcrypt password hashing with salt
- Parameterized SQL queries
- CORS configuration
- Input validation with Pydantic

---

## [Unreleased]

### Planned
- Real-time WebSocket updates
- PostgreSQL database support
- Mobile-responsive design
- DISCOM API integration
- Staking interface
- Admin dashboard

---

[1.0.0]: https://github.com/amitduabits/shaktichain/releases/tag/v1.0.0
[Unreleased]: https://github.com/amitduabits/shaktichain/compare/v1.0.0...HEAD
