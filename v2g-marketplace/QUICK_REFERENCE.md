# ShaktiChain V2G Marketplace - Quick Reference Card

## ⚡ Lightning Quick Start

```cmd
setup.bat          # First time only
run_backend.bat    # Terminal 1
run_frontend.bat   # Terminal 2
```

Open: http://localhost:5173

---

## 🎯 Common Commands

### Development
```cmd
# Backend
cd backend
venv\Scripts\activate
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Frontend
cd frontend
npm run dev

# Tests
python test_integration.py
```

### Docker
```cmd
# Dev mode (hot reload)
docker-compose -f docker-compose.dev.yml up

# Production
docker-compose up

# Stop
docker-compose down
```

---

## 📡 Key API Endpoints

| Endpoint | Method | Auth? | Purpose |
|----------|--------|-------|---------|
| `/health` | GET | No | Check API health |
| `/auth/register` | POST | No | Register user |
| `/auth/login` | POST | No | Login (get JWT) |
| `/market/price` | GET | No | Current price |
| `/simulation/start` | POST | **Yes** | Start simulation |
| `/simulation/status/{id}` | GET | **Yes** | Get progress |

**Auth Header:** `Authorization: Bearer <jwt_token>`

---

## 🔧 Troubleshooting

### Backend won't start
```cmd
cd backend
pip install -r requirements.txt
python -c "from core.database import get_database; db = get_database()"
```

### Frontend can't connect
1. Check: http://localhost:8000/health
2. Clear browser localStorage: `localStorage.clear()`
3. Check `.env.development` has correct API URL

### Simulation fails
- Check backend logs in terminal
- Ensure database directory exists: `mkdir data`
- Verify Python version: `python --version` (3.9+)

---

## 📁 Important Files

| File | Purpose |
|------|---------|
| `backend/api/main.py` | All API endpoints |
| `backend/api/simulation_service.py` | Background job manager |
| `frontend/src/services/api.js` | API client |
| `frontend/src/components/SimulationPanel.jsx` | Simulation UI |
| `test_integration.py` | Integration tests |
| `INTEGRATION_GUIDE.md` | Detailed docs |

---

## 🧪 Testing Workflow

```python
# Run all integration tests
python test_integration.py
```

### Manual Test Steps
1. Register → Login → Get JWT token
2. View Dashboard → See current price
3. Start Simulation → Configure params
4. Monitor → Watch progress bar
5. View Results → See metrics
6. Download CSV → Export data

---

## 💡 Default Configuration

```
Backend:    http://localhost:8000
Frontend:   http://localhost:5173
Database:   data/v2g.db (SQLite)
API Docs:   http://localhost:8000/docs

Default Login:
  Email: test@shaktichain.com
  Password: testpass123 (after registration)

Default Simulation:
  Agents: 100
  Duration: 1 day
  Region: Delhi
  Mix: 50% residential, 30% commercial, 20% fleet
```

---

## 🚀 Deployment Checklist

### Development
- [ ] Run `setup.bat`
- [ ] Start backend: `run_backend.bat`
- [ ] Start frontend: `run_frontend.bat`
- [ ] Register test account
- [ ] Run test simulation

### Production (Docker)
- [ ] Build images: `docker-compose build`
- [ ] Start containers: `docker-compose up -d`
- [ ] Check health: `curl http://localhost:8000/health`
- [ ] Check frontend: Open http://localhost
- [ ] Create admin account
- [ ] Backup data directory

---

## 📊 Monitoring

### Check Backend Status
```cmd
# Health check
curl http://localhost:8000/health

# API docs
start http://localhost:8000/docs

# Check logs
docker-compose logs -f backend
```

### Check Frontend Status
```cmd
# Development server
# Should see "Local: http://localhost:5173"

# Production build
cd frontend
npm run build
```

### Check Database
```cmd
cd backend
python -c "from core.database import get_database; db = get_database(); print(db.list_simulations(5))"
```

---

## 🎨 UI Features

### Dashboard
- **Current Price**: Auto-updates every 30s
- **Price Chart**: Last 100 price points (₹/kWh)
- **Simulation Panel**: Configure and run simulations

### Simulation Panel
- **Agents**: 50-1000 (slider)
- **Duration**: 1, 7, or 30 days (dropdown)
- **Agent Mix**: Residential/Commercial/Fleet (sliders)
- **Region**: Delhi, Mumbai, Bangalore, Chennai (dropdown)
- **Progress**: Real-time progress bar during execution
- **Results**: Comprehensive metrics after completion

### Results Display
- Total Energy Traded (kWh)
- Average Price (₹/kWh)
- Total Transactions
- Grid Savings (₹)
- Carbon Offset (tons CO₂)
- Peak Reduction (%)

---

## 🔐 Security Notes

- JWT tokens expire after 24 hours
- Passwords hashed with bcrypt
- CORS enabled (development: all origins)
- **Production**: Change `JWT_SECRET` in `.env`

---

## 📞 Getting Help

1. **Check logs** - Terminal output for errors
2. **Run tests** - `python test_integration.py`
3. **Check docs** - [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md)
4. **API docs** - http://localhost:8000/docs
5. **Browser console** - F12 → Console tab

---

## 🎯 Success Indicators

✅ Backend health check returns `{"status": "healthy"}`
✅ Frontend loads at http://localhost:5173
✅ Login/register works
✅ Price chart displays data
✅ Simulation completes successfully
✅ CSV download works
✅ Integration tests pass

---

**Version**: 1.0.0 (Fully Integrated)
**Last Updated**: 2025-01-28
**Status**: ✅ Production Ready
