#!/usr/bin/env bash
# KiranaGPT Setup Script — run once after unzipping
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║        KiranaGPT — Setup                 ║"
echo "╚══════════════════════════════════════════╝"

echo "▶ Installing Python dependencies..."
cd "$ROOT"
pip install -r backend/requirements.txt
echo "  ✅ Python deps installed"

echo "▶ Installing Node.js dependencies..."
cd "$ROOT/frontend"
npm install
echo "  ✅ Node deps installed"

cd "$ROOT"
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "  ✅ Created .env"
else
  echo "  ✅ .env already exists"
fi

if [ ! -f "frontend/.env.local" ]; then
  cp frontend/.env.local.example frontend/.env.local
  echo "  ✅ Created frontend/.env.local"
else
  echo "  ✅ frontend/.env.local already exists"
fi

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  Setup complete! Next steps:             ║"
echo "║                                          ║"
echo "║  1. Get FREE Gemini API key:             ║"
echo "║     https://aistudio.google.com          ║"
echo "║                                          ║"
echo "║  2. Edit .env → paste your key:          ║"
echo "║     GEMINI_API_KEY=your_key_here         ║"
echo "║                                          ║"
echo "║  3. Train ML models (run once):          ║"
echo "║     python backend/train_models.py       ║"
echo "║                                          ║"
echo "║  4. Start both servers:                  ║"
echo "║     bash start.sh                        ║"
echo "╚══════════════════════════════════════════╝"
echo ""
