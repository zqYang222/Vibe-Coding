@echo off
cd /d "%~dp0"
echo ==============================================
echo   Online Judge - starting services...
echo ==============================================
echo.

start "OJ-Backend-8000" cmd /k "python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
start "OJ-Frontend-8501" cmd /k "python -m streamlit run frontend/app.py --server.port 8501"

timeout /t 3 /nobreak >nul
start "" http://localhost:8501

echo.
echo   Backend  : http://127.0.0.1:8000
echo   Frontend : http://localhost:8501   (browser should open)
echo.
echo   Close the two command windows to stop the servers.
echo   Login: admin / admintestpassword
echo.
pause
