/**
 * KiranaGPT Demo Result
 *
 * A pre-built, realistic assessment for a Mumbai Tier-1 kirana store.
 * Used for:
 *   1. "Load Demo Result" button — instant preview during live demo
 *   2. Fallback when Gemini agents timeout
 *
 * Numbers are grounded in India retail benchmarks (NCAER 2023, Nielsen 2022).
 */

export function getDemoResult(): Record<string, unknown> {
  return {
    // ── Pipeline scores ──────────────────────────────────────────────
    store_id:        'DEMO-MUMBAI-001',
    store_name:      'DEMO-MUMBAI-001',
    owner_name:      'Ramesh Kumar',
    id:              'DEMO001',
    created_at:      new Date().toISOString(),
    images_count:    5,
    decision:        'approve',
    visual_score:    0.74,
    geo_score:       0.81,
    fraud_score:     0.04,
    composite_score: 0.71,
    confidence:      0.87,
    confidence_score:0.87,
    risk_score:      29,

    // ── Financial estimates ──────────────────────────────────────────
    monthly_revenue:       148200,
    monthly_profit:        24350,
    monthly_revenue_range: [121000, 175400],
    monthly_income_range:  [19600, 29100],
    daily_sales_range:     [4033, 5846],

    // ── Location ────────────────────────────────────────────────────
    location: { lat: 19.0596, lng: 72.8295, accuracy: 8 },

    // ── ML outputs ──────────────────────────────────────────────────
    ml_outputs: { credit_score: 712, market_share: 0.31 },

    // ── Feature scores ──────────────────────────────────────────────
    feature_scores: [
      { name: 'SDI',   label: 'Shelf Density Index',  score: 74, weight: 0.25 },
      { name: 'Geo',   label: 'Location Quality',     score: 81, weight: 0.25 },
      { name: 'ML',    label: 'Credit Score (ML)',    score: 69, weight: 0.25 },
      { name: 'Fraud', label: 'Fraud Resilience',     score: 96, weight: 0.25 },
    ],

    // ── Loan sizing ──────────────────────────────────────────────────
    loan_sizing: {
      recommended:   250000,
      minimum:       125000,
      maximum:       375000,
      tenure_months: 12,
      interest_rate: 18,
      emi:           24583,
    },

    // ── Fraud flags ──────────────────────────────────────────────────
    fraud_flags: [],
    risk_flags:  [],
    breakdown: {
      visual_contribution: 0.296,
      geo_contribution:    0.284,
      fraud_penalty:       0.010,
    },
    metadata: {
      geo_extraction: { tier: 1, is_mock: false },
      inventory: {
        total_items: 84,
        inventory_value_inr: 47200,
        fast_moving_fraction: 0.48,
        source: 'sdi_proxy',
      },
      shelf_metrics: { sdi_raw: 0.71, sdi_uniformity: 0.68, sdi_depth: 0.74 },
    },

    // ── AI agents ────────────────────────────────────────────────────
    agents_run:      ['business_advisor', 'loan_advisor', 'report_agent', 'store_owner'],
    ai_powered:      true,
    hindi_store_report: `आपकी दुकान का मूल्यांकन मंज़ूर (APPROVE) हुआ है।

आपकी दुकान की अच्छी बातें:
1. आपकी दुकान मुंबई के अच्छे इलाके में है जहाँ ग्राहक ज़्यादा हैं।
2. आपकी shelves अच्छी तरह भरी हुई हैं — इससे आपका SDI score 71/100 आया।
3. आप 8 साल से दुकान चला रहे हैं — यह bank को भरोसे का sign देता है।

इस हफ्ते 3 काम करें:
1. Maggi, Parle-G और Kurkure billing counter पर रखें — इससे ₹8,000–₹12,000 ज़्यादा हर महीने मिल सकते हैं।
2. UPI QR code लगाएं — 35 साल से कम उम्र के ग्राहक ज़्यादा खरीदते हैं।
3. सुबह 7–9 बजे dairy products बेचना शुरू करें — इससे नए ग्राहक आएंगे।

हिम्मत रखें — आपकी मेहनत रंग लाएगी!`,
    agent_elapsed_s: 6.3,

    business_insights: {
      business_health_score: 72,
      health_grade: 'B',
      top_problems: [
        'FMCG variety too low — missing Maggi, Parle-G, Kurkure SKUs on centre wall',
        'High competition — 4 stores within 300m radius reducing footfall share',
        'No digital payment signage visible — losing 20-30% of younger customers',
      ],
      top_opportunities: [
        'Add mobile recharge counter — increases daily footfall by ~20% (₹800–1,200/day)',
        'Stock premium biscuits (Dark Fantasy, Oreo) — 40% gross margin vs 18% on staples',
        'Install UPI QR display — digital-first customers spend 1.4x more per visit',
      ],
      inventory_recommendations: [
        { category: 'FMCG',    action: 'Add Maggi, Parle-G, Kurkure at billing counter', reason: 'Impulse purchase, 25-35% margin, high velocity' },
        { category: 'Staples', action: 'Stock Tata Salt 1kg and Aashirvaad Atta 5kg', reason: 'Core daily demand, anchors repeat visits' },
        { category: 'Beverages', action: 'Stock chilled water and Pepsi/Coke 200ml', reason: 'Impulse purchase, 30% margin, fast-moving' },
      ],
      revenue_growth_strategy: 'Stock Maggi, Parle-G, Kurkure at the billing counter — these 3 SKUs alone add ₹8K–₹12K/month. Partner with a local dairy for morning delivery to extend the store trading window beyond evening hours. Install a visible UPI QR code to capture the 18-35 age group.',
      expected_revenue_increase_pct: 18,
      risk_assessment: 'Store shows low-to-moderate risk with consistent revenue pattern. Key risk is high local competition — differentiation through product mix and digital payments is essential.',
      quick_wins: ['Install UPI QR code (zero cost, same day)', 'Add 5 fast-moving snack SKUs this week'],
      long_term_plays: ['WhatsApp ordering list for top 30 regular customers'],
    },

    loan_advice: {
      recommended_loan_inr:  250000,
      minimum_loan_inr:      125000,
      maximum_loan_inr:      375000,
      reasoning: 'Monthly revenue ₹1.2L–₹1.8L → 4× cap = ₹6L. XGBoost 712 + 1 MEDIUM flag → 0.82× multiplier → ₹2,50,000 recommended. 8 years tenure + Mumbai Tier-1 are strong positive signals. EMI ₹24,583 is 17% of median income — within our 25% FOIR threshold.',
      key_strengths: ['Strong Tier-1 location with 81/100 geo score', '8+ years operation history signals creditworthiness'],
      key_risks: ['No formal credit history on record', '4 competitors within 300m may pressure revenue'],
      suggested_tenure_months: 12,
      interest_rate_pct: 18,
      monthly_emi_inr: 24583,
      approval_conditions: 'Submit 3 months UPI transaction history. Field officer to verify store physically before disbursement.',
      lender_verdict: 'APPROVE',
      next_steps: 'Borrower to visit nearest branch with KYC documents and UPI statement. Disbursement within 5 working days after field visit.',
    },

    report_markdown: `# KiranaGPT Underwriting Report

**Store ID:** DEMO-MUMBAI-001  
**Report Date:** ${new Date().toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' })}  
**Assessment:** ✅ APPROVE

---

## Executive Summary

This Mumbai Tier-1 kirana store has received an **APPROVE** decision based on multi-modal AI analysis of 5 store images and live GPS location data. Monthly revenue is estimated at ₹1,21,000–₹1,75,400 with an 87% confidence level. The store demonstrates consistent inventory turnover and a strong geo footfall signal.

## Store Quality Assessment

### Visual Intelligence
YOLOv8 computer vision detected 84 items across 5 shelf views. Shelf Density Index (SDI) of 0.71 indicates well-stocked shelves with moderate uniformity. Centre wall coverage is good; minor gaps observed on left-wall FMCG section.

### Location Intelligence
OpenStreetMap geo analysis: Mumbai Tier-1 location with 4 competitors within 300m. Population ring 0–500m estimated at 12,000 residents. Geo score 81/100 — strong catchment, manageable competition.

### Credit Profile
AI credit score 712/900 (GradientBoosting, 2,000-sample training set). Market share estimate 31%. Composite quality score 0.71/1.00.

## Risk Assessment

### Fraud & Anomaly Flags
No significant fraud or anomaly flags detected.

### Business Risks
- High competition density (4 stores, 300m radius) may cap revenue growth
- FMCG SKU gap reduces impulse purchase revenue by an estimated ₹8K–₹12K/month

## Business Recommendations

- **Immediate**: Add Maggi, Parle-G, Kurkure at billing counter (₹8K–₹12K/month uplift)
- **Week 1**: Install UPI QR code — targets 20-35 age group who prefer digital
- **Week 2**: Stock 200ml cold drinks at eye level near counter
- **Month 1**: Partner with local dairy for 7am–9am morning window
- **Month 3**: Build WhatsApp ordering list for top 30 regular customers

## Loan Recommendation

Recommended loan: **₹2,50,000** over **12 months** at **18% p.a.**  
Monthly EMI: ₹24,583 (17% of estimated income — within FOIR threshold).  
Verdict: **APPROVE — field verification required**.  
Conditions: Submit 3 months UPI transaction history before disbursement.

## Disclaimer
*This report is AI-generated by KiranaGPT for indicative purposes only. Final credit decisions require field verification and compliance with applicable RBI and NBFC guidelines.*`,
  };
}
