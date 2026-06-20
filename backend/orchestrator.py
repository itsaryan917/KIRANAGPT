"""
KiranaGPT Orchestrator

Runs all AI agents in parallel (business_advisor + loan_advisor), 
then sequentially runs report_agent using their outputs.

Usage:
    from backend.orchestrator import run_all_agents
    result = await run_all_agents(pipeline_output)
"""

import asyncio
import logging
import time
from typing import Any, Dict

from backend.agents import business_advisor, loan_advisor, report_agent

logger = logging.getLogger(__name__)


async def run_all_agents(pipeline_output: Dict[str, Any]) -> Dict[str, Any]:
    """
    Orchestrate all AI agents for a single store assessment.

    Execution plan:
    1. Run business_advisor + loan_advisor IN PARALLEL (saves ~2-3s)
    2. Run report_agent SEQUENTIALLY (needs outputs from step 1)

    Args:
        pipeline_output: The merged output from app.py (pipeline + financial estimates)

    Returns:
        Dict with keys: business_insights, loan_advice, report_markdown, 
                        agents_run, total_elapsed_s
    """
    start = time.monotonic()
    store_id = pipeline_output.get("store_id", "unknown")
    logger.info("Orchestrator: starting agents for store %s", store_id)

    # ── Step 1: Parallel agents ──────────────────────────────────────
    logger.info("Orchestrator: running business_advisor and loan_advisor in parallel")
    biz_task = asyncio.create_task(
        business_advisor.run(pipeline_output),
        name="business_advisor",
    )
    loan_task = asyncio.create_task(
        loan_advisor.run(pipeline_output),
        name="loan_advisor",
    )

    results = await asyncio.gather(biz_task, loan_task, return_exceptions=True)

    business_insights = results[0] if not isinstance(results[0], Exception) else {
        "error": str(results[0]), "fallback": True,
        "business_health_score": 50, "health_grade": "C",
        "top_problems": ["Analysis unavailable"], "top_opportunities": ["Analysis unavailable"],
        "revenue_growth_strategy": "N/A", "expected_revenue_increase_pct": 0,
    }
    loan_advice = results[1] if not isinstance(results[1], Exception) else {
        "error": str(results[1]), "fallback": True,
        "recommended_loan_inr": pipeline_output.get("loan_sizing", {}).get("recommended", 0),
        "lender_verdict": "REFER_TO_BRANCH",
    }

    logger.info(
        "Orchestrator: parallel agents done — health=%s, verdict=%s",
        business_insights.get("business_health_score"),
        loan_advice.get("lender_verdict"),
    )

    # ── Step 2: Report agent (uses parallel outputs) ─────────────────
    logger.info("Orchestrator: running report_agent")
    try:
        report_md = await report_agent.run(pipeline_output, business_insights, loan_advice)
    except Exception as exc:
        logger.error("Orchestrator: report_agent failed: %s", exc)
        report_md = "Report generation failed. Please retry."

    elapsed = time.monotonic() - start
    logger.info("Orchestrator: all agents complete in %.2fs", elapsed)

    return {
        "business_insights": business_insights,
        "loan_advice": loan_advice,
        "report_markdown": report_md,
        "agents_run": ["business_advisor", "loan_advisor", "report_agent"],
        "ai_powered": True,
        "agent_elapsed_s": round(elapsed, 2),
    }
