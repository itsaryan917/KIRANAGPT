"""Voice Agent — bilingual Hindi + English Q&A for store owners."""

import logging
from .llm import call_llm

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are KiranaGPT, a friendly AI assistant that helps kirana store owners 
understand their loan assessment results. You work for an NBFC in India.

LANGUAGE RULES:
- If the user writes in Hindi (Devanagari script or Hinglish like "mujhe batao"), respond in Hindi (Devanagari).
- If the user writes in English, respond in English.
- If mixed, match the dominant language.

TONE RULES:
- Be warm, simple, encouraging, and honest.
- Use ₹ for amounts. Say amounts in Indian style: "do lakh", "pachis hazaar".
- Keep responses under 120 words — they will be read aloud.
- Never use markdown formatting, headers, or bullet points — pure conversational text only.
- If you don't know something, say so honestly.

KNOWLEDGE:
You have access to this store's assessment data which will be provided in the user message.
Always refer to specific numbers from the store's actual results when answering."""


async def answer(question: str, store_context: dict) -> str:
    """
    Answer a store owner's question about their assessment.

    Args:
        question: User's question (Hindi or English)
        store_context: Merged pipeline + AI agent outputs

    Returns:
        Short conversational answer in the same language as the question.
    """
    logger.info("Voice Agent: answering question")

    rev_range = store_context.get("monthly_revenue_range", [0, 0])
    inc_range = store_context.get("monthly_income_range", [0, 0])
    decision = store_context.get("decision", "REVIEW")
    ml = store_context.get("ml_outputs", {})
    biz = store_context.get("business_insights", {})
    loan = store_context.get("loan_advice", {})

    context_block = f"""
Store Assessment Data:
- Decision: {decision}
- Monthly Revenue: ₹{rev_range[0]:,}–₹{rev_range[1]:,}
- Monthly Income: ₹{inc_range[0]:,}–₹{inc_range[1]:,}
- Credit Score: {ml.get('credit_score', 'N/A')}/900
- Business Health Score: {biz.get('business_health_score', 'N/A')}/100
- Recommended Loan: ₹{loan.get('recommended_loan_inr', 0):,}
- Loan Verdict: {loan.get('lender_verdict', decision)}
- EMI: ₹{loan.get('monthly_emi_inr', 0):,}/month
- Key Opportunities: {biz.get('top_opportunities', [])}
- Key Problems: {biz.get('top_problems', [])}
- Fraud Flags: {len(store_context.get('fraud_flags', []))} flags detected

Store owner's question: {question}

Answer in the same language the question was asked. Keep it under 120 words. Be conversational.
"""

    result = await call_llm(SYSTEM_PROMPT, context_block, max_tokens=250, json_mode=False)

    if isinstance(result, str) and len(result) > 10:
        logger.info("Voice Agent: answered (%d chars)", len(result))
        return result

    # Fallback
    if any(ord(c) > 0x900 for c in question):  # Devanagari
        return f"आपकी दुकान का मूल्यांकन {decision} हुआ है। आपकी मासिक आय ₹{inc_range[0]:,} से ₹{inc_range[1]:,} के बीच अनुमानित है। कोई और सवाल हो तो पूछें।"
    return f"Your store assessment result is {decision}. Estimated monthly income is ₹{inc_range[0]:,}–₹{inc_range[1]:,}. Feel free to ask any other questions."
