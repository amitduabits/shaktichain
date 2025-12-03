@echo off
echo ========================================
echo SHAKTI-CHAIN Backend Restart Script
echo ========================================
echo.

REM Kill any existing backend process
echo [1/5] Stopping existing backend processes...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq *uvicorn*" 2>nul
taskkill /F /FI "WINDOWTITLE eq *ShaktiChain Backend*" 2>nul
timeout /t 2 /nobreak >nul

REM Clear port 8000 if stuck
echo [2/5] Checking port 8000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    echo Killing process on port 8000: %%a
    taskkill /F /PID %%a 2>nul
)
timeout /t 1 /nobreak >nul

REM Navigate to directory
echo [3/5] Setting up environment...
cd /d "%~dp0backend"

REM Activate virtual environment
echo [4/5] Activating virtual environment...
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    echo ERROR: Virtual environment not found!
    echo Please run setup.bat first
    pause
    exit /b 1
)

REM Set Python path
cd ..
set PYTHONPATH=%CD%
cd backend

REM Start backend
echo [5/5] Starting backend server...
echo.
echo ========================================
echo Backend starting on http://localhost:8000
echo API Docs: http://localhost:8000/docs
echo Health Check: http://localhost:8000/api/health
echo ========================================
echo.
echo Press Ctrl+C to stop the server
echo.

python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

pause
