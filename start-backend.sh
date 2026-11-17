#!/usr/bin/env bash
# MindTrace backend: macOS/Linux one-command start. First run installs everything.
set -e
cd "$(dirname "$0")/backend"
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
[ -f .venv/installed.flag ] || { pip install -r requirements.txt && touch .venv/installed.flag; }
[ -f ../.env ] || cp ../.env.example ../.env
echo "MindTrace API: http://localhost:8000/docs  (teacher@mindtrace.demo / demo1234)"
exec python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
