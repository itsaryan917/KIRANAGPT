#!/usr/bin/env bash
# KiranaGPT — Start both servers
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"

if [ ! -f "$ROOT/.env" ]; then
  echo "❌  .env not found. Run: bash setup.sh first"
  exit 1
fi

if [ ! -f "$ROOT/frontend/.env.local" ]; then
  cp "$ROOT/frontend/.env.local.example" "$ROOT/frontend/.env.local"
fi

# Export backend env
set -a; source "$ROOT/.env"; set +a

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║        KiranaGPT — Starting              ║"
echo "╚══════════════════════════════════════════╝"

echo "▶ Backend  → http://localhost:8000"
cd "$ROOT"
uvicorn app:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

echo "▶ Frontend → http://localhost:3000"
cd "$ROOT/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "  API docs → http://localhost:8000/docs"
echo "  Press Ctrl+C to stop"
echo ""

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM
wait
