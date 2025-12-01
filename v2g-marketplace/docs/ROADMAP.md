# Product Roadmap

V2G Marketplace development roadmap, completed features, and contribution guide.

---

## Table of Contents

- [Vision](#vision)
- [Completed Features](#completed-features)
- [Planned Features](#planned-features)
- [Known Limitations](#known-limitations)
- [How to Contribute](#how-to-contribute)

---

## Vision

V2G Marketplace aims to become India's leading platform for Vehicle-to-Grid energy trading, enabling:

1. **Democratized Energy Trading**: Allow any EV owner to participate in energy markets
2. **Grid Stability**: Help balance India's growing renewable energy capacity
3. **Economic Benefits**: Create new revenue streams for EV owners
4. **Sustainable Future**: Accelerate EV adoption through V2G incentives

---

## Completed Features

### v1.0.0 (Current Release)

#### Core Platform
- [x] **McAfee Double Auction Engine**
  - Incentive-compatible bid matching
  - Fair price discovery
  - Multi-unit trading support

- [x] **SHAKTI Token Model**
  - Velocity-based pricing
  - Deflationary burn mechanism (30% of fees)
  - Staking rewards (8% APY)
  - Supply tracking and history

- [x] **Prosumer Agent System**
  - Three agent types: residential, commercial, fleet
  - SOC-based decision making
  - Time-of-use optimization
  - Bid generation with noise

- [x] **Indian Demand Modeling**
  - Hourly load profiles (morning/evening peaks)
  - Day-of-week variations
  - Seasonal adjustments (summer peak)
  - 8 regional profiles (Delhi, Mumbai, etc.)

#### Backend API
- [x] **Authentication System**
  - JWT-based authentication
  - User registration and login
  - bcrypt password hashing
  - 24-hour token expiration

- [x] **Simulation Management**
  - Create simulations with configurable agents/duration
  - Track simulation status
  - Store results and metrics

- [x] **Market Data**
  - Period-by-period clearing prices
  - Volume tracking
  - Price history

#### Frontend
- [x] **Dashboard**
  - Real-time price display
  - Market statistics
  - Price/demand charts

- [x] **Simulation Interface**
  - Agent count slider (50-1000)
  - Duration selection (1/7/30 days)
  - Agent mix configuration
  - Region selector
  - Progress tracking
  - Results display

- [x] **Authentication UI**
  - Login page
  - Registration page
  - Session management
  - Auto-logout on expiration

#### Infrastructure
- [x] **Docker Containerization**
  - Multi-stage builds
  - Production and development configs
  - Health checks
  - Volume persistence

- [x] **Testing Suite**
  - Backend unit tests (pytest)
  - Frontend component tests (Vitest)
  - E2E tests (Playwright)

- [x] **Documentation**
  - API reference
  - Deployment guide
  - Architecture documentation
  - Mathematical foundations

---

## Planned Features

### v1.1.0 - Enhanced Trading

| Feature | Description | Priority |
|---------|-------------|----------|
| **Real-time Bidding** | WebSocket-based live bid updates | High |
| **Order Book Visualization** | Display live buy/sell orders | High |
| **Bid History** | Track user's past bids and outcomes | Medium |
| **Price Alerts** | Notify users of price thresholds | Medium |
| **Mobile-responsive UI** | Optimize for mobile devices | Medium |

### v1.2.0 - Advanced Analytics

| Feature | Description | Priority |
|---------|-------------|----------|
| **Portfolio Dashboard** | Track earnings, energy traded, carbon offset | High |
| **Market Analytics** | Historical trends, volatility metrics | High |
| **Agent Performance** | Individual agent profitability analysis | Medium |
| **Export Reports** | PDF/CSV export of trading history | Medium |
| **Predictive Pricing** | ML-based price forecasting | Low |

### v1.3.0 - Grid Integration

| Feature | Description | Priority |
|---------|-------------|----------|
| **DISCOM API Integration** | Connect to state utilities | High |
| **Smart Meter Support** | Real-time energy metering | High |
| **Demand Response** | Automated response to grid signals | Medium |
| **Ancillary Services** | Frequency regulation, spinning reserve | Medium |
| **Renewable Forecasting** | Solar/wind availability predictions | Low |

### v1.4.0 - Token Ecosystem

| Feature | Description | Priority |
|---------|-------------|----------|
| **Staking Interface** | UI for staking/unstaking SHAKTI | High |
| **Governance Voting** | Token holder voting on parameters | Medium |
| **Rewards Dashboard** | Track staking rewards | Medium |
| **Token Transfers** | P2P token transfers | Medium |
| **Multi-chain Support** | Bridge to Ethereum/Polygon | Low |

### v2.0.0 - Enterprise Features

| Feature | Description | Priority |
|---------|-------------|----------|
| **Fleet Management** | Multi-vehicle management for fleets | High |
| **API for Third Parties** | Public API for integrators | High |
| **Admin Dashboard** | Platform administration tools | High |
| **Audit Logging** | Compliance and audit trails | Medium |
| **Multi-tenancy** | Support multiple organizations | Medium |
| **SLA Management** | Service level agreements | Low |

---

## Known Limitations

### Current Limitations

| Limitation | Impact | Workaround | Planned Fix |
|------------|--------|------------|-------------|
| **SQLite Database** | Single-server only, limited concurrent writes | Sufficient for MVP scale | v1.2: PostgreSQL migration |
| **No Real Grid Connection** | Simulation only, no actual energy flow | Use for planning and modeling | v1.3: DISCOM integration |
| **Single Region Support** | Can't run multi-region simultaneously | Run separate instances | v1.2: Multi-region support |
| **No Mobile App** | Desktop browser only | Responsive web design | v2.0: Native mobile apps |
| **Manual Token Operations** | No blockchain integration | Simulated tokens | v1.4: On-chain tokens |
| **No Rate Limiting** | Vulnerable to API abuse | Trusted users only | v1.1: Rate limiting |
| **Basic Error Handling** | Generic error messages | Check logs for details | v1.1: Detailed errors |

### Technical Debt

| Item | Description | Priority |
|------|-------------|----------|
| Add request validation middleware | Centralize input validation | Medium |
| Implement database migrations | Alembic for schema changes | High |
| Add API versioning | Support /v1/, /v2/ endpoints | Medium |
| Improve test coverage | Target 90%+ coverage | High |
| Add logging aggregation | ELK stack or CloudWatch | Medium |
| Implement caching layer | Redis for frequently accessed data | Low |

### Security Considerations

| Item | Status | Notes |
|------|--------|-------|
| HTTPS/TLS | Deployment-dependent | Use Let's Encrypt in production |
| CORS configuration | Permissive (*) | Restrict in production |
| Rate limiting | Not implemented | Add before public launch |
| Input sanitization | Basic validation | Add comprehensive sanitization |
| SQL injection | Protected (parameterized) | Maintain with new features |
| XSS protection | React escapes by default | Review any dangerouslySetInnerHTML |

---

## How to Contribute

We welcome contributions from the community! Here's how to get involved:

### Getting Started

1. **Fork the Repository**
   ```bash
   # Fork on GitHub, then clone your fork
   git clone https://github.com/YOUR_USERNAME/shaktichain.git
   cd shaktichain/v2g-marketplace
   ```

2. **Set Up Development Environment**
   ```bash
   # Backend
   cd backend
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt

   # Frontend
   cd ../frontend
   npm install
   ```

3. **Create a Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

### Contribution Guidelines

#### Code Style

**Python (Backend)**:
- Follow PEP 8
- Use type hints
- Maximum line length: 100 characters
- Use docstrings for public functions

```python
def calculate_clearing_price(
    buyers: list[Bid],
    sellers: list[Bid]
) -> tuple[float, int]:
    """
    Calculate market clearing price using McAfee mechanism.

    Args:
        buyers: List of buyer bids, sorted by price descending
        sellers: List of seller asks, sorted by price ascending

    Returns:
        Tuple of (clearing_price, matched_count)
    """
    ...
```

**JavaScript (Frontend)**:
- ESLint configuration included
- Use functional components with hooks
- PropTypes for component props

```javascript
/**
 * Price chart component displaying energy prices over time.
 * @param {Object} props
 * @param {Array} props.data - Price data points
 * @param {string} props.timeRange - Time range ('24h', '7d', '30d')
 */
function PriceChart({ data, timeRange }) {
  ...
}
```

#### Commit Messages

Use conventional commits format:

```
type(scope): description

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting (no code change)
- `refactor`: Code restructuring
- `test`: Adding tests
- `chore`: Maintenance tasks

Examples:
```
feat(auction): add support for multi-unit bids

fix(auth): handle expired token refresh

docs(api): update simulation endpoint examples

test(token): add unit tests for burn mechanism
```

#### Pull Request Process

1. **Update Documentation**
   - Add docstrings for new functions
   - Update API.md for new endpoints
   - Update README if needed

2. **Add Tests**
   - Unit tests for new functions
   - Integration tests for new endpoints
   - Maintain >80% coverage

3. **Run CI Checks**
   ```bash
   # Backend
   cd backend
   pytest tests/ -v --cov

   # Frontend
   cd frontend
   npm test
   npm run lint
   ```

4. **Submit PR**
   - Reference any related issues
   - Describe changes clearly
   - Include screenshots for UI changes

### Areas for Contribution

#### Good First Issues

- [ ] Add loading spinners for API calls
- [ ] Improve error messages on login failure
- [ ] Add unit tests for prosumer agent
- [ ] Update API documentation with more examples
- [ ] Add input validation for simulation parameters

#### Help Wanted

- [ ] Implement WebSocket for real-time updates
- [ ] Add PostgreSQL support
- [ ] Create Kubernetes deployment manifests
- [ ] Build mobile-responsive design
- [ ] Add internationalization (i18n) support

#### Feature Requests

Have an idea? Open an issue with the `enhancement` label:

1. **Problem Statement**: What problem does this solve?
2. **Proposed Solution**: How should it work?
3. **Alternatives**: Other approaches considered
4. **Additional Context**: Screenshots, mockups, references

### Community

- **Issues**: [GitHub Issues](https://github.com/amitduabits/shaktichain/issues)
- **Discussions**: [GitHub Discussions](https://github.com/amitduabits/shaktichain/discussions)
- **Code of Conduct**: Be respectful, inclusive, and constructive

### Recognition

Contributors are recognized in:
- CONTRIBUTORS.md file
- Release notes
- Project documentation

---

## Release Schedule

| Version | Target | Focus |
|---------|--------|-------|
| v1.0.0 | **Released** | Core platform, MVP |
| v1.1.0 | Q1 2025 | Real-time trading |
| v1.2.0 | Q2 2025 | Analytics & database |
| v1.3.0 | Q3 2025 | Grid integration |
| v1.4.0 | Q4 2025 | Token ecosystem |
| v2.0.0 | 2026 | Enterprise features |

---

## Feedback

We value your feedback! Please share:
- Bug reports via GitHub Issues
- Feature requests via GitHub Discussions
- General feedback via email (coming soon)

Thank you for your interest in V2G Marketplace!
