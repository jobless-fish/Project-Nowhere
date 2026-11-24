#!/usr/bin/env bash
# Project Nowhere - update and start in one step (macOS / Linux).
set -e
cd "$(dirname "$0")"
echo "[1/4] Pulling the latest code..."; git pull origin main
echo "[2/4] Python packages...";        python3 -m pip install -q -r requirements.txt
echo "[3/4] Building the web app...";   (cd web && npm install --no-audit --no-fund && npm run build)
echo "[4/4] Starting Nowhere...";       exec python3 launch.py
