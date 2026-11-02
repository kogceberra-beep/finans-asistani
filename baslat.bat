@echo off
cd /d "%~dp0"
start "Banka Servisi" cmd /k python -m uvicorn mock_bank:app --port 8001
timeout /t 3 /nobreak >nul
python app.py
