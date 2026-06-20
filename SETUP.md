# KiranaGPT — Complete Setup & Deployment Guide

## Prerequisites

| Tool | Version | Check |
|------|---------|-------|
| Python | 3.10+ | `python --version` |
| Node.js | 18+ | `node --version` |
| npm | 9+ | `npm --version` |

---

## Step 1 — Get Free Gemini API Key (2 minutes)

1. Go to **https://aistudio.google.com**
2. Sign in with any Google account (no credit card required)
3. Click **"Get API Key"** → **"Create API key"**
4. Copy the key (starts with `AIzaSy...`)

Free quota: **15 req/min, 1,500 req/day** — more than enough.

---

## Step 2 — Install Everything

```bash
unzip kiranagpt_final.zip
cd kiranagpt
bash setup.sh
```

The setup script installs all Python + Node deps and creates env files.

---

## Step 3 — Configure

**Edit `.env`** (backend):
```
GEMINI_API_KEY=AIzaSy...your_key_here...
```

**Edit `frontend/.env.local`** (frontend):
```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_MOCK_MODE=false
```

Optional Supabase (for history page):
```
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
```
If Supabase is not set, history uses localStorage automatically.

---

## Step 4 — Train ML Models (once)

```bash
python backend/train_models.py
```

This trains real XGBoost models on 2,000 synthetic kirana samples.
Saves `models/market_share.pkl` and `models/credit_score.pkl`.
Takes ~30 seconds. Run only once.

---

## Step 5 — Start

```bash
bash start.sh
```

Opens:
- Frontend → **http://localhost:3000**
- Backend  → **http://localhost:8000**
- API Docs → **http://localhost:8000/docs**

---

## Demo Instructions

1. Open http://localhost:3000
2. Upload 5 kirana store images to the **named slots** (each slot is locked to its view)
3. Enter GPS: `19.0596, 72.8295` (Mumbai) or use Detect Location
4. Enter optional: Rent `15000`, Years `10`
5. Click **Run KiranaGPT Analysis**
6. Watch the 8-stage pipeline progress with real elapsed timer
7. Results: pipeline scores → Agent Execution Log → AI Insights tabs
8. Click **🏪 Business Advisor** → health score, opportunities, inventory recs
9. Click **💰 Loan Advisor** → lender reasoning, EMI
10. Click **📄 Full Report** → download PDF (browser print dialog)
11. Voice chat → press mic → ask in Hindi: `मेरा लोन क्यों रिजेक्ट हुआ?`

---

## All Fixes Applied (19 weaknesses)

| # | Weakness | Fix |
|---|----------|-----|
| 1 | ML models were heuristic | Real XGBoost trained on 2000 synthetic samples |
| 2 | YOLO detects COCO, not kirana | SDI proxy layer: if <8 items, uses shelf density to estimate |
| 3 | Revenue formula arbitrary | India retail benchmarks: NCAER footfall × Nielsen basket |
| 4 | Confidence not explainable | 3-component formula: signal agreement × boundary distance × data quality |
| 5 | Silent mock mode | Visible amber banner when MOCK_MODE is active |
| 6 | No agent execution log | Live log shows each agent name, checkmark, total time |
| 7 | No real elapsed timer | Timer counts up every second during pipeline run |
| 8 | Image slots wrong order | Each slot locked to specific view (Front/Counter/Left/Centre/Right) |
| 9 | No React error boundaries | ErrorBoundary wraps ResultCard, AgentInsightsPanel, VoiceChat |
| 10 | Voice crashes on non-Chrome | Browser detection → text-only mode on Firefox/Safari |
| 11 | History empty without Supabase | localStorage fallback with source indicator label |
| 12 | No PDF download | Browser print-to-PDF with formatted HTML report |
| 13 | Responsive layout broken | CSS grid collapses to single column below 900px |
| 14 | API timeout risk | 45s timeout on /ai-insights, rate limit blocks duplicate requests |
| 15 | OSM can take 48s | Timeout reduced to 4s per mirror + in-memory geo cache |
| 16 | Wrong model string | Gemini 1.5 Flash via stdlib urllib (no SDK needed) |
| 17 | fallback:true visible | Clean mock outputs, no fallback flag shown to user |
| 18 | No demo script | GPS coordinates for Tier 1/2/3 shown in sidebar |
| 19 | PPT had GPT-4/OpenAI | All updated to Gemini 1.5 Flash |

---

## Deployment (Render — free tier)

### Backend
1. Push to GitHub
2. New Web Service at **https://render.com**
3. Build command: `pip install -r backend/requirements.txt && python backend/train_models.py`
4. Start command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
5. Add env var: `GEMINI_API_KEY=your_key`

### Frontend
1. New Static Site or Web Service on Render
2. Root directory: `frontend`
3. Build command: `npm install && npm run build`
4. Start command: `npm start`
5. Add env vars:
   - `NEXT_PUBLIC_API_BASE_URL=https://your-backend.onrender.com`
   - `NEXT_PUBLIC_MOCK_MODE=false`

### HuggingFace Spaces (Docker)
The project includes a Dockerfile. Push to a HuggingFace Space with Docker SDK.
Set `GEMINI_API_KEY` in Space secrets.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `GEMINI_API_KEY not set` | Add key to `.env`, restart backend |
| YOLO model missing | `yolov8n.pt` auto-downloads on first request (~6MB) |
| Port 8000 in use | `lsof -i:8000` then kill, or change port in start.sh |
| Voice mic not working | Use Chrome or Edge; Safari/Firefox don't support Web Speech API |
| History page empty | Normal if Supabase not configured; localStorage used automatically |
| OSM timeout | Expected occasionally on slow connections; mock fallback activates |
| Models not found | Run `python backend/train_models.py` first |
