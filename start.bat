@echo off
echo ========================================
echo   LLM Security Gateway - Start
echo ========================================
echo.
echo [1/2] Starting backend (port 5001)...
start "Backend" cmd /k "cd /d %~dp0backend && python run_modular.py"

echo [2/2] Starting frontend (port 51438)...
start "Frontend" cmd /k "cd /d %~dp0frontend && python -m http.server 51438"

timeout /t 3 /nobreak >nul

echo.
echo ========================================
echo   Started!
echo   Backend:  http://127.0.0.1:5001
echo   Frontend: http://127.0.0.1:51438
echo ========================================
echo.

start http://127.0.0.1:51438

pause
