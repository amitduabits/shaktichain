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

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd v2g-marketplace

# Set up backend
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run tests
pytest tests/
```

## Contributing

We welcome contributions! Please see our contributing guidelines in the docs folder.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contact

For questions or support regarding this V2G platform, please open an issue in the repository.
