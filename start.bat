@echo off
rem Project Nowhere - update and start in one step (Windows). Double-click this file, or run it from a terminal.
rem  1) git pull  2) install/refresh Python packages  3) build the web app  4) open the app window
chcp 65001 >nul
cd /d "%~dp0"

echo [1/4] Pulling the latest code...
git pull origin main
if errorlevel 1 goto :fail

echo [2/4] Python packages...
python -m pip install -q -r requirements.txt
if errorlevel 1 goto :fail

echo [3/4] Building the web app...
pushd web
call npm install --no-audit --no-fund
if errorlevel 1 (popd & goto :fail)
call npm run build
if errorlevel 1 (popd & goto :fail)
popd

echo [4/4] Starting Nowhere...
python launch.py
exit /b 0

:fail
echo.
echo Something failed above. Fix it (or send the message to Claude) and run this file again.
pause
exit /b 1
