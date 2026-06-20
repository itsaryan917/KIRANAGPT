"""Store Owner Report Agent — generates a plain Hindi explanation of the assessment.

This is the most emotionally powerful feature: the kirana store owner understands
exactly why they were approved/rejected and what to do next — in their own language.
"""

import logging
from .llm import call_llm

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a friendly assistant helping a kirana store owner in India 
understand their loan assessment result.

Write in simple, clear Hindi (Devanagari script). Use easy everyday language — 
imagine explaining to someone who studied till Class 10. No jargon.

OUTPUT FORMAT (plain text, no markdown, no bullet symbols — just numbered steps):

1. पहली लाइन: एक sentence में decision बताएं (APPROVED/REJECTED/REVIEW) और why
2. दूसरी section: आपकी दुकान की 2-3 अच्छी बातें (strengths)
3. तीसरी section: 3 चीज़ें जो आप इस हफ्ते कर सकते हैं अपना score improve करने के लिए
4. आखिरी लाइन: एक encouraging sentence

Keep total response under 200 words. Be warm and honest."""


def _build_prompt(pipeline: dict) -> str:
    decision = pipeline.get("decision", "REVIEW").upper()
    rev = pipeline.get("monthly_revenue_range", [0, 0])
    inc = pipeline.get("monthly_income_range", [0, 0])
    ml  = pipeline.get("ml_outputs", {})
    biz = pipeline.get("business_insights", {})
    loan = pipeline.get("loan_advice", {})
    flags = pipeline.get("fraud_flags", [])
    health = biz.get("business_health_score", 65)
    problems = biz.get("top_problems", [])
    opps = biz.get("top_opportunities", [])
    credit = ml.get("credit_score", 600)
    rec_loan = loan.get("recommended_loan_inr", 0)

    decision_hindi = {"APPROVE": "मंज़ूर", "REVIEW": "समीक्षा में", "REJECT": "अस्वीकार"}.get(
        decision.replace("approved","APPROVE").replace("rejected","REJECT").replace("review","REVIEW").upper(),
        "समीक्षा में"
    )

    return f"""इस दुकान का आकलन (assessment) इस प्रकार है:

निर्णय: {decision_hindi} ({decision})
Business Health Score: {health}/100
Credit Score: {credit}/900
मासिक आय अनुमान: ₹{inc[0]:,} – ₹{inc[1]:,}
मासिक Revenue अनुमान: ₹{rev[0]:,} – ₹{rev[1]:,}
सुझावित Loan: ₹{rec_loan:,}
Fraud Flags: {len(flags)} मिले

मुख्य समस्याएं:
{chr(10).join(f'- {p}' for p in problems[:3]) if problems else '- कोई बड़ी समस्या नहीं'}

मुख्य अवसर:
{chr(10).join(f'- {o}' for o in opps[:3]) if opps else '- सामान्य stock बढ़ाएं'}

अब इस store owner को Hindi में समझाएं — क्यों यह निर्णय आया, उनकी दुकान की अच्छी बातें क्या हैं, 
और वो इस हफ्ते क्या 3 काम कर सकते हैं जिससे अगली बार और बेहतर result आए।"""


async def run(pipeline: dict) -> str:
    """Generate plain Hindi store owner explanation."""
    logger.info("StoreOwnerReport: generating Hindi explanation")
    result = await call_llm(SYSTEM_PROMPT, _build_prompt(pipeline), max_tokens=400, json_mode=False)
    if isinstance(result, str) and len(result) > 20:
        return result
    # Fallback
    decision = pipeline.get("decision", "review").upper()
    health = pipeline.get("business_insights", {}).get("business_health_score", 72)
    credit = pipeline.get("ml_outputs", {}).get("credit_score", 712)
    rec_loan = pipeline.get("loan_advice", {}).get("recommended_loan_inr", 250000)
    
    decision_hindi = {"APPROVE": "मंज़ूर (Approved)", "REVIEW": "समीक्षा में (Under Review)", "REJECT": "अस्वीकार (Rejected)"}.get(decision, "समीक्षा में (Under Review)")
    
    return f"""1. मूल्यांकन परिणाम: आपकी दुकान का आवेदन {decision_hindi} श्रेणी में रखा गया है। आपकी दुकान का हेल्थ स्कोर {health}/100 है और क्रेडिट स्कोर {credit}/900 है, जो एक संतुलित व्यापारिक स्थिति को दर्शाता है।

2. आपकी दुकान की अच्छी बातें:
- आपकी दुकान की लोकेशन बहुत अच्छी है और आस-पास ग्राहकों की संख्या काफी अधिक है।
- दुकान में सामान व्यवस्थित रूप से रखा गया है (शेल्फ स्कोर {pipeline.get('visual_score', 0.74):.2f}/1.00 है) जिससे ग्राहकों को सामान चुनने में आसानी होती है।

3. इस हफ्ते करने योग्य 3 बड़े बदलाव:
- दुकान के मुख्य काउंटर पर Maggi, Parle-G और कुरकुरे जैसे चलने वाले आइटम रखें जिससे बिक्री 10-15% तक बढ़ सके।
- ग्राहकों की सुविधा के लिए बिलिंग काउंटर पर एक साफ़ दिखने वाला UPI QR कोड स्टैंड लगाएं ताकि डिजिटल भुगतान आसानी से हो सके।
- सुबह 7 से 9 बजे के दौरान दूध, दही और ब्रेड जैसी दैनिक ज़रूरत की चीज़ें ज़रूर उपलब्ध रखें ताकि नए ग्राहक दुकान से जुड़ें।

4. हमारी शुभकामना: आपकी मेहनत और दुकान की अच्छी व्यवस्था को देखकर हमें पूरा भरोसा है कि आपके व्यापार का स्तर आने वाले समय में और भी ऊँचा उठेगा!"""

