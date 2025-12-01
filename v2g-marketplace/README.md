# V2G Marketplace

A Vehicle-to-Grid (V2G) energy trading platform designed for the Indian energy market.

## Overview

V2G Marketplace enables electric vehicle (EV) owners to participate in India's energy ecosystem by allowing bidirectional energy flow between EVs and the power grid. This platform facilitates peer-to-peer energy trading, grid stabilization services, and optimized charging/discharging schedules.

## Key Features

- **Energy Trading**: Buy and sell energy between EVs and the grid through an auction-based marketplace
- **Smart Agents**: Autonomous agents that optimize charging/discharging decisions based on grid demand and pricing
- **Token-based Transactions**: Secure and transparent energy transactions using blockchain-based tokens
- **Grid Integration**: Seamless integration with Indian DISCOM (Distribution Companies) systems
- **Real-time Pricing**: Dynamic pricing based on Time-of-Day (ToD) tariffs and grid conditions

## Project Structure

```
v2g-marketplace/
├── backend/
│   ├── api/              # REST API endpoints
│   ├── core/
│   │   ├── auction/      # Auction engine for energy trading
│   │   ├── agents/       # Smart agents for automated trading
│   │   └── token/        # Token management and transactions
│   ├── tests/            # Unit and integration tests
│   └── requirements.txt  # Python dependencies
├── frontend/             # Web interface (coming soon)
├── simulation/           # Grid and EV simulation tools
├── docs/                 # Documentation
└── README.md
```

## Indian Energy Market Context

This platform is designed to work within India's regulatory framework:

- Compliant with CERC (Central Electricity Regulatory Commission) guidelines
- Supports integration with state-level DISCOMs
- Aligned with India's National Electric Mobility Mission Plan (NEMMP)
- Compatible with FAME (Faster Adoption and Manufacturing of Electric Vehicles) initiatives

## Use Cases

1. **Peak Load Management**: EVs discharge to grid during peak hours (6-10 PM) when demand is highest
2. **Renewable Integration**: Store excess solar energy during daytime and supply back during evening peak
3. **Frequency Regulation**: Provide ancillary services for grid frequency stabilization
4. **Demand Response**: Participate in demand response programs offered by DISCOMs

## Getting Started

### Prerequisites

- Python 3.9+
- Node.js 18+ (for frontend)
- Docker & Docker Compose (for containerized deployment)

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd v2g-marketplace

# Set up backend
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run tests
pytest tests/
```

## Docker Deployment

The application can be deployed using Docker for both development and production environments.

### Quick Start with Docker

```bash
# Build and run in production mode
./scripts/docker-build.sh
./scripts/docker-run.sh

# Access the application
# Frontend: http://localhost
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Development Mode (Hot Reload)

```bash
# Build and run with hot reload enabled
./scripts/docker-build.sh --dev
./scripts/docker-run.sh --dev

# Access the application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
```

### Docker Commands

#### Build Images
```bash
# Production build
./scripts/docker-build.sh

# Development build
./scripts/docker-build.sh --dev

# Build without cache
./scripts/docker-build.sh --no-cache
```

#### Run Containers
```bash
# Production mode (detached)
./scripts/docker-run.sh

# Development mode with hot reload
./scripts/docker-run.sh --dev

# Run in foreground (see logs)
./scripts/docker-run.sh --foreground

# Build and run
./scripts/docker-run.sh --build
```

#### Stop Containers
```bash
# Stop production containers
./scripts/docker-stop.sh

# Stop development containers
./scripts/docker-stop.sh --dev

# Stop all containers
./scripts/docker-stop.sh --all

# Stop and remove volumes (WARNING: deletes data)
./scripts/docker-stop.sh --volumes
```

### Docker Compose Files

| File | Description |
|------|-------------|
| `docker-compose.yml` | Production configuration |
| `docker-compose.dev.yml` | Development with hot reload |

### Manual Docker Commands

```bash
# Production
docker-compose up -d
docker-compose logs -f
docker-compose down

# Development
docker-compose -f docker-compose.dev.yml up -d
docker-compose -f docker-compose.dev.yml logs -f
docker-compose -f docker-compose.dev.yml down
```

### Data Persistence

Data is persisted in the `./data` directory, which is mounted as a volume. This includes:
- SQLite database (`v2g.db`)
- Simulation results
- Generated reports

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///data/v2g.db` | Database connection URL |
| `DEBUG` | `0` | Enable debug mode (dev only) |
| `PYTHONUNBUFFERED` | `1` | Python output buffering |

## Contributing

We welcome contributions! Please see our contributing guidelines in the docs folder.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contact

For questions or support regarding this V2G platform, please open an issue in the repository.
