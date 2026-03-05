@echo off
echo Starting SmartClinic...

start "Backend" cmd /k "cd /d d:\Backup\SmartClinic\backend && uvicorn app.main:app --reload"

timeout /t 3 /nobreak >nul

start "Frontend" cmd /k "cd /d d:\Backup\SmartClinic\frontend && npm run dev"

echo Both servers starting...
echo Backend: http://localhost:8000
echo Frontend: http://localhost:3000
echo.
pause
