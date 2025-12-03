@echo off
echo ========================================
echo SHAKTI-CHAIN Backend Startup
echo ========================================
echo.

REM Kill any existing processes on port 8000
echo [1/4] Checking for processes on port 8000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    echo Found process %%a on port 8000, stopping it...
    taskkill /F /PID %%a 2>nul
)
timeout /t 2 /nobreak >nul

REM Navigate to directory
echo [2/4] Navigating to backend directory...
cd /d "%~dp0backend"

REM Activate virtual environment
echo [3/4] Activating virtual environment...
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    echo ERROR: Virtual environment not found at backend\venv
    echo.
    echo Please create it first:
    echo   cd backend
    echo   python -m venv venv
    echo   venv\Scripts\activate.bat
    echo   pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

REM Set PYTHONPATH
cd ..
set PYTHONPATH=%CD%

REM Start backend
echo [4/4] Starting backend server...
echo.
echo ========================================
echo Server starting at: http://localhost:8000
echo API Documentation: http://localhost:8000/docs
echo Health Check: http://localhost:8000/api/health
echo ========================================
echo.
echo Backend is now running. Press Ctrl+C to stop.
echo.

cd backend
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

pause
