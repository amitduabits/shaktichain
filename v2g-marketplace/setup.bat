@echo off
REM ShaktiChain V2G Marketplace - Windows Setup Script

echo ========================================
echo ShaktiChain V2G Marketplace Setup
echo ========================================
echo.

REM Check Python installation
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.9 or higher
    pause
    exit /b 1
)

REM Check Node.js installation
node --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js is not installed or not in PATH
    echo Please install Node.js 16 or higher
    pause
    exit /b 1
)

echo [1/4] Setting up Backend...
echo.

REM Create backend virtual environment
cd backend
if not exist venv (
    echo Creating Python virtual environment...
    python -m venv venv
)

REM Activate virtual environment and install dependencies
echo Installing backend dependencies...
call venv\Scripts\activate.bat
pip install --upgrade pip
pip install -r requirements.txt

REM Initialize database
echo Initializing database...
python -c "from core.database import get_database; db = get_database(); print('Database initialized successfully')"

cd ..

echo.
echo [2/4] Setting up Frontend...
echo.

REM Install frontend dependencies
cd frontend
if not exist node_modules (
    echo Installing npm packages...
    call npm install
) else (
    echo Frontend dependencies already installed
)

cd ..

echo.
echo [3/4] Creating data directories...
if not exist data mkdir data

echo.
echo [4/4] Setup complete!
echo.
echo ========================================
echo Next Steps:
echo ========================================
echo.
echo To run the application:
echo.
echo   1. Start Backend:  run_backend.bat
echo   2. Start Frontend: run_frontend.bat
echo.
echo Or use Docker:
echo   docker-compose up
echo.
echo ========================================
pause
