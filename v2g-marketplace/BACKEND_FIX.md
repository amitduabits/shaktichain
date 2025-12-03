# Backend Network Error - Quick Fix Guide

## Problem
Your frontend is showing "Network error - please check your connection" with failed register requests. This means the backend is not responding.

## Quick Fix (3 Steps)

### Step 1: Run Diagnostics
```bash
cd c:\Users\HP\Desktop\ShaktiChain\shaktichain\v2g-marketplace
diagnose.bat
```

This will show you exactly what's wrong.

### Step 2: Restart Backend
```bash
restart_backend.bat
```

This will:
- Kill any stuck Python processes
- Clear port 8000
- Restart the backend server

### Step 3: Verify It's Working
Open your browser and go to:
- http://localhost:8000/docs - Should show API documentation
- http://localhost:8000/api/health - Should return `{"status": "healthy"}`

## If Still Not Working

### Check 1: Port Conflict
Another program might be using port 8000.

**Find what's using the port:**
```bash
netstat -ano | findstr :8000
```

**Kill the process:**
```bash
taskkill /F /PID <process_id>
```

### Check 2: Virtual Environment Issues
The Python virtual environment might be corrupted.

**Recreate it:**
```bash
cd backend
rmdir /s /q venv
python -m venv venv
call venv\Scripts\activate.bat
pip install -r requirements.txt
```

### Check 3: Database Issues
The database might be locked or corrupted.

**Check database:**
```bash
dir data\v2g.db
dir backend\data\v2g.db
```

**If missing, reinitialize:**
```bash
cd backend
python -c "from core.database import init_db; init_db()"
```

### Check 4: Dependencies Missing
Required Python packages might not be installed.

**Reinstall dependencies:**
```bash
cd backend
call venv\Scripts\activate.bat
pip install -r requirements.txt
```

## Common Error Messages

### "Failed to connect to localhost port 8000"
**Cause**: Backend not running
**Fix**: Run `restart_backend.bat`

### "Port 8000 already in use"
**Cause**: Another process using the port
**Fix**:
```bash
netstat -ano | findstr :8000
taskkill /F /PID <process_id>
```

### "Module not found"
**Cause**: Dependencies not installed
**Fix**:
```bash
cd backend
call venv\Scripts\activate.bat
pip install -r requirements.txt
```

### "Database is locked"
**Cause**: Multiple backend instances or file lock
**Fix**:
```bash
taskkill /F /IM python.exe
timeout /t 2
restart_backend.bat
```

## CORS Issues

If backend is running but you still get network errors, it might be CORS.

**Check backend configuration:**
The backend should have CORS enabled for `http://localhost:3000` (frontend).

**File**: `backend/api/main.py`
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Frontend Configuration

**Check frontend API URL:**

**File**: `frontend/src/config.js` or `frontend/.env`
```javascript
// Should point to backend
API_URL=http://localhost:8000
```

**Or in code:**
```javascript
const API_URL = 'http://localhost:8000';
```

## Testing the Backend Manually

### 1. Test Health Endpoint
```bash
curl http://localhost:8000/api/health
```

**Expected response:**
```json
{"status": "healthy", "timestamp": "2024-12-03T..."}
```

### 2. Test Register Endpoint
```bash
curl -X POST http://localhost:8000/api/register ^
  -H "Content-Type: application/json" ^
  -d "{\"username\":\"test\",\"email\":\"test@example.com\",\"password\":\"test123\"}"
```

### 3. Check API Documentation
Open browser: http://localhost:8000/docs

Should show interactive API documentation (Swagger UI).

## Step-by-Step Debugging

### 1. Check Backend Logs
```bash
cd backend
type logs\latest.log
```

Look for error messages like:
- `ModuleNotFoundError`
- `Database error`
- `Port already in use`

### 2. Check Backend Process
```bash
tasklist | findstr python.exe
```

Should show python.exe running.

### 3. Check Port Status
```bash
netstat -ano | findstr :8000
```

Should show:
```
TCP    0.0.0.0:8000    0.0.0.0:0    LISTENING    <PID>
```

### 4. Test from Browser Console
Open browser console (F12) and run:
```javascript
fetch('http://localhost:8000/api/health')
  .then(r => r.json())
  .then(console.log)
  .catch(console.error);
```

## Nuclear Option (Full Reset)

If nothing else works, do a complete reset:

```bash
REM 1. Stop everything
taskkill /F /IM python.exe
taskkill /F /IM node.exe

REM 2. Clean up
cd backend
rmdir /s /q venv
rmdir /s /q __pycache__
del /s /q *.pyc

cd ..\frontend
rmdir /s /q node_modules
rmdir /s /q dist

REM 3. Rebuild
cd ..\backend
python -m venv venv
call venv\Scripts\activate.bat
pip install -r requirements.txt

cd ..\frontend
npm install

REM 4. Restart
cd ..
restart_backend.bat
```

## Quick Command Reference

```bash
# Diagnose issues
diagnose.bat

# Restart backend
restart_backend.bat

# Check port
netstat -ano | findstr :8000

# Kill port 8000
for /f "tokens=5" %a in ('netstat -ano ^| findstr :8000') do taskkill /F /PID %a

# Test backend
curl http://localhost:8000/api/health

# View API docs
start http://localhost:8000/docs
```

## Getting More Help

### Collect Logs
```bash
REM Backend logs
type backend\logs\latest.log > backend_debug.txt

REM System info
systeminfo > system_info.txt

REM Network info
netstat -ano > network_info.txt

REM Process info
tasklist /V > processes.txt
```

Send these files to the support team.

### Support Channels
- **GitHub Issues**: https://github.com/shaktichain/v2g-marketplace/issues
- **Email**: support@shaktichain.io
- **Slack**: #v2g-marketplace-support

---

## Success Checklist

After fixing, verify:

- [ ] `diagnose.bat` shows all OK
- [ ] http://localhost:8000/docs loads
- [ ] http://localhost:8000/api/health returns healthy
- [ ] Frontend loads without network errors
- [ ] Can register a new user
- [ ] Can login

If all checked, you're good to go! 🎉

---

**Last Updated**: 2024-12-03
**For urgent issues**: Run `diagnose.bat` and share output
