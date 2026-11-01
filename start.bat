@echo off
REM ShopDesk - script khoi dong cho Windows
REM Cach dung: mo File Explorer, vao thu muc shopdesk, nhap doi start.bat roi Enter
cd /d "%~dp0"

echo === ShopDesk ===

REM 1. Kiem tra Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo LOI: Chua cai Python. Tai va cai Python 3.10 tro len tai https://www.python.org/downloads/
    echo Luu y: khi cai dat nho tick chon "Add python.exe to PATH".
    pause
    exit /b 1
)

REM 2. Cai thu vien neu thieu Flask
python -c "import flask" >nul 2>nul
if %errorlevel% neq 0 (
    echo Dang cai thu vien can thiet (Flask, requests)...
    python -m pip install -r requirements.txt
)

REM 3. Chay app
echo Khoi dong ShopDesk tai http://localhost:8000
echo Nhan Ctrl+C de dung.
python app.py
pause
