#!/usr/bin/env bash
# Starts FinBridge internal systems (:9000) and the assistant (:8000) as two separate processes.
set -e
export LLM_PROVIDER=${LLM_PROVIDER:-mock} SOURCE=world WORLD_URL=http://localhost:9000
export ASSISTANT_URL=http://localhost:8000 DEFAULT_MODE=${DEFAULT_MODE:-auto}
uvicorn world.main:app --port 9000 &
uvicorn app.main:app --port 8000 &
trap 'kill 0' EXIT; wait
