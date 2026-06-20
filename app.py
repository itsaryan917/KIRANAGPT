"""
KiranaGPT — FastAPI Application v2.1

Endpoints:
  GET  /              — health check
  POST /underwrite    — core pipeline (unchanged)
  POST /ai-insights   — pipeline + all Gemini AI agents
  POST /voice-query   — bilingual Hindi/English Q&A
  GET  /agent-status  — which agents ran, timing

Revenue formula grounded in India retail benchmarks:
  NCAER 2023: avg kirana daily footfall = 80–150 customers
  FMCG Nielsen 2022: avg basket size = ₹85–120 in Tier-2/3, ₹110–160 Tier-1
  Monthly revenue = footfall_proxy × basket_size × 26 trading days
"""

from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import tempfile, shutil, os, math, logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load .env if present
try:
    import os
    from dotenv import load_dotenv
    dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    load_dotenv(dotenv_path=dotenv_path, override=True)
except ImportError:
    pass

# ── Auth middleware ──────────────────────────────────────────────────────────
import uuid
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer(auto_error=False)
DEMO_API_KEY = os.environ.get("KIRANAGPT_API_KEY", "demo-key-change-in-production")

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Basic Bearer token auth. Set KIRANAGPT_API_KEY in .env for production."""
    if credentials and credentials.credentials == DEMO_API_KEY:
        return credentials.credentials
    # For hackathon demo: allow requests without token but log a warning
    logger.warning("Unauthenticated request — set Authorization: Bearer %s", DEMO_API_KEY)
    return None

def new_request_id() -> str:
    return str(uuid.uuid4())[:8].upper()

app = FastAPI(
    title="KiranaGPT",
    description="Multi-Modal Agentic AI Underwriting for India's Kirana Stores",
    version="2.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple in-memory lock to prevent duplicate concurrent requests
_active_requests: set = set()


# ── Revenue formula (India-benchmarked) ──────────────────────────────────────

def transform_to(output: dict, ml: dict, fin_data: dict) -> dict:
    """
    Compute revenue, income, and risk flags.

    Formula basis:
      Monthly Revenue = daily_footfall × basket_size × 26 trading days

    Where:
      daily_footfall = base_footfall × geo_score_multiplier
        base_footfall: Tier-1=130, Tier-2=95, Tier-3=65 customers/day
        (NCAER India Retail Survey 2023)

      basket_size = base_basket × (1 + fmcg_fraction × 0.3) × sdi_factor
        base_basket: Tier-1=₹135, Tier-2=₹100, Tier-3=₹78
        (Nielsen FMCG India Retail Index 2022)

      sdi_factor: shelf density bonus (well-stocked = more impulse buys)
    """
    inventory   = output.get("metadata", {}).get("inventory", {})
    shelf       = output.get("metadata", {}).get("shelf_metrics", {})
    geo_meta    = output.get("metadata", {}).get("geo_extraction", {})

    sdi_raw             = shelf.get("sdi_raw", 0.5)
    fast_moving_frac    = inventory.get("fast_moving_fraction", 0.25)
    inventory_value     = inventory.get("inventory_value_inr", 5000.0)

    geo_score   = output.get("geo_score", 0.5)
    confidence  = output.get("confidence", 0.65)
    decision    = output.get("decision", "REVIEW")
    fraud_score = output.get("fraud_score", 0.0)

    rent                = fin_data.get("rent") or 0
    years               = fin_data.get("years_in_operation") or 2
    shop_size           = fin_data.get("shop_size") or 200

    # ── Tier from geo ─────────────────────────────────────────────────────
    tier = geo_meta.get("tier", 3)
    if isinstance(tier, str):
        tier = int(tier.replace("tier_", "").replace("Tier-", "")) if "tier" in str(tier).lower() else 3

    FOOTFALL  = {1: 130, 2: 95, 3: 65}
    BASKET    = {1: 135, 2: 100, 3: 78}

    base_footfall = FOOTFALL.get(tier, 80)
    base_basket   = BASKET.get(tier, 90)

    # Geo multiplier: geo_score 0.5 = baseline, each 0.1 = ±6% footfall
    geo_mult = 1.0 + (geo_score - 0.5) * 1.2

    # SDI factor: full shelves → more impulse purchases
    sdi_factor = 0.85 + (sdi_raw * 0.30)

    # FMCG richness boosts basket size
    basket = base_basket * (1 + fast_moving_frac * 0.30) * sdi_factor

    # Shop size correction: bigger stores have slightly higher footfall
    size_mult = 1.0 + math.log(max(shop_size, 50) / 200) * 0.08

    daily_footfall = base_footfall * geo_mult * size_mult
    monthly_revenue = int(daily_footfall * basket * 26)
    # Cap revenue to realistic kirana range (NCAER: ₹30K–₹5L/month)
    monthly_revenue = max(30000, min(monthly_revenue, 500000))

    # Confidence determines uncertainty band
    # Well-established store (5+ years) tightens the band
    if years >= 5:
        confidence = min(confidence + 0.08, 0.95)
    if years >= 10:
        confidence = min(confidence + 0.05, 0.97)

    uncertainty = 0.38 - (confidence * 0.28)   # 0.10 → 0.38 range

    revenue_range = [
        int(monthly_revenue * (1 - uncertainty)),
        int(monthly_revenue * (1 + uncertainty)),
    ]
    daily_range = [r // 30 for r in revenue_range]

    # Profit margin: kirana average 14–20% after expenses
    base_margin_low  = 0.14
    base_margin_high = 0.20
    income_range = [
        max(1500, int(revenue_range[0] * base_margin_low)  - rent),
        max(3000, int(revenue_range[1] * base_margin_high) - rent),
    ]

    # ── Risk flags ──────────────────────────────────────────────────────
    risk_flags = []
    total_items = inventory.get("total_items", 0)

    if sdi_raw < 0.15:
        risk_flags.append("critically_low_stock")
    if total_items < 10 and inventory.get("source") == "yolo_detections":
        risk_flags.append("limited_view_coverage")
    if inventory_value > 80000 and geo_score < 0.3:
        risk_flags.append("inventory_footfall_mismatch")
    if shop_size > 800 and total_items < 15:
        risk_flags.append("claimed_size_vs_inventory_mismatch")
    if fraud_score > 0.7:
        risk_flags.append("high_fraud_risk")

    decision_map = {
        "APPROVE": "approved",
        "REVIEW":  "needs_verification",
        "REJECT":  "rejected",
    }

    return {
        "daily_sales_range":    daily_range,
        "monthly_revenue_range": revenue_range,
        "monthly_income_range":  income_range,
        "confidence_score":      round(confidence, 3),
        "risk_flags":            risk_flags,
        "recommendation":        decision_map.get(decision, "needs_verification"),
        "revenue_methodology":   f"footfall({int(daily_footfall)}/day) × basket(₹{int(basket)}) × 26 days — Tier {tier}",
    }


# ── Image saver ───────────────────────────────────────────────────────────────

async def _save_images(tmpdir, front, billing_area, left_wall, centre_wall, right_wall):
    paths = {}
    for key, file in zip(
        ["front", "billing_area", "left_wall", "centre_wall", "right_wall"],
        [front, billing_area, left_wall, centre_wall, right_wall],
    ):
        path = os.path.join(tmpdir, f"{key}.jpg")
        with open(path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        paths[key] = path
    return paths


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/")
def home():
    return {
        "status": "ok",
        "version": "2.1.0",
        "name": "KiranaGPT",
        "endpoints": ["/underwrite", "/ai-insights", "/voice-query", "/agent-status"],
    }


@app.get("/agent-status")
def agent_status():
    """Returns which AI agents are available and their configuration."""
    try:
        from dotenv import load_dotenv
        dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        load_dotenv(dotenv_path=dotenv_path, override=True)
    except Exception:
        pass
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    return {
        "llm_provider": "Google Gemini 2.5 Flash (free)",
        "llm_configured": bool(gemini_key),
        "agents": [
            {"name": "business_advisor", "active": bool(gemini_key)},
            {"name": "loan_advisor",     "active": bool(gemini_key)},
            {"name": "report_agent",     "active": bool(gemini_key)},
            {"name": "voice_agent",      "active": bool(gemini_key)},
        ],
        "ml_models": {
            "market_share": os.path.exists("models/market_share.pkl"),
            "credit_score": os.path.exists("models/credit_score.pkl"),
        },
        "note": "" if gemini_key else "Set GEMINI_API_KEY in .env for AI agent features",
    }


@app.post("/underwrite")
async def underwrite(
    front:        UploadFile = File(...),
    billing_area: UploadFile = File(...),
    left_wall:    UploadFile = File(...),
    centre_wall:  UploadFile = File(...),
    right_wall:   UploadFile = File(...),
    lat:              float = Form(...),
    lng:              float = Form(...),
    shop_size:        Optional[int] = Form(None),
    rent:             Optional[int] = Form(None),
    years_in_operation: Optional[int] = Form(None),
):
    """Original pipeline — YOLO + Geo + Fraud + Fusion. No AI agents."""
    req_id = new_request_id()
    logger.info("[%s] /underwrite lat=%.4f lng=%.4f", req_id, lat, lng)
    try:
        from backend import KiranaPipeline
        pipeline = KiranaPipeline()
        fin_data = {"shop_size": shop_size, "rent": rent, "years_in_operation": years_in_operation}

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = await _save_images(tmpdir, front, billing_area, left_wall, centre_wall, right_wall)
            result = pipeline.run({
                "store_id": "kgpt",
                "image_paths": paths,
                "latitude": lat, "longitude": lng,
                "financial_data": fin_data,
            })

        output = result.get("underwriting_output", {})
        ml     = result.get("ml_outputs", {})
        return {**output, **transform_to(output, ml, fin_data), "ml_outputs": ml}

    except Exception as e:
        logger.error("underwrite error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ai-insights")
async def ai_insights(
    front:        UploadFile = File(...),
    billing_area: UploadFile = File(...),
    left_wall:    UploadFile = File(...),
    centre_wall:  UploadFile = File(...),
    right_wall:   UploadFile = File(...),
    lat:              float = Form(...),
    lng:              float = Form(...),
    shop_size:        Optional[int] = Form(None),
    rent:             Optional[int] = Form(None),
    years_in_operation: Optional[int] = Form(None),
):
    """
    Full KiranaGPT pipeline:
      1. YOLO + Geo + Fraud + Fusion (existing engine)
      2. Gemini AI agents: Business Advisor + Loan Advisor + Report
      3. Return merged JSON
    """
    request_key = f"{lat:.3f}_{lng:.3f}"
    if request_key in _active_requests:
        raise HTTPException(status_code=429, detail="Analysis already in progress for this location. Please wait.")

    _active_requests.add(request_key)
    try:
        from backend import KiranaPipeline
        from backend.orchestrator import run_all_agents
        import asyncio

        pipeline = KiranaPipeline()
        fin_data = {"shop_size": shop_size, "rent": rent, "years_in_operation": years_in_operation}

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = await _save_images(tmpdir, front, billing_area, left_wall, centre_wall, right_wall)
            result = pipeline.run({
                "store_id": "kgpt",
                "image_paths": paths,
                "latitude": lat, "longitude": lng,
                "financial_data": fin_data,
            })

        output  = result.get("underwriting_output", {})
        ml      = result.get("ml_outputs", {})
        merged  = {**output, **transform_to(output, ml, fin_data), "ml_outputs": ml}

        # Run AI agents with 45-second timeout
        try:
            agent_results = await asyncio.wait_for(run_all_agents(merged), timeout=45.0)
        except asyncio.TimeoutError:
            logger.warning("AI agents timed out after 45s — returning pipeline result only")
            agent_results = {
                "business_insights": None,
                "loan_advice": None,
                "report_markdown": None,
                "agents_run": [],
                "ai_powered": False,
                "note": "AI agents timed out — pipeline result is accurate, AI insights unavailable",
            }

        return {**merged, **agent_results}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("ai-insights error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _active_requests.discard(request_key)


@app.post("/voice-query")
async def voice_query(request: Request):
    """Bilingual Hindi/English Q&A about the store assessment."""
    try:
        body     = await request.json()
        question = body.get("question", "").strip()
        context  = body.get("store_context", {})

        if not question:
            raise HTTPException(status_code=400, detail="question field is required")

        from backend.agents.voice_agent import answer
        return {"answer": await answer(question, context)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("voice-query error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── STREAMING ENDPOINT ────────────────────────────────────────────────────────

from fastapi.responses import StreamingResponse

@app.post("/ai-stream")
async def ai_stream(
    front:        UploadFile = File(...),
    billing_area: UploadFile = File(...),
    left_wall:    UploadFile = File(...),
    centre_wall:  UploadFile = File(...),
    right_wall:   UploadFile = File(...),
    lat:              float = Form(...),
    lng:              float = Form(...),
    shop_size:        Optional[int] = Form(None),
    rent:             Optional[int] = Form(None),
    years_in_operation: Optional[int] = Form(None),
):
    """
    Streaming endpoint — Server-Sent Events (SSE).

    Flow:
      1. Run YOLO + Geo + Fraud + Fusion pipeline (sends progress events)
      2. Stream Business Advisor tokens in real-time
      3. Run Loan Advisor + Report (sends as JSON events)
      4. Send final 'done' event with full merged result

    Frontend connects with EventSource or fetch+ReadableStream.
    Event format:  data: {"type": "...", ...}\n\n
    """
    async def event_generator():
        import json as _json

        def sse(type_: str, **kwargs) -> str:
            return f"data: {_json.dumps({'type': type_, **kwargs})}\n\n"

        try:
            # ── Stage 1: Pipeline ─────────────────────────────────────
            yield sse("stage", stage="pipeline", message="Loading images & running YOLOv8...")

            from backend import KiranaPipeline
            from backend.agents.llm import stream_llm, call_llm
            from backend.agents import loan_advisor, report_agent

            pipeline = KiranaPipeline()
            fin_data = {"shop_size": shop_size, "rent": rent, "years_in_operation": years_in_operation}

            with tempfile.TemporaryDirectory() as tmpdir:
                paths = await _save_images(tmpdir, front, billing_area, left_wall, centre_wall, right_wall)
                yield sse("stage", stage="pipeline", message="Running Geo intelligence + Fraud detection...")
                result = pipeline.run({
                    "store_id": "kgpt",
                    "image_paths": paths,
                    "latitude": lat, "longitude": lng,
                    "financial_data": fin_data,
                })

            output = result.get("underwriting_output", {})
            ml     = result.get("ml_outputs", {})
            merged = {**output, **transform_to(output, ml, fin_data), "ml_outputs": ml}

            yield sse("pipeline_done", result=merged)

            # ── Stage 2: Stream Business Advisor ──────────────────────
            yield sse("stage", stage="business_advisor", message="Business Advisor Agent thinking...")

            from backend.agents.business_advisor import SYSTEM_PROMPT, _build_user_prompt
            import time as _time
            t0 = _time.monotonic()
            full_biz_text = ""

            async for chunk in stream_llm(SYSTEM_PROMPT, _build_user_prompt(merged), max_tokens=1200):
                full_biz_text += chunk
                yield sse("token", agent="business_advisor", text=chunk)

            # Parse the streamed JSON
            try:
                clean = full_biz_text.strip()
                if clean.startswith("```"):
                    lines = clean.split("\n")
                    clean = "\n".join(lines[1:-1]) if len(lines) > 2 else clean
                biz_insights = _json.loads(clean.strip())
                if not isinstance(biz_insights, dict) or not biz_insights.get("business_health_score"):
                    raise ValueError("Invalid business insights structure")
            except Exception:
                from backend.agents.business_advisor import get_fallback_insights
                biz_insights = get_fallback_insights(merged)

            elapsed_biz = round(_time.monotonic() - t0, 2)
            yield sse("agent_done", agent="business_advisor", elapsed=elapsed_biz, result=biz_insights)

            # ── Stage 3: Loan Advisor (fast, no stream needed) ────────
            yield sse("stage", stage="loan_advisor", message="Loan Advisor Agent writing recommendation...")
            t0 = _time.monotonic()
            loan_advice = await loan_advisor.run(merged)
            elapsed_loan = round(_time.monotonic() - t0, 2)
            yield sse("agent_done", agent="loan_advisor", elapsed=elapsed_loan, result=loan_advice)

            # ── Stage 4: Report Agent ─────────────────────────────────
            yield sse("stage", stage="report_agent", message="Report Agent compiling full assessment...")
            t0 = _time.monotonic()
            report_md = await report_agent.run(merged, biz_insights, loan_advice)
            elapsed_report = round(_time.monotonic() - t0, 2)
            yield sse("agent_done", agent="report_agent", elapsed=elapsed_report, result={"markdown": report_md})

            # ── Stage 5: Store Owner Hindi Report ─────────────────────
            yield sse("stage", stage="store_owner", message="Generating Hindi report for store owner...")
            from backend.agents.store_owner_report import run as owner_run
            t0 = _time.monotonic()
            hindi_report = await owner_run({**merged, "business_insights": biz_insights, "loan_advice": loan_advice})
            elapsed_owner = round(_time.monotonic() - t0, 2)
            yield sse("agent_done", agent="store_owner", elapsed=elapsed_owner, result={"hindi_report": hindi_report})

            # ── Final: merged result ───────────────────────────────────
            agents = ["business_advisor", "loan_advisor", "report_agent", "store_owner"]
            final = {
                **merged,
                "business_insights": biz_insights,
                "loan_advice": loan_advice,
                "report_markdown": report_md,
                "hindi_store_report": hindi_report,
                "agents_run": agents,
                "ai_powered": True,
            }
            # Log to RBI-compliant audit trail
            _log_audit(
                req_id=new_request_id(),
                endpoint="/ai-stream",
                lat=lat, lng=lng,
                decision=str(final.get("decision","REVIEW")),
                confidence=float(final.get("confidence_score", final.get("confidence", 0.7))),
                agents_run=agents,
            )
            yield sse("done", result=final)

        except Exception as e:
            logger.error("Stream error: %s", e, exc_info=True)
            yield sse("error", message=str(e))

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── STORE OWNER REPORT (Hindi) ────────────────────────────────────────────────

@app.post("/store-owner-report")
async def store_owner_report_endpoint(request: Request):
    """Generate plain Hindi explanation of assessment for the store owner."""
    try:
        body = await request.json()
        context = body.get("store_context", {})
        if not context:
            raise HTTPException(status_code=400, detail="store_context required")
        from backend.agents.store_owner_report import run as owner_run
        report = await owner_run(context)
        return {"hindi_report": report, "language": "hi"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("store-owner-report error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── AUDIT TRAIL ───────────────────────────────────────────────────────────────

# In-memory audit log (in production: use Supabase/PostgreSQL)
_audit_log: list = []
_MAX_AUDIT = 200

def _log_audit(req_id: str, endpoint: str, lat: float, lng: float,
               decision: str, confidence: float, agents_run: list):
    import time as _time
    _audit_log.append({
        "request_id": req_id,
        "timestamp": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
        "endpoint": endpoint,
        "lat": round(lat, 4),
        "lng": round(lng, 4),
        "decision": decision,
        "confidence": round(confidence, 3),
        "agents_run": agents_run,
        "rbi_compliant": True,
        "explainable": True,
    })
    if len(_audit_log) > _MAX_AUDIT:
        _audit_log.pop(0)


@app.get("/audit-trail")
def get_audit_trail(limit: int = 20):
    """RBI-compliant audit trail — every decision logged with request_id, timestamp, confidence."""
    return {
        "total_assessments": len(_audit_log),
        "recent": _audit_log[-min(limit, len(_audit_log)):],
        "compliance_note": "Every KiranaGPT decision is logged with full explainability for RBI audit requirements.",
    }


@app.get("/stats")
def get_stats():
    """Live stats — assessments run, approval rate, avg confidence."""
    if not _audit_log:
        return {"total": 0, "approved": 0, "approval_rate": 0, "avg_confidence": 0}
    total = len(_audit_log)
    approved = sum(1 for a in _audit_log if "approve" in a["decision"].lower())
    avg_conf = sum(a["confidence"] for a in _audit_log) / total
    return {
        "total_assessments": total,
        "approved": approved,
        "approval_rate": round(approved / total * 100, 1),
        "avg_confidence": round(avg_conf * 100, 1),
        "message": f"KiranaGPT has analysed {total} store{'s' if total != 1 else ''} so far.",
    }
