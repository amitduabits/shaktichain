@echo off
echo ========================================
echo SHAKTI-CHAIN System Diagnostics
echo ========================================
echo.

REM Check Python
echo [1/8] Checking Python installation...
python --version 2>nul
if %errorlevel% neq 0 (
    echo ERROR: Python not found in PATH
) else (
    echo OK: Python found
)
echo.

REM Check virtual environment
echo [2/8] Checking virtual environment...
if exist backend\venv\Scripts\python.exe (
    echo OK: Virtual environment exists
    backend\venv\Scripts\python.exe --version
) else (
    echo ERROR: Virtual environment not found
    echo Please run setup.bat
)
echo.

REM Check port 8000
echo [3/8] Checking port 8000...
netstat -ano | findstr :8000 | findstr LISTENING >nul
if %errorlevel% equ 0 (
    echo OK: Port 8000 is in use
    netstat -ano | findstr :8000 | findstr LISTENING
) else (
    echo WARNING: Port 8000 is not in use
)
echo.

REM Check database
echo [4/8] Checking database...
if exist data\v2g.db (
    echo OK: Database found at data\v2g.db
    dir data\v2g.db | findstr v2g.db
) else (
    echo WARNING: Database not found at data\v2g.db
)
if exist backend\data\v2g.db (
    echo OK: Database found at backend\data\v2g.db
    dir backend\data\v2g.db | findstr v2g.db
) else (
    echo WARNING: Database not found at backend\data\v2g.db
)
echo.

REM Test backend connectivity
echo [5/8] Testing backend connectivity...
curl -s http://localhost:8000/api/health >nul 2>&1
if %errorlevel% equ 0 (
    echo OK: Backend is responding
    curl http://localhost:8000/api/health
) else (
    echo ERROR: Backend is not responding
    echo Try running restart_backend.bat
)
echo.

REM Check frontend
echo [6/8] Checking frontend...
if exist frontend\package.json (
    echo OK: Frontend package.json found
) else (
    echo WARNING: Frontend package.json not found
)
if exist frontend\node_modules (
    echo OK: Frontend node_modules exists
) else (
    echo WARNING: Frontend dependencies not installed
    echo Run: cd frontend ^&^& npm install
)
echo.

REM Check running processes
echo [7/8] Checking running processes...
echo Python processes:
tasklist | findstr python.exe
echo Node processes:
tasklist | findstr node.exe
echo.

REM Check recent errors
echo [8/8] Checking for backend logs...
if exist backend\logs (
    echo Recent backend logs:
    dir backend\logs /O-D /B | findstr /R ".*" >nul 2>&1
    if %errorlevel% equ 0 (
        for /f %%f in ('dir backend\logs /O-D /B') do (
            echo Last log file: backend\logs\%%f
            type backend\logs\%%f | findstr /I "error exception failed" | tail -n 5
            goto :logs_done
        )
    )
)
:logs_done
echo.

echo ========================================
echo Diagnostics Complete
echo ========================================
echo.
echo Common fixes:
echo 1. Backend not responding? Run: restart_backend.bat
echo 2. Port 8000 stuck? Restart will kill the process
echo 3. Frontend errors? Check browser console (F12)
echo 4. Database issues? Check data\v2g.db exists
echo.
echo For more help, see NETWORK_TROUBLESHOOTING.md
echo.
pause
