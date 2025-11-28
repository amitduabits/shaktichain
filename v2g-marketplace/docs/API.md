# API Reference

Complete API documentation for the V2G Marketplace backend.

**Base URL**: `http://localhost:8000` (development) | `https://api.yoursite.com` (production)

**API Documentation**: Interactive Swagger UI available at `/docs`

---

## Table of Contents

- [Authentication](#authentication)
- [Health Check](#health-check)
- [Auth Endpoints](#auth-endpoints)
- [Simulation Endpoints](#simulation-endpoints)
- [Market Period Endpoints](#market-period-endpoints)
- [Price History Endpoints](#price-history-endpoints)
- [Error Codes](#error-codes)

---

## Authentication

The API uses JWT (JSON Web Token) Bearer authentication.

### Token Format

```
Authorization: Bearer <jwt_token>
```

### Token Structure

```json
{
  "sub": "user_id",
  "email": "user@example.com",
  "role": "user",
  "exp": 1734567890,
  "iat": 1734481490
}
```

### Token Lifetime

- **Expiration**: 24 hours from issuance
- **Algorithm**: HS256
- **Refresh**: Re-login required after expiration

### Authentication Flow

```
┌─────────┐          ┌─────────┐          ┌─────────┐
│ Client  │          │   API   │          │   DB    │
└────┬────┘          └────┬────┘          └────┬────┘
     │                    │                    │
     │  POST /auth/login  │                    │
     │  {email, password} │                    │
     │───────────────────>│                    │
     │                    │  Verify password   │
     │                    │───────────────────>│
     │                    │<───────────────────│
     │                    │                    │
     │  {access_token,    │                    │
     │   token_type,      │                    │
     │   expires_in}      │                    │
     │<───────────────────│                    │
     │                    │                    │
     │  GET /simulations  │                    │
     │  Authorization:    │                    │
     │  Bearer <token>    │                    │
     │───────────────────>│                    │
     │                    │  Validate JWT      │
     │                    │  Query data        │
     │                    │───────────────────>│
     │                    │<───────────────────│
     │  [simulations]     │                    │
     │<───────────────────│                    │
```

---

## Health Check

### GET /health

Check API server health status.

**Authentication**: Not required

**Response**

```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**Example**

```bash
curl http://localhost:8000/health
```

---

## Auth Endpoints

### POST /auth/register

Register a new user account.

**Authentication**: Not required

**Request Body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `email` | string | Yes | Valid email address |
| `password` | string | Yes | Minimum 6 characters |

**Request Example**

```json
{
  "email": "user@example.com",
  "password": "securepassword123"
}
```

**Response (201 Created)**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

**Error Responses**

| Status | Description |
|--------|-------------|
| 400 | Invalid email format |
| 400 | Password too short (min 6 chars) |
| 409 | Email already registered |

**Example**

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "securepassword123"}'
```

---

### POST /auth/login

Authenticate and receive access token.

**Authentication**: Not required

**Request Body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `email` | string | Yes | Registered email |
| `password` | string | Yes | Account password |

**Request Example**

```json
{
  "email": "user@example.com",
  "password": "securepassword123"
}
```

**Response (200 OK)**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

**Error Responses**

| Status | Description |
|--------|-------------|
| 401 | Invalid email or password |

**Example**

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "securepassword123"}'
```

---

### GET /auth/me

Get current authenticated user information.

**Authentication**: Required

**Response (200 OK)**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "role": "user",
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Error Responses**

| Status | Description |
|--------|-------------|
| 401 | Missing or invalid token |

**Example**

```bash
curl http://localhost:8000/auth/me \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

## Simulation Endpoints

### POST /simulations

Create a new market simulation.

**Authentication**: Required

**Request Body**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `n_agents` | integer | No | 100 | Number of prosumer agents (50-1000) |
| `n_days` | integer | No | 1 | Simulation duration in days (1-30) |

**Request Example**

```json
{
  "n_agents": 200,
  "n_days": 7
}
```

**Response (201 Created)**

```json
{
  "id": "sim_550e8400-e29b-41d4-a716-446655440000",
  "created_at": "2024-01-15T10:30:00Z",
  "n_agents": 200,
  "n_days": 7,
  "status": "pending",
  "avg_price": null,
  "total_volume": null
}
```

**Example**

```bash
curl -X POST http://localhost:8000/simulations \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{"n_agents": 200, "n_days": 7}'
```

---

### GET /simulations

List recent simulations.

**Authentication**: Required

**Query Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `limit` | integer | No | 20 | Results per page (1-100) |

**Response (200 OK)**

```json
[
  {
    "id": "sim_550e8400-e29b-41d4-a716-446655440000",
    "created_at": "2024-01-15T10:30:00Z",
    "n_agents": 200,
    "n_days": 7,
    "status": "completed",
    "avg_price": 8.45,
    "total_volume": 15420.5
  },
  {
    "id": "sim_660e8400-e29b-41d4-a716-446655440001",
    "created_at": "2024-01-14T08:15:00Z",
    "n_agents": 100,
    "n_days": 1,
    "status": "completed",
    "avg_price": 7.82,
    "total_volume": 2150.0
  }
]
```

**Example**

```bash
curl "http://localhost:8000/simulations?limit=10" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### GET /simulations/{sim_id}

Get details of a specific simulation.

**Authentication**: Required

**Path Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `sim_id` | string | Simulation ID |

**Response (200 OK)**

```json
{
  "id": "sim_550e8400-e29b-41d4-a716-446655440000",
  "created_at": "2024-01-15T10:30:00Z",
  "n_agents": 200,
  "n_days": 7,
  "status": "completed",
  "avg_price": 8.45,
  "total_volume": 15420.5
}
```

**Error Responses**

| Status | Description |
|--------|-------------|
| 404 | Simulation not found |

**Example**

```bash
curl http://localhost:8000/simulations/sim_550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### PATCH /simulations/{sim_id}

Update simulation status or metrics.

**Authentication**: Required

**Path Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `sim_id` | string | Simulation ID |

**Request Body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `status` | string | No | pending, running, completed, failed |
| `avg_price` | float | No | Average clearing price (INR/kWh) |
| `total_volume` | float | No | Total energy traded (kWh) |

**Request Example**

```json
{
  "status": "completed",
  "avg_price": 8.45,
  "total_volume": 15420.5
}
```

**Response (200 OK)**

```json
{
  "id": "sim_550e8400-e29b-41d4-a716-446655440000",
  "created_at": "2024-01-15T10:30:00Z",
  "n_agents": 200,
  "n_days": 7,
  "status": "completed",
  "avg_price": 8.45,
  "total_volume": 15420.5
}
```

**Example**

```bash
curl -X PATCH http://localhost:8000/simulations/sim_550e8400 \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{"status": "completed", "avg_price": 8.45}'
```

---

## Market Period Endpoints

### POST /periods

Record a market period from a simulation.

**Authentication**: Required

**Request Body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `simulation_id` | string | Yes | Parent simulation ID |
| `period` | integer | Yes | Period index (0-based) |
| `hour` | integer | Yes | Hour of day (0-23) |
| `clearing_price` | float | No | Market clearing price (INR/kWh) |
| `volume` | float | No | Energy traded (kWh) |
| `n_buyers` | integer | No | Number of matched buyers |
| `n_sellers` | integer | No | Number of matched sellers |

**Request Example**

```json
{
  "simulation_id": "sim_550e8400-e29b-41d4-a716-446655440000",
  "period": 18,
  "hour": 18,
  "clearing_price": 10.25,
  "volume": 450.5,
  "n_buyers": 85,
  "n_sellers": 62
}
```

**Response (201 Created)**

```json
{
  "id": 1,
  "simulation_id": "sim_550e8400-e29b-41d4-a716-446655440000",
  "period": 18,
  "hour": 18,
  "clearing_price": 10.25,
  "volume": 450.5,
  "n_buyers": 85,
  "n_sellers": 62
}
```

**Example**

```bash
curl -X POST http://localhost:8000/periods \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{"simulation_id": "sim_550e8400", "period": 18, "hour": 18, "clearing_price": 10.25}'
```

---

### GET /simulations/{sim_id}/periods

Get all market periods for a simulation.

**Authentication**: Required

**Path Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `sim_id` | string | Simulation ID |

**Response (200 OK)**

```json
[
  {
    "id": 1,
    "simulation_id": "sim_550e8400-e29b-41d4-a716-446655440000",
    "period": 0,
    "hour": 0,
    "clearing_price": 5.20,
    "volume": 120.5,
    "n_buyers": 45,
    "n_sellers": 30
  },
  {
    "id": 2,
    "simulation_id": "sim_550e8400-e29b-41d4-a716-446655440000",
    "period": 1,
    "hour": 1,
    "clearing_price": 5.10,
    "volume": 95.0,
    "n_buyers": 38,
    "n_sellers": 28
  }
]
```

**Example**

```bash
curl http://localhost:8000/simulations/sim_550e8400/periods \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

## Price History Endpoints

### POST /prices

Add a price history entry.

**Authentication**: Not required

**Request Body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `price` | float | Yes | Price in INR/kWh |
| `source` | string | Yes | "simulation" or "live" |

**Request Example**

```json
{
  "price": 8.50,
  "source": "simulation"
}
```

**Response (201 Created)**

```json
{
  "id": 1,
  "timestamp": "2024-01-15T10:30:00Z",
  "price": 8.50,
  "source": "simulation"
}
```

**Example**

```bash
curl -X POST http://localhost:8000/prices \
  -H "Content-Type: application/json" \
  -d '{"price": 8.50, "source": "simulation"}'
```

---

### GET /prices

Get recent price history.

**Authentication**: Not required

**Query Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `limit` | integer | No | 100 | Results to return (1-1000) |

**Response (200 OK)**

```json
[
  {
    "id": 150,
    "timestamp": "2024-01-15T10:30:00Z",
    "price": 8.50,
    "source": "simulation"
  },
  {
    "id": 149,
    "timestamp": "2024-01-15T10:00:00Z",
    "price": 8.35,
    "source": "simulation"
  }
]
```

**Example**

```bash
curl "http://localhost:8000/prices?limit=50"
```

---

## Error Codes

### Standard Error Response

```json
{
  "detail": "Error message describing what went wrong"
}
```

### HTTP Status Codes

| Code | Meaning | Common Causes |
|------|---------|---------------|
| 200 | OK | Request successful |
| 201 | Created | Resource created successfully |
| 400 | Bad Request | Invalid input, validation error |
| 401 | Unauthorized | Missing/invalid/expired token |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource doesn't exist |
| 409 | Conflict | Resource already exists (e.g., duplicate email) |
| 422 | Unprocessable Entity | Request body validation failed |
| 500 | Internal Server Error | Server-side error |

### Validation Errors (422)

```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "value is not a valid email address",
      "type": "value_error.email"
    }
  ]
}
```

### Authentication Errors (401)

```json
{
  "detail": "Could not validate credentials"
}
```

```json
{
  "detail": "Token has expired"
}
```

---

## Rate Limiting

Currently, the API does not implement rate limiting. For production deployments, consider implementing:

- **Anonymous**: 100 requests/minute
- **Authenticated**: 1000 requests/minute
- **Simulation creation**: 10 requests/hour

---

## SDK Examples

### Python (requests)

```python
import requests

BASE_URL = "http://localhost:8000"

# Login
response = requests.post(f"{BASE_URL}/auth/login", json={
    "email": "user@example.com",
    "password": "securepassword123"
})
token = response.json()["access_token"]

# Create simulation
headers = {"Authorization": f"Bearer {token}"}
response = requests.post(f"{BASE_URL}/simulations",
    headers=headers,
    json={"n_agents": 200, "n_days": 1}
)
simulation = response.json()
print(f"Created simulation: {simulation['id']}")
```

### JavaScript (fetch)

```javascript
const BASE_URL = 'http://localhost:8000';

// Login
const loginResponse = await fetch(`${BASE_URL}/auth/login`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    email: 'user@example.com',
    password: 'securepassword123'
  })
});
const { access_token } = await loginResponse.json();

// Create simulation
const simResponse = await fetch(`${BASE_URL}/simulations`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${access_token}`
  },
  body: JSON.stringify({ n_agents: 200, n_days: 1 })
});
const simulation = await simResponse.json();
console.log(`Created simulation: ${simulation.id}`);
```

### cURL

```bash
# Store token in variable
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "pass123"}' \
  | jq -r '.access_token')

# Use token for authenticated requests
curl http://localhost:8000/simulations \
  -H "Authorization: Bearer $TOKEN"
```

---

## Changelog

### v1.0.0 (Current)

- Initial release
- Authentication (register, login, me)
- Simulation CRUD operations
- Market period tracking
- Price history
