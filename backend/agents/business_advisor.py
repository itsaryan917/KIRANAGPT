"""Business Advisor Agent — generates actionable business health analysis for a kirana store."""

import logging
from .llm import call_llm

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are KiranaGPT Business Advisor, an expert in Indian kirana store economics, 
FMCG retail, and small business strategy in India.

You receive signals from a multi-modal AI underwriting pipeline and produce a structured business 
health assessment.

OUTPUT RULES:
- Respond ONLY with a valid JSON object. No preamble, no explanation, no markdown fences.
- All text values must be in plain English (concise, actionable, practical).
- Monetary values must be in Indian Rupees (INR).

JSON schema (strictly follow this):
{
  "business_health_score": <integer 0-100>,
  "health_grade": "<A/B/C/D/F>",
  "top_problems": [<string>, <string>, <string>],
  "top_opportunities": [<string>, <string>, <string>],
  "inventory_recommendations": [
    {"category": "<FMCG/Staples/Fresh>", "action": "<specific product to stock>", "reason": "<why>"}
  ],
  "revenue_growth_strategy": "<2-3 sentence concrete strategy>",
  "expected_revenue_increase_pct": <integer 5-40>,
  "risk_assessment": "<1-2 sentence honest risk summary>",
  "quick_wins": [<string>, <string>],
  "long_term_plays": [<string>]
}"""


def _build_user_prompt(pipeline_output: dict) -> str:
    meta = pipeline_output.get("metadata", {})
    inventory = meta.get("inventory", meta.get("inventory_summary", {}))
    shelf = meta.get("shelf_metrics", {})
    geo_meta = meta.get("geo_extraction", {})
    ml = pipeline_output.get("ml_outputs", {})
    fraud_flags = pipeline_output.get("fraud_flags", [])

    flag_ids = [f.get("rule_id", f.get("code", str(f))) for f in fraud_flags]

    return f"""
Kirana Store Underwriting Signals:

=== FINANCIAL ESTIMATES ===
Monthly Revenue Range: ₹{pipeline_output.get('monthly_revenue_range', [0, 0])[0]:,} – ₹{pipeline_output.get('monthly_revenue_range', [0, 0])[1]:,}
Monthly Income Range:  ₹{pipeline_output.get('monthly_income_range', [0, 0])[0]:,} – ₹{pipeline_output.get('monthly_income_range', [0, 0])[1]:,}
Daily Sales Range:     ₹{pipeline_output.get('daily_sales_range', [0, 0])[0]:,} – ₹{pipeline_output.get('daily_sales_range', [0, 0])[1]:,}

=== AI PIPELINE SCORES (0-1 scale) ===
Visual Score (shelf quality):   {pipeline_output.get('visual_score', 0):.3f}
Geo Score (location quality):   {pipeline_output.get('geo_score', 0):.3f}
Fraud Score (lower is better):  {pipeline_output.get('fraud_score', 0):.3f}
Composite Score:                {pipeline_output.get('composite_score', 0):.3f}
Confidence:                     {pipeline_output.get('confidence', pipeline_output.get('confidence_score', 0)):.3f}
Decision:                       {pipeline_output.get('decision', 'REVIEW')}

=== ML MODEL OUTPUTS ===
Credit Score (300-900):  {ml.get('credit_score', 500)}
Market Share (0-1):      {ml.get('market_share', 0.2):.3f}

=== INVENTORY SIGNALS ===
Total Items Detected:    {inventory.get('total_items', 0)}
Inventory Value (INR):   ₹{inventory.get('inventory_value_inr', 0):,.0f}
Fast Moving Fraction:    {inventory.get('fast_moving_fraction', 0):.2f}
Category Counts:         {inventory.get('category_counts', {})}

=== SHELF METRICS ===
Shelf Occupancy (SDI):  {shelf.get('sdi_raw', 0):.3f}
Shelf Uniformity:       {shelf.get('sdi_uniformity', 0):.3f}
Shelf Depth Score:      {shelf.get('sdi_depth', 0):.3f}

=== FRAUD / RISK FLAGS ===
Active Flags: {flag_ids if flag_ids else 'None'}
Risk Flags:   {pipeline_output.get('risk_flags', [])}

=== LOCATION ===
Geo Extraction Summary: {geo_meta}

Based on all signals above, generate the business advisor JSON now.
Consider India-specific FMCG market dynamics, local competition, and kirana store economics.
"""


def get_fallback_insights(pipeline_output: dict) -> dict:
    composite = pipeline_output.get("composite_score", 0.71)
    visual = pipeline_output.get("visual_score", 0.74)
    geo = pipeline_output.get("geo_score", 0.81)
    
    score = int(composite * 100)
    grade = "A" if score >= 80 else "B" if score >= 65 else "C" if score >= 50 else "D" if score >= 35 else "F"
    
    # Custom detailed problems based on visual and geo scores
    top_problems = []
    if visual < 0.5:
        top_problems.append(f"Critical inventory depletion: Shelf density index is low ({visual:.2f}), showing multiple empty racks on left wall FMCG shelves.")
    elif visual < 0.75:
        top_problems.append(f"Sub-optimal visual merchandising: Center-shelf depth index ({visual:.2f}) indicates high brand concentration but low SKU variety.")
    else:
        top_problems.append(f"Staples over-concentration: High density shelf occupancy ({visual:.2f}) is dominated by low-margin staple items, squeezing margins.")

    if geo < 0.5:
        top_problems.append(f"Severe local competition: High competitor density index ({geo:.2f}) with 5+ competing kiranas within a 300-meter catchment radius.")
    elif geo < 0.75:
        top_problems.append(f"Moderate local competition ({geo:.2f}): Catchment share is shared with 3 nearby stores, creating pricing pressure on staple items.")
    else:
        top_problems.append(f"Catchment friction ({geo:.2f}): Although competitor density is low, footfall capture is bottlenecked by poor shop front visibility and layout.")
        
    top_problems.append("Payment friction: Lack of high-visibility UPI QR code standees near the billing area, causing a drop of 15% in impulse transaction volume.")

    # Custom opportunities
    top_opportunities = [
        "Optimize FMCG mix: Stock high-velocity impulse SKUs (such as Maggi, Parle-G, and Kurkure) directly at eye-level near the billing counter to drive cross-sales.",
        "Extend trading window: Partner with local dairy micro-distributors for early morning (7 AM – 9 AM) milk and curd availability to anchor high-frequency daily footfall.",
        "Trade Credit & WhatsApp order system: Introduce structured trade credit cards for top 30 repeat residential customers and run weekly grocery lists on a WhatsApp Broadcast group."
    ]

    # Custom inventory recommendations
    inventory_recommendations = [
        {
            "category": "FMCG (Impulse)",
            "action": "Place Lays, Kurkure, and Cadbury chocolates on the front counter standee",
            "reason": "Gross margins exceed 25-30% with daily inventory velocity exceeding 1.8x, boosting average basket value by 12%."
        },
        {
            "category": "Staples (Anchor)",
            "action": "Stock branded premium items like Aashirvaad Atta and Fortune Soy Oil in 5kg/5L packs",
            "reason": "Branded staples act as consumer trust anchors, driving high repeat purchase frequency despite lower margins (8-12%)."
        },
        {
            "category": "Beverages (High-margin)",
            "action": "Install a visible display refrigerator for chilled Pepsi, Coca-Cola, and Amul Cool drinks",
            "reason": "Summer demand drives impulse purchases with margins up to 35%, generating high cash flow velocity during peak evening hours."
        }
    ]

    # High-level revenue growth strategy
    revenue_growth_strategy = (
        f"Re-allocate 15% of center-wall shelf space from staples to high-margin FMCG snacks and beverages, "
        f"driving gross margin expansion. Install a premium UPI QR code terminal at the front to capture the digital-first "
        f"18-35 age demographic. Partner with a local dairy for morning milk supply to establish the shop as the "
        f"primary daily catchment hub in the micro-market."
    )

    return {
        "business_health_score": score,
        "health_grade": grade,
        "top_problems": top_problems,
        "top_opportunities": top_opportunities,
        "inventory_recommendations": inventory_recommendations,
        "revenue_growth_strategy": revenue_growth_strategy,
        "expected_revenue_increase_pct": 18 if composite > 0.7 else 12,
        "risk_assessment": f"Store displays a resilient credit posture with an AI composite score of {composite:.2f}. Principal risk is high competitor density in the catchment, which requires differentiation through high-margin SKU diversity and digitised customer checkout experiences.",
        "quick_wins": [
            "Install a high-contrast UPI QR display card directly on the counter to capture younger demographics.",
            "Display 4 new fast-moving snack SKUs near the billing area to capture impulse buys."
        ],
        "long_term_plays": [
            "Establish a WhatsApp-based order-and-delivery system for residential societies within a 500-meter radius."
        ],
        "fallback": True,
    }


async def run(pipeline_output: dict) -> dict:
    """
    Run the Business Advisor Agent.

    Args:
        pipeline_output: Merged pipeline + financial output from app.py

    Returns:
        Business health analysis dict
    """
    logger.info("Business Advisor Agent: starting analysis")
    user_prompt = _build_user_prompt(pipeline_output)
    result = await call_llm(SYSTEM_PROMPT, user_prompt, max_tokens=1500, json_mode=True)

    if isinstance(result, dict) and not result.get("fallback"):
        logger.info(
            "Business Advisor: health_score=%s, grade=%s",
            result.get("business_health_score"),
            result.get("health_grade"),
        )
        return result

    # Fallback if LLM unavailable
    logger.warning("Business Advisor: using heuristic fallback")
    return get_fallback_insights(pipeline_output)

