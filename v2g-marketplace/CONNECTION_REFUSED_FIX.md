# ERR_CONNECTION_REFUSED - Complete Fix

## Problem Summary

Your frontend is showing multiple `ERR_CONNECTION_REFUSED` errors because the backend is failing to start due to missing imports.

## Root Cause

The backend code was importing classes that weren't exported from the blockchain services module:
- ❌ `NetworkType`
- ❌ `TransactionStatus`
- ❌ `TransactionResult`
- ❌ `PendingTransaction`

## What I Fixed

**File**: `backend/services/blockchain/__init__.py`

**Added these exports**:
```python
from .provider import Web3Provider, get_web3_provider, NetworkType
from .transactions import (
    TransactionManager,
    TransactionStatus,
    TransactionResult,
    PendingTransaction,
)

__all__ = [
    # ... existing exports ...
    "NetworkType",
    "TransactionStatus",
    "TransactionResult",
    "PendingTransaction",
]
```

## How to Fix NOW (3 Simple Steps)

### Step 1: Test Imports Work
```bash
cd c:\Users\HP\Desktop\ShaktiChain\shaktichain\v2g-marketplace\backend
venv\Scripts\activate.bat
python test_imports.py
```

**Expected output**:
```
Testing imports...
--------------------------------------------------
1. Testing blockchain services...
   ✓ All blockchain imports successful
   ✓ NetworkType available: [...]
   ✓ TransactionStatus available: [...]

2. Testing API routes...
   ✓ Blockchain routes imported

3. Testing main app...
   ✓ Main app imported successfully

==================================================
✅ All imports successful!
==================================================
```

### Step 2: Start Backend
```bash
cd c:\Users\HP\Desktop\ShaktiChain\shaktichain\v2g-marketplace
start_backend.bat
```

**Wait for this message**:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started server process [xxxxx]
INFO:     Application startup complete.
```

### Step 3: Verify & Test

**Open new terminal and test**:
```bash
curl http://localhost:8000/api/health
```

**Expected response**:
```json
{"status":"healthy","timestamp":"..."}
```

**Or open browser**:
- http://localhost:8000/docs - Should show API documentation ✅
- http://localhost:8000/api/health - Should show health status ✅

## Frontend Will Now Work

Once the backend is running, refresh your frontend page:

**Before** (Console errors):
```
❌ POST http://localhost:8000/auth/login net::ERR_CONNECTION_REFUSED
❌ GET http://localhost:8000/health net::ERR_CONNECTION_REFUSED
```

**After** (Success):
```
✅ POST http://localhost:8000/auth/login 200 OK
✅ GET http://localhost:8000/health 200 OK
```

## Troubleshooting

### Issue: "Virtual environment not found"

**Fix**:
```bash
cd backend
python -m venv venv
venv\Scripts\activate.bat
pip install -r requirements.txt
```

### Issue: "Port 8000 already in use"

**Fix**:
```bash
# Find and kill the process
netstat -ano | findstr :8000
taskkill /F /PID <process_id>
```

**Or use PowerShell**:
```powershell
Get-NetTCPConnection -LocalPort 8000 | ForEach-Object {
    Stop-Process -Id $_.OwningProcess -Force
}
```

### Issue: "ModuleNotFoundError"

**Fix**: Reinstall dependencies
```bash
cd backend
venv\Scripts\activate.bat
pip install --upgrade pip
pip install -r requirements.txt
```

### Issue: Still getting connection errors

**Check firewall**:
```bash
# Run as Administrator
netsh advfirewall firewall add rule name="Backend 8000" dir=in action=allow protocol=TCP localport=8000
```

**Try different port**:
```bash
# In start_backend.bat, change:
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8001

# Then update frontend/.env.development:
VITE_API_URL=http://localhost:8001
```

## Quick Verification Checklist

Run through this checklist:

- [ ] `cd backend && python test_imports.py` - Shows all ✓
- [ ] `start_backend.bat` - Starts without errors
- [ ] `curl http://localhost:8000/api/health` - Returns healthy
- [ ] http://localhost:8000/docs - Loads API documentation
- [ ] Frontend console - No more ERR_CONNECTION_REFUSED
- [ ] Can register new user - Success
- [ ] Can login - Success

## Common Mistakes

### ❌ Don't Do This:
```bash
# Running from wrong directory
cd v2g-marketplace
python -m uvicorn api.main:app  # WRONG - will fail
```

### ✅ Do This Instead:
```bash
cd v2g-marketplace
start_backend.bat  # Handles everything correctly
```

### ❌ Don't Do This:
```bash
# Running without virtual environment
python -m uvicorn api.main:app  # WRONG - missing dependencies
```

### ✅ Do This Instead:
```bash
cd backend
venv\Scripts\activate.bat
cd ..
set PYTHONPATH=%CD%
cd backend
python -m uvicorn api.main:app --reload
```

## Understanding the Errors

### What `ERR_CONNECTION_REFUSED` Means

```
Frontend (Browser) → tries to connect to → Backend (Port 8000)
                                              ↓
                                         Not running!
                                              ↓
                                     ERR_CONNECTION_REFUSED
```

**Solution**: Start the backend!

### What the Import Errors Mean

```
Backend tries to start → Imports api.main
                              ↓
                         Imports routes/blockchain.py
                              ↓
                         Tries to import NetworkType
                              ↓
                         ❌ ImportError (not exported)
                              ↓
                         Backend crashes
                              ↓
                         Port 8000 not listening
                              ↓
                         Frontend can't connect
```

**Solution**: Export the missing classes (already fixed!)

## Additional Tools

### Quick Diagnostic
```bash
cd c:\Users\HP\Desktop\ShaktiChain\shaktichain\v2g-marketplace
diagnose.bat
```

Shows:
- Python installation ✓/✗
- Virtual environment ✓/✗
- Port 8000 status
- Database status
- Backend connectivity
- Frontend status

### Backend Logs

Check for errors:
```bash
cd backend
type logs\latest.log
```

Or watch in real-time:
```bash
# Start backend in one terminal
start_backend.bat

# Watch logs in another
tail -f backend\logs\latest.log
```

## Success Indicators

### Backend Started Successfully:
```
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

### Frontend Connected Successfully:
- No red errors in console
- API calls return 200 OK
- Can register/login/use features

## Next Steps After Fix

1. **Register a test user**
2. **Login with test credentials**
3. **Connect wallet** (if needed)
4. **Test core features**

## Need More Help?

### Run Diagnostics
```bash
diagnose.bat
```

### Check Backend Logs
```bash
cd backend
dir /O-D logs
type logs\<latest-file>
```

### Test Specific Endpoints
```bash
# Health
curl http://localhost:8000/api/health

# API Docs
start http://localhost:8000/docs

# Test register
curl -X POST http://localhost:8000/api/auth/register ^
  -H "Content-Type: application/json" ^
  -d "{\"username\":\"test\",\"email\":\"test@test.com\",\"password\":\"test123\"}"
```

## Files Created to Help You

1. **`start_backend.bat`** - Clean startup script
2. **`test_imports.py`** - Verify all imports work
3. **`diagnose.bat`** - System diagnostics
4. **`CONNECTION_REFUSED_FIX.md`** - This guide

---

## Quick Start Command

Just run this:
```bash
cd c:\Users\HP\Desktop\ShaktiChain\shaktichain\v2g-marketplace
start_backend.bat
```

Wait for "Application startup complete", then refresh your frontend!

---

**Status**: ✅ Import errors fixed
**Action**: Start backend with `start_backend.bat`
**Result**: Frontend should work without connection errors

**Last Updated**: 2024-12-03
