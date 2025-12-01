# ShaktiChain V2G Marketplace - Integration Guide

## 🎯 Complete Integration Overview

This guide explains how the frontend and backend are now fully integrated and aligned.

---

## ✅ What Has Been Fixed

### 1. **API Endpoint Alignment**

All frontend API calls now match backend endpoints perfectly:

| Frontend Call | Backend Endpoint | Status |
|--------------|------------------|--------|
| `register()` | `POST /auth/register` | ✅ Aligned |
| `login()` | `POST /auth/login` | ✅ Aligned |
| `getCurrentUser()` | `GET /auth/me` | ✅ Aligned |
| `getCurrentPrice()` | `GET /market/price` | ✅ **NEW** |
| `getPriceHistory()` | `GET /market/price/history` | ✅ **NEW** |
| `startSimulation()` | `POST /simulation/start` | ✅ **NEW** |
| `getSimulationStatus()` | `GET /simulation/status/{jobId}` | ✅ **NEW** |
| `downloadSimulationCsv()` | `GET /simulation/download/{jobId}` | ✅ **NEW** |
| `getProsumers()` | `GET /prosumers` | ✅ **NEW** (placeholder) |

### 2. **New Backend Services Created**

#### **SimulationService** ([backend/api/simulation_service.py](backend/api/simulation_service.py))
- Manages background simulation execution in separate threads
- Tracks job status and progress
- Stores results in database
- Generates CSV exports

#### **Market Endpoints** (backend/api/main.py)
- `/market/price` - Returns current energy price
- `/market/price/history` - Returns historical price data
- Integrated with price_history database table

#### **Simulation Endpoints** (backend/api/main.py)
- `/simulation/start` - Starts background simulation job
- `/simulation/status/{job_id}` - Returns real-time progress
- `/simulation/download/{job_id}` - Downloads CSV results

### 3. **Frontend Updates**

#### **PriceChart Component**
- Now fetches **real data** from `/market/price/history`
- Auto-refreshes every 30 seconds
- Falls back to sample data if API unavailable
- Updated to show **INR (₹)** currency instead of USD

#### **Dashboard Component**
- Shows current price from `/market/price`
- Updated to display **₹** (Indian Rupees)
- Real-time price polling every 30 seconds

#### **SimulationPanel Component**
- Fully integrated with backend simulation service
- Shows real-time progress during simulation
- Displays comprehensive results after completion
- CSV download functionality working

### 4. **Database Integration**

All simulation results are now persisted:
- **simulations** table - Stores simulation metadata
- **market_periods** table - Stores hourly clearing results
- **price_history** table - Stores price time series
- **users** table - Authentication data

### 5. **Configuration Files Created**

- `.env.example` - Template with all configuration options
- `frontend/.env.development` - Frontend dev environment
- `frontend/.env.production` - Frontend production environment

### 6. **Setup Scripts Created**

- `setup.bat` - Complete Windows setup automation
- `run_backend.bat` - Start backend server
- `run_frontend.bat` - Start frontend server
- `test_integration.py` - End-to-end integration tests

---

## 🚀 Quick Start Guide

### Prerequisites

- Python 3.9+
- Node.js 16+
- Git

### Option 1: Automated Setup (Windows)

```cmd
# Run the setup script
setup.bat

# Start backend (in one terminal)
run_backend.bat

# Start frontend (in another terminal)
run_frontend.bat
```

### Option 2: Manual Setup

#### Backend Setup

```cmd
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run server
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

#### Frontend Setup

```cmd
cd frontend

# Install dependencies
npm install

# Run dev server
npm run dev
```

### Option 3: Docker Setup

```cmd
# Development mode (with hot reload)
docker-compose -f docker-compose.dev.yml up

# Production mode
docker-compose up
```

---

## 🧪 Testing the Integration

### Run Automated Integration Tests

```cmd
# Make sure backend is running on http://localhost:8000
python test_integration.py
```

This will test:
1. API health check
2. User registration
3. User login
4. Authentication token validation
5. Current price retrieval
6. Price history retrieval
7. Simulation creation
8. Simulation status polling
9. Results retrieval
10. CSV download

### Manual Testing

1. **Start Backend**: `run_backend.bat`
2. **Start Frontend**: `run_frontend.bat`
3. **Open Browser**: http://localhost:5173
4. **Register Account**: Use the registration page
5. **Login**: Login with your credentials
6. **View Dashboard**: See current price and price history chart
7. **Run Simulation**:
   - Adjust number of agents (50-1000)
   - Select duration (1, 7, or 30 days)
   - Adjust agent mix (residential/commercial/fleet)
   - Select region (Delhi, Mumbai, Bangalore, Chennai)
   - Click "Run Simulation"
8. **Watch Progress**: Real-time progress bar updates
9. **View Results**: Comprehensive metrics after completion
10. **Download CSV**: Export detailed results

---

## 📊 Data Flow Architecture

```
┌─────────────────┐
│  React Frontend │
│   (Port 5173)   │
└────────┬────────┘
         │
         │ HTTP/REST API
         │ (axios with JWT)
         ▼
┌─────────────────┐
│  FastAPI Backend│
│   (Port 8000)   │
└────────┬────────┘
         │
         ├──────────────────────┬────────────────────┐
         ▼                      ▼                    ▼
┌────────────────┐    ┌──────────────────┐  ┌─────────────────┐
│ SimulationService│    │   Database       │  │  Simulation     │
│  (Threading)    │    │   (SQLite)       │  │   Runner        │
└────────┬────────┘    └──────────────────┘  └─────────────────┘
         │                      │                      │
         │                      │                      │
         │  ┌───────────────────┴──────────┬──────────┘
         │  ▼                              ▼
         │  Simulations Table     ┌────────────────┐
         │  Market Periods        │ Core Modules:  │
         │  Price History         │ - Prosumer     │
         └─────────────────────── │ - McAfee       │
                                  │ - Token Model  │
                                  │ - India Load   │
                                  └────────────────┘
```

---

## 🔑 Key Integration Points

### 1. Authentication Flow

```javascript
// Frontend: Login
const response = await login({ email, password });
localStorage.setItem('auth_token', response.access_token);

// Backend: Validate
@app.get("/protected-route")
async def protected(user: dict = Depends(get_current_user)):
    return {"user_id": user["id"]}
```

### 2. Simulation Workflow

```javascript
// Frontend: Start simulation
const { job_id } = await startSimulation(params);

// Backend: Background execution
sim_service = get_simulation_service(db)
job_id = sim_service.start_simulation(...)

// Thread runs SimulationRunner
runner = SimulationRunner(config)
result = runner.run()

// Save to database
db.save_simulation(...)
db.save_period(...)
db.save_price(...)
```

### 3. Real-time Updates

```javascript
// Frontend: Poll every 2 seconds
const pollStatus = async (job_id) => {
  const status = await getSimulationStatus(job_id);
  // Update UI with progress, current_day, etc.
};

setInterval(() => pollStatus(job_id), 2000);
```

---

## 📝 API Endpoint Reference

### Authentication

```
POST   /auth/register       # Register new user
POST   /auth/login          # Login and get JWT token
GET    /auth/me             # Get current user info (requires auth)
```

### Market Data

```
GET    /market/price              # Get current energy price
GET    /market/price/history      # Get price history (default 100 records)
```

### Simulations

```
POST   /simulation/start          # Start new simulation (requires auth)
GET    /simulation/status/{id}    # Get simulation progress (requires auth)
GET    /simulation/download/{id}  # Download CSV results (requires auth)
```

### Database Management

```
POST   /simulations               # Create simulation record (requires auth)
GET    /simulations               # List recent simulations (requires auth)
GET    /simulations/{id}          # Get simulation details (requires auth)
PATCH  /simulations/{id}          # Update simulation (requires auth)
POST   /periods                   # Create market period (requires auth)
GET    /simulations/{id}/periods  # Get simulation periods (requires auth)
POST   /prices                    # Add price history entry
GET    /prices                    # Get recent prices
```

### Utility

```
GET    /health                    # API health check
GET    /prosumers                 # List prosumers (placeholder)
GET    /prosumers/{id}            # Get prosumer details (placeholder)
```

---

## 🛠️ Troubleshooting

### Backend won't start

```cmd
# Check Python version
python --version  # Should be 3.9+

# Reinstall dependencies
cd backend
pip install --upgrade pip
pip install -r requirements.txt

# Check database
python -c "from core.database import get_database; db = get_database(); print('OK')"
```

### Frontend won't connect to backend

1. **Check backend is running**: Visit http://localhost:8000/health
2. **Check CORS settings**: Backend allows all origins by default
3. **Check API URL**: Should be `http://localhost:8000` in `.env.development`
4. **Check browser console**: Look for network errors

### Simulation fails

```cmd
# Check backend logs for Python errors
# Common issues:
# 1. Missing dependencies (pip install -r requirements.txt)
# 2. Import path issues (check PYTHONPATH)
# 3. Database write permissions (check data/ directory)
```

### Authentication fails

```cmd
# Clear browser localStorage
# In browser console:
localStorage.clear()

# Re-register user
# Check backend logs for JWT errors
```

---

## 🎨 Currency & Localization

The application now uses **Indian Rupees (₹)** throughout:

- Price displays: `₹6.00/kWh` instead of `$0.12/kWh`
- All calculations use INR base price (₹6.00/kWh)
- Results show grid savings in INR
- Charts display ₹ symbol

---

## 📦 Project Structure

```
v2g-marketplace/
├── backend/
│   ├── api/
│   │   ├── main.py                    # ✅ Updated with new endpoints
│   │   ├── auth.py                    # JWT authentication
│   │   ├── schemas.py                 # Pydantic models
│   │   └── simulation_service.py      # 🆕 Background simulation manager
│   ├── core/
│   │   ├── database.py                # SQLite database handler
│   │   ├── agents/prosumer.py         # EV prosumer model
│   │   ├── auction/mcafee.py          # Double auction mechanism
│   │   ├── demand/india_load.py       # Indian demand profiles
│   │   ├── token/shakti.py            # SHAKTI token economics
│   │   └── reports/generator.py       # Report generation
│   ├── tests/                         # Unit tests
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Dashboard.jsx          # ✅ Updated INR display
│   │   │   ├── PriceChart.jsx         # ✅ Real data integration
│   │   │   └── SimulationPanel.jsx    # ✅ Full integration
│   │   ├── services/
│   │   │   └── api.js                 # ✅ All endpoints aligned
│   │   ├── context/
│   │   │   └── AuthContext.jsx        # JWT token management
│   │   └── pages/
│   │       ├── Login.jsx
│   │       └── Register.jsx
│   ├── .env.development               # 🆕 Dev environment config
│   ├── .env.production                # 🆕 Prod environment config
│   └── package.json
├── simulation/
│   └── runner.py                      # Simulation execution engine
├── data/                              # SQLite database storage
├── .env.example                       # 🆕 Configuration template
├── setup.bat                          # 🆕 Automated setup
├── run_backend.bat                    # 🆕 Backend launcher
├── run_frontend.bat                   # 🆕 Frontend launcher
├── test_integration.py                # 🆕 E2E integration tests
├── docker-compose.yml                 # Production deployment
└── docker-compose.dev.yml             # Development deployment
```

---

## 🎯 Next Steps

The integration is now complete! Here's what you can do:

### Immediate
1. ✅ Run `setup.bat` to install everything
2. ✅ Run `test_integration.py` to verify all endpoints
3. ✅ Start both servers and test the UI

### Short-term Enhancements
- [ ] Add WebSocket support for real-time simulation updates (no polling)
- [ ] Implement prosumer tracking and live agent visualization
- [ ] Add date range filtering for price history
- [ ] Create simulation comparison dashboard

### Long-term Features
- [ ] Integrate with actual blockchain for SHAKTI token
- [ ] Connect to real DISCOM APIs for live grid data
- [ ] Add multi-region support with geolocation
- [ ] Implement ML-based demand forecasting
- [ ] Add mobile app (React Native)

---

## 📞 Support

If you encounter any issues:

1. Check this integration guide
2. Review the troubleshooting section
3. Run `test_integration.py` to identify the issue
4. Check backend logs (terminal output)
5. Check frontend console (browser DevTools)

---

**Last Updated**: 2025-01-28
**Integration Status**: ✅ **COMPLETE**
**Test Coverage**: ✅ **PASSING**

