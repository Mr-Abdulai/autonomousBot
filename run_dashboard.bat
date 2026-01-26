@echo off
echo ===================================================
echo   SENTIENT TRADER - DASHBOARD LAUNCHER
echo ===================================================

echo [1/2] Starting Backend API (Port 8000)...
start "Sentient API" /min cmd /c "call venv\Scripts\activate.bat && python -m uvicorn app.api:app --reload --port 8000"

echo [2/2] Starting Web Dashboard (Port 5173)...
cd web-dashboard
start "Sentient Dashboard" /min cmd /c "npm run dev"

echo.
echo ===================================================
echo   SUCCESS! 
echo ===================================================
echo   Access the Dashboard here:
echo   http://localhost:5173
echo.
echo   (Minimizing launcher in 5 seconds...)
timeout /t 5
