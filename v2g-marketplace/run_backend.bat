@echo off
echo Starting ShaktiChain Backend Server...
cd backend
call venv\Scripts\activate.bat
cd ..
set PYTHONPATH=%CD%
cd backend
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
