# API Reference

Complete API documentation for the V2G Marketplace platform.

**Base URL**: `http://localhost:8000`
**API Version**: 1.0
**Authentication**: JWT Bearer Token

## Table of Contents

- [Authentication](#authentication)
- [Simulations](#simulations)
- [Market Data](#market-data)
- [Async Simulation](#async-simulation)
- [Blockchain Operations](#blockchain-operations)
- [Health & Monitoring](#health--monitoring)
- [Error Codes](#error-codes)

---

## Authentication

### Register User

Create a new user account.

**Endpoint**: `POST /auth/register`

**Request Body**:
```json
{
  "email": "user@example.com",
  "password": "securePassword123",
  "role": "trader"
}
```

**Response** (201 Created):
```json
{
  "id": 1,
  "email": "user@example.com",
  "role": "trader",
  "created_at": "2025-12-03T10:30:00Z"
}
```

**Errors**:
- `400 Bad Request`: Email already registered
- `422 Unprocessable Entity`: Validation error

**Example**:
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "trader@example.com",
    "password": "MySecurePass123"
  }'
```

---

### Login

Authenticate and receive JWT token.

**Endpoint**: `POST /auth/login`

**Request Body**:
```json
{
  "email": "user@example.com",
  "password": "securePassword123"
}
```

**Response** (200 OK):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

**Token Contents** (decoded):
```json
{
  "sub": "1",
  "email": "user@example.com",
  "role": "trader",
  "exp": 1735819800,
  "iat": 1735733400
}
```

**Example**:
```bash
# Login and save token
TOKEN=$(curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password"}' \
  | jq -r '.access_token')

# Use token in subsequent requests
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/simulations
```

---

### Get Current User

**Endpoint**: `GET /auth/me`

**Headers**: `Authorization: Bearer <token>`

**Response** (200 OK):
```json
{
  "id": 1,
  "email": "user@example.com",
  "role": "trader",
  "created_at": "2025-12-01T08:00:00Z"
}
```

---

## Simulations

### Create Simulation

Create a new energy market simulation.

**Endpoint**: `POST /simulations`

**Headers**:
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Request Body**:
```json
{
  "n_agents": 300,
  "n_days": 7,
  "agent_mix": {
    "residential": 60,
    "commercial": 30,
    "fleet": 10
  },
  "region": "Delhi",
  "demand_mode": "realistic"
}
```

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `n_agents` | integer | Yes | Number of agents (50-1000) |
| `n_days` | integer | Yes | Duration in days (1-365) |
| `agent_mix` | object | Yes | Distribution (must sum to 100%) |
| `region` | string | Yes | Delhi, Mumbai, Bangalore, Chennai, etc. |
| `demand_mode` | string | No | "flat", "realistic", "hourly", "custom" |

**Response** (201 Created):
```json
{
  "id": 42,
  "created_at": "2025-12-03T10:30:00Z",
  "n_agents": 300,
  "n_days": 7,
  "status": "pending",
  "avg_price": null,
  "total_volume": null,
  "region": "Delhi",
  "agent_mix": {
    "residential": 60,
    "commercial": 30,
    "fleet": 10
  }
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/simulations \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "n_agents": 300,
    "n_days": 7,
    "agent_mix": {"residential": 60, "commercial": 30, "fleet": 10},
    "region": "Delhi"
  }'
```

---

### List Simulations

**Endpoint**: `GET /simulations`

**Query Parameters**:
| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `limit` | integer | Max results | 50 |
| `offset` | integer | Pagination offset | 0 |
| `status` | string | Filter: pending/running/completed/failed | all |

**Response** (200 OK):
```json
{
  "total": 127,
  "limit": 50,
  "offset": 0,
  "simulations": [
    {
      "id": 42,
      "created_at": "2025-12-03T10:30:00Z",
      "n_agents": 300,
      "n_days": 7,
      "status": "completed",
      "avg_price": 4.85,
      "total_volume": 8750.5,
      "region": "Delhi"
    }
  ]
}
```

**Example**:
```bash
# Get completed simulations
curl -X GET "http://localhost:8000/simulations?status=completed&limit=20" \
  -H "Authorization: Bearer $TOKEN"
```

---

### Get Simulation Details

**Endpoint**: `GET /simulations/{id}`

**Response** (200 OK):
```json
{
  "id": 42,
  "created_at": "2025-12-03T10:30:00Z",
  "n_agents": 300,
  "n_days": 7,
  "status": "completed",
  "avg_price": 4.85,
  "total_volume": 8750.5,
  "region": "Delhi",
  "agent_mix": {
    "residential": 60,
    "commercial": 30,
    "fleet": 10
  },
  "completed_at": "2025-12-03T10:45:00Z",
  "duration_seconds": 890
}
```

---

### Update Simulation

**Endpoint**: `PATCH /simulations/{id}`

**Request Body**:
```json
{
  "status": "completed",
  "avg_price": 4.85,
  "total_volume": 8750.5
}
```

**Response** (200 OK):
```json
{
  "id": 42,
  "status": "completed",
  "avg_price": 4.85,
  "total_volume": 8750.5,
  "updated_at": "2025-12-03T10:45:00Z"
}
```

---

## Market Data

### Record Market Period

Save hourly market clearing results.

**Endpoint**: `POST /periods`

**Request Body**:
```json
{
  "simulation_id": 42,
  "period": 5,
  "hour": 14,
  "clearing_price": 5.20,
  "volume": 125.5,
  "n_buyers": 85,
  "n_sellers": 72
}
```

**Response** (201 Created):
```json
{
  "id": 1234,
  "simulation_id": 42,
  "period": 5,
  "hour": 14,
  "clearing_price": 5.20,
  "volume": 125.5,
  "n_buyers": 85,
  "n_sellers": 72,
  "created_at": "2025-12-03T14:00:00Z"
}
```

---

### Get Simulation Periods

**Endpoint**: `GET /simulations/{id}/periods`

**Query**: `?limit=168` (7 days × 24 hours)

**Response** (200 OK):
```json
{
  "simulation_id": 42,
  "total_periods": 168,
  "periods": [
    {
      "id": 1234,
      "period": 5,
      "hour": 14,
      "clearing_price": 5.20,
      "volume": 125.5,
      "n_buyers": 85,
      "n_sellers": 72
    }
  ]
}
```

---

### Get Current Market Price

**Endpoint**: `GET /market/price`

**Response** (200 OK):
```json
{
  "price": 4.85,
  "timestamp": "2025-12-03T14:30:00Z",
  "source": "simulation",
  "currency": "INR",
  "unit": "kWh"
}
```

---

### Get Price History

**Endpoint**: `GET /market/price/history?limit=100`

**Response** (200 OK):
```json
{
  "start_time": "2025-12-02T14:30:00Z",
  "end_time": "2025-12-03T14:30:00Z",
  "data_points": 24,
  "prices": [
    {
      "timestamp": "2025-12-03T14:00:00Z",
      "price": 4.85
    },
    {
      "timestamp": "2025-12-03T13:00:00Z",
      "price": 4.92
    }
  ]
}
```

---

## Async Simulation

For long-running simulations with job tracking.

### Start Async Simulation

**Endpoint**: `POST /simulation/start`

**Request Body**:
```json
{
  "n_agents": 300,
  "n_days": 7,
  "agent_mix": {
    "residential": 60,
    "commercial": 30,
    "fleet": 10
  },
  "region": "Delhi",
  "enable_token_economics": true
}
```

**Response** (202 Accepted):
```json
{
  "job_id": "sim_abc123xyz",
  "status": "pending",
  "created_at": "2025-12-03T14:30:00Z",
  "estimated_duration_seconds": 900
}
```

---

### Check Simulation Status

**Endpoint**: `GET /simulation/status/{job_id}`

**Response - Running** (200 OK):
```json
{
  "job_id": "sim_abc123xyz",
  "status": "running",
  "progress": 45,
  "current_period": 76,
  "total_periods": 168,
  "started_at": "2025-12-03T14:30:00Z",
  "elapsed_seconds": 405
}
```

**Response - Completed** (200 OK):
```json
{
  "job_id": "sim_abc123xyz",
  "status": "completed",
  "progress": 100,
  "started_at": "2025-12-03T14:30:00Z",
  "completed_at": "2025-12-03T14:45:00Z",
  "duration_seconds": 890,
  "results": {
    "avg_price": 4.85,
    "total_volume": 8750.5,
    "n_periods": 168,
    "clearing_efficiency": 0.94
  }
}
```

**Status Values**:
- `pending`: Job queued
- `running`: In progress
- `completed`: Finished successfully
- `failed`: Error occurred

**Example - Polling**:
```bash
while true; do
  curl -X GET http://localhost:8000/simulation/status/sim_abc123xyz \
    -H "Authorization: Bearer $TOKEN"
  sleep 5
done
```

---

### Download Simulation Results

**Endpoint**: `GET /simulation/download/{job_id}`

**Response** (200 OK):
```csv
period,hour,clearing_price,volume,n_buyers,n_sellers,demand_multiplier
1,0,4.20,95.5,65,58,0.75
1,1,4.15,88.2,62,55,0.70
1,2,4.10,82.0,58,52,0.68
```

**Example**:
```bash
curl -X GET http://localhost:8000/simulation/download/sim_abc123xyz \
  -H "Authorization: Bearer $TOKEN" \
  -o simulation_results.csv
```

---

## Blockchain Operations

All blockchain endpoints prefixed with `/api/blockchain`.

### Get Token Balance

**Endpoint**: `GET /api/blockchain/tokens/balance/{address}`

**Response** (200 OK):
```json
{
  "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb4",
  "balance": "1250.5",
  "decimals": 18,
  "symbol": "SHAKTI"
}
```

---

### Get Auction Status

**Endpoint**: `GET /api/blockchain/auction/status`

**Response** (200 OK):
```json
{
  "round": 1234,
  "status": "bidding",
  "start_time": "2025-12-03T14:00:00Z",
  "end_time": "2025-12-03T15:00:00Z",
  "total_bids": 247,
  "clearing_price": null
}
```

**Status**: `bidding` | `clearing` | `settled`

---

### Submit Auction Bid

**Endpoint**: `POST /api/blockchain/auction/bid`

**Request Body**:
```json
{
  "is_buy": true,
  "quantity": 10.0,
  "price": 5.20,
  "wallet_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb4"
}
```

**Response** (201 Created):
```json
{
  "bid_id": "bid_xyz789",
  "transaction_hash": "0x1a2b3c...",
  "status": "pending",
  "estimated_confirmation_time": 30
}
```

**Example**:
```bash
# Submit buy order
curl -X POST http://localhost:8000/api/blockchain/auction/bid \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "is_buy": true,
    "quantity": 10.0,
    "price": 5.20,
    "wallet_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb4"
  }'
```

---

### Get Staking Info

**Endpoint**: `GET /api/blockchain/staking/{address}`

**Response** (200 OK):
```json
{
  "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb4",
  "staked_amount": "500.0",
  "rewards_earned": "2.35",
  "apy": 8.0,
  "stake_start_time": "2025-11-01T00:00:00Z"
}
```

---

### Stake Tokens

**Endpoint**: `POST /api/blockchain/staking/stake`

**Request Body**:
```json
{
  "amount": 1000,
  "wallet_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb4"
}
```

**Response** (201 Created):
```json
{
  "transaction_hash": "0x1a2b3c...",
  "amount": 1000,
  "new_total_staked": 1500,
  "estimated_apy": 8.0
}
```

---

### Unstake Tokens

**Endpoint**: `POST /api/blockchain/staking/unstake`

**Request Body**:
```json
{
  "amount": 500,
  "wallet_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb4"
}
```

**Response** (200 OK):
```json
{
  "transaction_hash": "0x2b3c4d...",
  "amount": 500,
  "rewards_claimed": 2.35,
  "new_total_staked": 1000
}
```

---

### Claim Staking Rewards

**Endpoint**: `POST /api/blockchain/staking/claim`

**Request Body**:
```json
{
  "wallet_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb4"
}
```

**Response** (200 OK):
```json
{
  "transaction_hash": "0x3c4d5e...",
  "rewards_claimed": 2.35,
  "remaining_rewards": 0
}
```

---

### Get User Reputation

**Endpoint**: `GET /api/blockchain/reputation/{address}`

**Response** (200 OK):
```json
{
  "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb4",
  "reputation_score": 87,
  "total_trades": 145,
  "successful_trades": 142,
  "reliability_rate": 0.979,
  "member_since": "2025-09-15T00:00:00Z"
}
```

---

### Get Trade History

**Endpoint**: `GET /api/blockchain/trades/{address}?limit=50&offset=0`

**Response** (200 OK):
```json
{
  "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb4",
  "total_trades": 145,
  "trades": [
    {
      "trade_id": "trade_123",
      "timestamp": "2025-12-03T14:00:00Z",
      "is_buy": true,
      "quantity": 10.0,
      "price": 5.20,
      "total_value": 52.0,
      "transaction_hash": "0x1a2b3c..."
    }
  ]
}
```

---

## Health & Monitoring

### Liveness Check

**Endpoint**: `GET /health`

**Response** (200 OK):
```json
{
  "status": "healthy",
  "timestamp": "2025-12-03T14:30:00Z"
}
```

---

### Readiness Check

**Endpoint**: `GET /health/ready`

**Response** (200 OK):
```json
{
  "status": "ready",
  "checks": {
    "database": "ok",
    "blockchain": "ok"
  },
  "timestamp": "2025-12-03T14:30:00Z"
}
```

---

### Prometheus Metrics

**Endpoint**: `GET /metrics`

**Response** (200 OK):
```prometheus
# HELP api_requests_total Total API requests
# TYPE api_requests_total counter
api_requests_total{method="GET",endpoint="/simulations"} 1247
api_requests_total{method="POST",endpoint="/simulations"} 89

# HELP api_request_duration_seconds Request latency
# TYPE api_request_duration_seconds histogram
api_request_duration_seconds_bucket{le="0.005"} 450
api_request_duration_seconds_bucket{le="0.01"} 890
api_request_duration_seconds_sum 245.3
api_request_duration_seconds_count 1336

# HELP simulation_runs_total Total simulations
# TYPE simulation_runs_total counter
simulation_runs_total 127

# HELP active_agents_count Current active agents
# TYPE active_agents_count gauge
active_agents_count 347
```

---

## Error Codes

### HTTP Status Codes

| Code | Meaning | Description |
|------|---------|-------------|
| 200 | OK | Success |
| 201 | Created | Resource created |
| 202 | Accepted | Async request accepted |
| 400 | Bad Request | Invalid parameters |
| 401 | Unauthorized | Invalid/missing auth |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource doesn't exist |
| 422 | Unprocessable Entity | Validation error |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error |

### Error Response Format

```json
{
  "error": {
    "code": "INVALID_PARAMETERS",
    "message": "Agent mix percentages must sum to 100",
    "details": {
      "provided_sum": 95,
      "expected_sum": 100
    }
  }
}
```

### Common Error Codes

| Code | Description |
|------|-------------|
| `INVALID_CREDENTIALS` | Login failed |
| `TOKEN_EXPIRED` | JWT expired |
| `TOKEN_INVALID` | Malformed JWT |
| `RESOURCE_NOT_FOUND` | Resource doesn't exist |
| `INVALID_PARAMETERS` | Validation failed |
| `SIMULATION_FAILED` | Execution error |
| `BLOCKCHAIN_ERROR` | Transaction failed |
| `RATE_LIMIT_EXCEEDED` | Too many requests |

---

## Rate Limiting

| Endpoint Category | Rate Limit | Window |
|------------------|------------|--------|
| Authentication | 10 requests | 1 minute |
| Simulation (create) | 10 requests | 1 minute |
| Market data (read) | 100 requests | 1 minute |
| Blockchain operations | 20 requests | 1 minute |
| Health checks | Unlimited | - |

**Rate Limit Headers**:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1735733520
```

---

## WebSocket Support

For real-time blockchain updates:

**Endpoint**: `ws://localhost:8000/ws/blockchain`

**Connection**:
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/blockchain');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Blockchain event:', data);
};
```

**Event Types**:
- `auction_cleared`: New auction cleared
- `trade_executed`: Trade completed
- `token_transfer`: Token transferred
- `staking_updated`: Staking updated

**Example Message**:
```json
{
  "event": "auction_cleared",
  "timestamp": "2025-12-03T15:00:00Z",
  "data": {
    "round": 1234,
    "clearing_price": 5.15,
    "volume": 1250.5,
    "n_trades": 145
  }
}
```

---

## API Client Libraries

### Python

```python
import requests

class V2GClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.token = None

    def login(self, email, password):
        response = requests.post(
            f"{self.base_url}/auth/login",
            json={"email": email, "password": password}
        )
        self.token = response.json()["access_token"]
        return self.token

    def create_simulation(self, n_agents, n_days, agent_mix, region):
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.post(
            f"{self.base_url}/simulations",
            headers=headers,
            json={
                "n_agents": n_agents,
                "n_days": n_days,
                "agent_mix": agent_mix,
                "region": region
            }
        )
        return response.json()

# Usage
client = V2GClient()
client.login("user@example.com", "password")
sim = client.create_simulation(
    n_agents=300,
    n_days=7,
    agent_mix={"residential": 60, "commercial": 30, "fleet": 10},
    region="Delhi"
)
print(f"Created simulation: {sim['id']}")
```

### JavaScript

```javascript
class V2GClient {
  constructor(baseURL = 'http://localhost:8000') {
    this.baseURL = baseURL;
    this.token = null;
  }

  async login(email, password) {
    const response = await fetch(`${this.baseURL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    const data = await response.json();
    this.token = data.access_token;
    return this.token;
  }

  async createSimulation(nAgents, nDays, agentMix, region) {
    const response = await fetch(`${this.baseURL}/simulations`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        n_agents: nAgents,
        n_days: nDays,
        agent_mix: agentMix,
        region: region
      })
    });
    return await response.json();
  }
}

// Usage
const client = new V2GClient();
await client.login('user@example.com', 'password');
const sim = await client.createSimulation(
  300, 7,
  { residential: 60, commercial: 30, fleet: 10 },
  'Delhi'
);
console.log(`Created simulation: ${sim.id}`);
```

---

## Interactive Documentation

Test APIs interactively at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

**For API support, contact: support@v2g-marketplace.com**
