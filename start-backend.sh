#!/usr/bin/env bash
# MindTrace backend: macOS/Linux one-command start. First run installs everything.
set -e
cd "$(dirname "$0")/backend"
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
cmp -s requirements.txt .venv/installed.flag || { pip install -r requirements.txt && cp requirements.txt .venv/installed.flag; }
[ -f ../.env ] || cp ../.env.example ../.env
[ -f ../frontend/dist/index.html ] || { command -v npm >/dev/null && (cd ../frontend && npm ci && npm run build); } || true
echo "MindTrace website: http://localhost:8000  (API docs /docs; teacher@mindtrace.demo / demo1234)"
exec python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
