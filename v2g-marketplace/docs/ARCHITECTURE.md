# Architecture Documentation

Detailed system architecture and design documentation for V2G Marketplace.

---

## Table of Contents

- [System Overview](#system-overview)
- [High-Level Architecture](#high-level-architecture)
- [Component Details](#component-details)
- [Data Flow](#data-flow)
- [Database Schema](#database-schema)
- [Technology Choices](#technology-choices)
- [Security Architecture](#security-architecture)
- [Scalability Considerations](#scalability-considerations)

---

## System Overview

V2G Marketplace is a full-stack application enabling bidirectional energy trading between electric vehicles (EVs) and the power grid. The system consists of:

- **React Frontend**: User interface for dashboard, simulations, and analytics
- **FastAPI Backend**: REST API for business logic and data management
- **Core Modules**: Auction engine, token model, and agent simulation
- **SQLite Database**: Persistent storage for users, simulations, and market data

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         V2G MARKETPLACE SYSTEM                              │
│                                                                             │
│   ┌───────────┐    ┌───────────┐    ┌───────────┐    ┌───────────┐        │
│   │   User    │    │    EV     │    │   Grid    │    │  Admin    │        │
│   │  Browser  │    │  Owners   │    │ Operators │    │  Console  │        │
│   └─────┬─────┘    └─────┬─────┘    └─────┬─────┘    └─────┬─────┘        │
│         │                │                │                │              │
│         └────────────────┼────────────────┼────────────────┘              │
│                          │                │                               │
│                          ▼                ▼                               │
│   ┌─────────────────────────────────────────────────────────────────┐    │
│   │                     PRESENTATION LAYER                          │    │
│   │   ┌─────────────────────────────────────────────────────────┐   │    │
│   │   │              React Frontend (SPA)                       │   │    │
│   │   │  • Dashboard  • Simulations  • Charts  • Auth Pages     │   │    │
│   │   └─────────────────────────────────────────────────────────┘   │    │
│   └─────────────────────────────────────────────────────────────────┘    │
│                                    │                                      │
│                                    │ HTTP/REST                            │
│                                    ▼                                      │
│   ┌─────────────────────────────────────────────────────────────────┐    │
│   │                      API GATEWAY LAYER                          │    │
│   │   ┌─────────────────────────────────────────────────────────┐   │    │
│   │   │              Nginx Reverse Proxy                        │   │    │
│   │   │  • SSL Termination  • Load Balancing  • Rate Limiting   │   │    │
│   │   └─────────────────────────────────────────────────────────┘   │    │
│   └─────────────────────────────────────────────────────────────────┘    │
│                                    │                                      │
│                                    ▼                                      │
│   ┌─────────────────────────────────────────────────────────────────┐    │
│   │                     APPLICATION LAYER                           │    │
│   │   ┌─────────────────────────────────────────────────────────┐   │    │
│   │   │              FastAPI Backend                            │   │    │
│   │   │  • Auth API  • Simulation API  • Price API  • Period API│   │    │
│   │   └─────────────────────────────────────────────────────────┘   │    │
│   └─────────────────────────────────────────────────────────────────┘    │
│                                    │                                      │
│                                    ▼                                      │
│   ┌─────────────────────────────────────────────────────────────────┐    │
│   │                     BUSINESS LOGIC LAYER                        │    │
│   │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │    │
│   │   │   McAfee    │  │   SHAKTI    │  │  Prosumer   │             │    │
│   │   │   Auction   │  │   Token     │  │   Agents    │             │    │
│   │   └─────────────┘  └─────────────┘  └─────────────┘             │    │
│   │   ┌─────────────┐  ┌─────────────┐                              │    │
│   │   │   India     │  │ Simulation  │                              │    │
│   │   │   Demand    │  │   Runner    │                              │    │
│   │   └─────────────┘  └─────────────┘                              │    │
│   └─────────────────────────────────────────────────────────────────┘    │
│                                    │                                      │
│                                    ▼                                      │
│   ┌─────────────────────────────────────────────────────────────────┐    │
│   │                       DATA LAYER                                │    │
│   │   ┌─────────────────────────────────────────────────────────┐   │    │
│   │   │              SQLite Database                            │   │    │
│   │   │  • users  • simulations  • market_periods  • prices     │   │    │
│   │   └─────────────────────────────────────────────────────────┘   │    │
│   └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## High-Level Architecture

### Request Flow

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Client  │────▶│  Nginx   │────▶│ FastAPI  │────▶│   Core   │────▶│  SQLite  │
│ Browser  │     │  Proxy   │     │  Server  │     │ Modules  │     │    DB    │
└──────────┘     └──────────┘     └──────────┘     └──────────┘     └──────────┘
     │                │                │                │                │
     │   HTTPS/80     │   /api/*       │   Python       │   SQL          │
     │                │   Proxy        │   Function     │   Queries      │
     │                │                │   Calls        │                │
     │                │   /static      │                │                │
     │                │   React SPA    │                │                │
     │                │                │                │                │
```

### Containerized Deployment

```
┌─────────────────────────────────────────────────────────────────┐
│                     Docker Compose Network                       │
│                                                                  │
│  ┌─────────────────────┐      ┌─────────────────────┐          │
│  │   Frontend Container │      │  Backend Container  │          │
│  │                     │      │                     │          │
│  │  ┌───────────────┐  │      │  ┌───────────────┐  │          │
│  │  │    Nginx      │  │      │  │   Uvicorn     │  │          │
│  │  │   :80/:443    │◀─┼──────┼─▶│    :8000      │  │          │
│  │  └───────────────┘  │      │  └───────────────┘  │          │
│  │         │          │      │         │          │          │
│  │  ┌───────────────┐  │      │  ┌───────────────┐  │          │
│  │  │  React Build  │  │      │  │   FastAPI     │  │          │
│  │  │  (Static)     │  │      │  │   + Core      │  │          │
│  │  └───────────────┘  │      │  └───────────────┘  │          │
│  │                     │      │         │          │          │
│  └─────────────────────┘      │  ┌───────────────┐  │          │
│                               │  │   SQLite DB   │  │          │
│                               │  │   (Volume)    │  │          │
│                               │  └───────────────┘  │          │
│                               └─────────────────────┘          │
│                                                                  │
│  External Port: 80 ─────────────▶ Frontend                       │
│  External Port: 8000 ───────────▶ Backend API                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### Frontend Components

```
frontend/src/
├── components/
│   ├── Dashboard.jsx        # Main dashboard with stats and charts
│   ├── SimulationPanel.jsx  # Simulation configuration and execution
│   ├── PriceChart.jsx       # Recharts-based price visualization
│   └── AgentMixSlider.jsx   # Agent type distribution control
├── pages/
│   ├── Login.jsx            # User authentication page
│   └── Register.jsx         # New user registration
├── services/
│   └── api.js               # Axios HTTP client with interceptors
├── context/
│   └── AuthContext.jsx      # JWT token management and auth state
├── hooks/
│   └── useApi.js            # Custom API hooks
├── App.jsx                   # Root component with routing
└── main.jsx                  # Application entry point
```

**Component Responsibilities:**

| Component | Responsibility |
|-----------|----------------|
| `Dashboard` | Display current price, market stats, coordinate child components |
| `SimulationPanel` | Configure simulation parameters, run simulations, show results |
| `PriceChart` | Render price/demand time series using Recharts |
| `AgentMixSlider` | Control residential/commercial/fleet agent distribution |
| `AuthContext` | Manage JWT tokens, login state, auto-logout on expiration |
| `api.js` | Centralized HTTP client with auth header injection |

### Backend API Structure

```
backend/api/
├── main.py          # FastAPI application, routes, middleware
├── auth.py          # JWT token creation and validation
├── schemas.py       # Pydantic request/response models
└── __init__.py
```

**Endpoint Groups:**

| Group | Prefix | Description |
|-------|--------|-------------|
| Health | `/health` | Server health check |
| Auth | `/auth/*` | User authentication (register, login, me) |
| Simulations | `/simulations` | CRUD for market simulations |
| Periods | `/periods` | Market period data |
| Prices | `/prices` | Price history tracking |

### Core Modules

```
backend/core/
├── database.py              # SQLite connection and operations
├── auction/
│   └── mcafee.py            # McAfee double auction mechanism
├── agents/
│   └── prosumer.py          # EV prosumer agent implementation
├── token/
│   └── shakti.py            # SHAKTI token economics model
├── demand/
│   └── india_load.py        # Indian regional demand profiles
└── reports/
    └── generator.py         # Report generation utilities
```

**Module Responsibilities:**

| Module | Responsibility |
|--------|----------------|
| `mcafee.py` | Implement incentive-compatible double auction, compute clearing prices |
| `shakti.py` | Token pricing, velocity calculations, burn/mint mechanics |
| `prosumer.py` | EV agent decision making, bid generation, utility calculations |
| `india_load.py` | Regional and temporal demand multipliers for India |
| `database.py` | SQLite operations, table creation, CRUD functions |

---

## Data Flow

### Simulation Execution Flow

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│  User   │     │Frontend │     │ Backend │     │ Runner  │     │Database │
│         │     │         │     │   API   │     │         │     │         │
└────┬────┘     └────┬────┘     └────┬────┘     └────┬────┘     └────┬────┘
     │               │               │               │               │
     │  Click "Run   │               │               │               │
     │  Simulation"  │               │               │               │
     │──────────────▶│               │               │               │
     │               │               │               │               │
     │               │ POST /simulations             │               │
     │               │ {n_agents, n_days}            │               │
     │               │──────────────▶│               │               │
     │               │               │               │               │
     │               │               │ Create sim    │               │
     │               │               │ record        │               │
     │               │               │──────────────────────────────▶│
     │               │               │               │               │
     │               │               │ Initialize    │               │
     │               │               │ runner        │               │
     │               │               │──────────────▶│               │
     │               │               │               │               │
     │               │               │               │  For each hour:
     │               │               │               │  ┌────────────┐
     │               │               │               │  │1. Generate │
     │               │               │               │  │   demand   │
     │               │               │               │  │2. Agents   │
     │               │               │               │  │   decide   │
     │               │               │               │  │3. Submit   │
     │               │               │               │  │   bids     │
     │               │               │               │  │4. Clear    │
     │               │               │               │  │   market   │
     │               │               │               │  │5. Update   │
     │               │               │               │  │   token    │
     │               │               │               │  └────────────┘
     │               │               │               │               │
     │               │               │◀──────────────│ Results       │
     │               │               │               │               │
     │               │ {id, status,  │               │               │
     │               │  avg_price,   │               │               │
     │               │  total_volume}│               │               │
     │               │◀──────────────│               │               │
     │               │               │               │               │
     │ Display       │               │               │               │
     │ results       │               │               │               │
     │◀──────────────│               │               │               │
```

### Authentication Flow

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│  User   │     │Frontend │     │ Backend │     │Database │
└────┬────┘     └────┬────┘     └────┬────┘     └────┬────┘
     │               │               │               │
     │  Login form   │               │               │
     │  submission   │               │               │
     │──────────────▶│               │               │
     │               │               │               │
     │               │ POST /auth/login              │
     │               │ {email, password}             │
     │               │──────────────▶│               │
     │               │               │               │
     │               │               │ Query user    │
     │               │               │──────────────▶│
     │               │               │◀──────────────│
     │               │               │               │
     │               │               │ Verify bcrypt │
     │               │               │ hash          │
     │               │               │               │
     │               │               │ Generate JWT  │
     │               │               │               │
     │               │ {access_token,│               │
     │               │  token_type,  │               │
     │               │  expires_in}  │               │
     │               │◀──────────────│               │
     │               │               │               │
     │               │ Store token   │               │
     │               │ in localStorage               │
     │               │               │               │
     │ Redirect to   │               │               │
     │ dashboard     │               │               │
     │◀──────────────│               │               │
     │               │               │               │
     │─ ─ ─ ─ ─ ─ ─ ─│─ ─ ─ ─ ─ ─ ─ ─│─ ─ ─ ─ ─ ─ ─ ─│
     │               │ Subsequent requests:          │
     │               │ Authorization: Bearer <token> │
     │               │──────────────▶│               │
     │               │               │ Validate JWT  │
     │               │               │ Extract user  │
```

### Market Clearing Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    Market Clearing Process                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. DEMAND GENERATION                                            │
│     ┌─────────────────────────────────────────────┐             │
│     │  Base Load × Hour Factor × Season × Region  │             │
│     │                                             │             │
│     │  Example: 100 MW × 1.4 × 1.3 × 1.2 = 218 MW │             │
│     │           (base)  (eve) (sum) (Del)         │             │
│     └─────────────────────────────────────────────┘             │
│                         │                                        │
│                         ▼                                        │
│  2. AGENT DECISIONS                                              │
│     ┌─────────────────────────────────────────────┐             │
│     │  For each EV agent:                         │             │
│     │    - Check SOC (State of Charge)            │             │
│     │    - Check current hour                     │             │
│     │    - Decide: BUYER or SELLER                │             │
│     │    - Generate bid with price noise          │             │
│     └─────────────────────────────────────────────┘             │
│                         │                                        │
│                         ▼                                        │
│  3. BID COLLECTION                                               │
│     ┌──────────────────────┬──────────────────────┐             │
│     │       BUYERS         │       SELLERS        │             │
│     ├──────────────────────┼──────────────────────┤             │
│     │  B1: 10kWh @ ₹12     │  S1: 8kWh @ ₹6       │             │
│     │  B2: 15kWh @ ₹11     │  S2: 12kWh @ ₹7      │             │
│     │  B3: 8kWh @ ₹10      │  S3: 10kWh @ ₹7.5    │             │
│     │  B4: 12kWh @ ₹9      │  S4: 15kWh @ ₹8      │             │
│     │  B5: 20kWh @ ₹8      │  S5: 20kWh @ ₹9      │             │
│     └──────────────────────┴──────────────────────┘             │
│                         │                                        │
│                         ▼                                        │
│  4. MCAFEE AUCTION CLEARING                                      │
│     ┌─────────────────────────────────────────────┐             │
│     │  Sort buyers DESC, sellers ASC              │             │
│     │                                             │             │
│     │  Buyers:  ₹12 > ₹11 > ₹10 > ₹9 > ₹8        │             │
│     │  Sellers: ₹6 < ₹7 < ₹7.5 < ₹8 < ₹9         │             │
│     │                                             │             │
│     │  Find k where buyer[k] >= seller[k]         │             │
│     │  k=4: buyer[4]=₹9, seller[4]=₹8 ✓          │             │
│     │                                             │             │
│     │  Clearing price = (₹9 + ₹8) / 2 = ₹8.50    │             │
│     │  Matched: 4 buyers, 4 sellers               │             │
│     └─────────────────────────────────────────────┘             │
│                         │                                        │
│                         ▼                                        │
│  5. SETTLEMENT                                                   │
│     ┌─────────────────────────────────────────────┐             │
│     │  - Transfer energy from sellers to buyers   │             │
│     │  - Process SHAKTI token transaction         │             │
│     │  - Update agent SOC                         │             │
│     │  - Record period data                       │             │
│     └─────────────────────────────────────────────┘             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Database Schema

```sql
-- Users table
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'user',  -- 'user' | 'admin'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Simulations table
CREATE TABLE simulations (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    n_agents INTEGER DEFAULT 100,
    n_days INTEGER DEFAULT 1,
    status TEXT DEFAULT 'pending',  -- pending|running|completed|failed
    avg_price REAL,
    total_volume REAL
);

-- Market periods table
CREATE TABLE market_periods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    simulation_id TEXT REFERENCES simulations(id),
    period INTEGER NOT NULL,
    hour INTEGER NOT NULL,
    clearing_price REAL,
    volume REAL,
    n_buyers INTEGER,
    n_sellers INTEGER
);

-- Price history table
CREATE TABLE price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    price REAL NOT NULL,
    source TEXT NOT NULL  -- 'simulation' | 'live'
);

-- Indexes for performance
CREATE INDEX idx_simulations_created_at ON simulations(created_at DESC);
CREATE INDEX idx_market_periods_simulation ON market_periods(simulation_id);
CREATE INDEX idx_price_history_timestamp ON price_history(timestamp DESC);
```

### Entity Relationship Diagram

```
┌─────────────────┐         ┌─────────────────────┐
│      users      │         │    simulations      │
├─────────────────┤         ├─────────────────────┤
│ PK id           │         │ PK id               │
│    email        │         │    created_at       │
│    password_hash│         │    n_agents         │
│    role         │         │    n_days           │
│    created_at   │         │    status           │
└─────────────────┘         │    avg_price        │
                            │    total_volume     │
                            └──────────┬──────────┘
                                       │
                                       │ 1:N
                                       │
                            ┌──────────▼──────────┐
                            │   market_periods    │
                            ├─────────────────────┤
                            │ PK id               │
                            │ FK simulation_id    │
                            │    period           │
                            │    hour             │
                            │    clearing_price   │
                            │    volume           │
                            │    n_buyers         │
                            │    n_sellers        │
                            └─────────────────────┘

┌─────────────────────┐
│    price_history    │
├─────────────────────┤
│ PK id               │
│    timestamp        │
│    price            │
│    source           │
└─────────────────────┘
```

---

## Technology Choices

### Frontend

| Technology | Choice | Rationale |
|------------|--------|-----------|
| **Framework** | React 19 | Industry standard, large ecosystem, excellent developer experience |
| **Build Tool** | Vite | Fast HMR, modern ES modules, excellent React support |
| **HTTP Client** | Axios | Interceptors for auth, request/response transformation |
| **Charts** | Recharts | React-native, declarative, responsive |
| **State** | React Context | Simple auth state, no need for Redux complexity |
| **Styling** | CSS Modules | Scoped styles, no runtime overhead |

### Backend

| Technology | Choice | Rationale |
|------------|--------|-----------|
| **Framework** | FastAPI | Modern async Python, automatic OpenAPI docs, Pydantic validation |
| **Server** | Uvicorn | High-performance ASGI server, async support |
| **Auth** | JWT + bcrypt | Stateless authentication, industry-standard password hashing |
| **Database** | SQLite | Zero-config, file-based, sufficient for MVP scale |
| **Validation** | Pydantic | Type-safe request/response models, automatic serialization |

### Infrastructure

| Technology | Choice | Rationale |
|------------|--------|-----------|
| **Container** | Docker | Reproducible builds, consistent environments |
| **Orchestration** | Docker Compose | Simple multi-container deployment |
| **Reverse Proxy** | Nginx | Production-grade, SSL termination, static serving |
| **CI/CD** | GitHub Actions | Native GitHub integration (planned) |

### Why These Choices?

1. **FastAPI over Flask/Django**: Modern async support, automatic API documentation, better performance
2. **SQLite over PostgreSQL**: Zero configuration, no separate service needed, sufficient for current scale
3. **React over Vue/Angular**: Largest ecosystem, best hiring pool, team familiarity
4. **JWT over Sessions**: Stateless, scales horizontally, works with mobile clients
5. **Nginx over Traefik**: Mature, well-documented, simple configuration

---

## Security Architecture

### Authentication & Authorization

```
┌─────────────────────────────────────────────────────────────────┐
│                    Security Layers                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Layer 1: Transport Security                                     │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  TLS 1.2/1.3 • HSTS • Secure cookies                       │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  Layer 2: Network Security                                       │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Firewall rules • Rate limiting • DDoS protection          │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  Layer 3: Application Security                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  JWT validation • CORS • Input validation • SQL injection  │ │
│  │  prevention (parameterized queries)                        │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  Layer 4: Data Security                                          │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  bcrypt password hashing • Secrets management • Encryption │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### JWT Token Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  JWT Token Structure                                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Header (Algorithm & Type)                                       │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  { "alg": "HS256", "typ": "JWT" }                          │ │
│  └────────────────────────────────────────────────────────────┘ │
│                           │                                      │
│                           ▼                                      │
│  Payload (Claims)                                                │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  {                                                         │ │
│  │    "sub": "user_id",          // Subject (user ID)         │ │
│  │    "email": "user@example.com",                            │ │
│  │    "role": "user",            // Role for authorization    │ │
│  │    "exp": 1734567890,         // Expiration (24h)          │ │
│  │    "iat": 1734481490          // Issued at                 │ │
│  │  }                                                         │ │
│  └────────────────────────────────────────────────────────────┘ │
│                           │                                      │
│                           ▼                                      │
│  Signature                                                       │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  HMACSHA256(base64(header) + "." + base64(payload),        │ │
│  │             JWT_SECRET)                                    │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Scalability Considerations

### Current Architecture (MVP)

- **Scale**: ~1000 concurrent users
- **Database**: SQLite (single file)
- **Deployment**: Single server with Docker

### Future Scaling Path

```
┌─────────────────────────────────────────────────────────────────┐
│                    Scaling Evolution                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Stage 1: Vertical Scaling (Current → 10K users)                 │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  • Increase server resources (CPU, RAM)                    │ │
│  │  • Add caching layer (Redis)                               │ │
│  │  • Optimize database queries                               │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  Stage 2: Database Migration (10K → 100K users)                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  • Migrate SQLite → PostgreSQL                             │ │
│  │  • Add read replicas                                       │ │
│  │  • Implement connection pooling                            │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  Stage 3: Horizontal Scaling (100K+ users)                       │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  • Multiple API server instances                           │ │
│  │  • Load balancer (ALB/nginx)                               │ │
│  │  • Distributed cache (Redis Cluster)                       │ │
│  │  • Message queue for async processing (RabbitMQ/SQS)       │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  Stage 4: Microservices (1M+ users)                              │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  • Split monolith into services:                           │ │
│  │    - Auth Service                                          │ │
│  │    - Simulation Service                                    │ │
│  │    - Market Service                                        │ │
│  │    - Token Service                                         │ │
│  │  • Kubernetes orchestration                                │ │
│  │  • Service mesh (Istio)                                    │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Performance Optimization Strategies

1. **Caching**: Redis for session data, price history, frequently accessed queries
2. **Async Processing**: Background jobs for simulation runs
3. **Database Indexing**: Composite indexes on frequently queried columns
4. **CDN**: CloudFront/CloudFlare for static assets
5. **API Response Compression**: gzip/brotli for JSON responses

---

## Related Documentation

- [API Reference](API.md) - Complete endpoint documentation
- [Deployment Guide](DEPLOYMENT.md) - Infrastructure setup
- [Math & Economics](MATH.md) - Auction and token model details
