// KiranaGPT API Layer — supports both /underwrite (original) and /ai-insights (agentic)

import type {
  UnderwriteRequest,
  UnderwriteApiResponse,
  HistoryApiResponse,
} from '../types/underwriting';

import { supabase } from './supabase';
import { fetchHistory } from './db';

// ============================================================
// MOCK DATA (offline / demo mode)
// ============================================================

function getMockUnderwrite(req: UnderwriteRequest): Record<string, unknown> {
  const shop_size = req.optional?.shop_size ?? 200;
  let rent = req.optional?.rent ?? 0;
  const years = req.optional?.years_in_operation ?? 2;

  const visual_score = Math.min(0.95, 0.72 + (years >= 5 ? 0.1 : 0.0) - (shop_size > 800 ? 0.15 : 0));
  const geo_score = 0.65 + (req.gps.lat > 19.0 ? 0.08 : -0.05);

  const fraud_flags: Record<string, unknown>[] = [];
  const risk_flags: string[] = [];

  if (shop_size > 800) {
    fraud_flags.push({
      rule_id: 'CROSS_SIZE_TO_ITEMS_MISMATCH',
      severity: 'high',
      description: `Large shop size claimed (${shop_size} sq ft) but extremely few items detected.`,
    });
    risk_flags.push('claimed_size_vs_inventory_mismatch');
  }

  const est_rev = Math.round(25000 * (1 + 0.3 * 3) * 3 * (0.5 + geo_score) * (0.8 + 0.6 * 0.5));

  if (req.optional?.rent !== undefined && rent > est_rev * 0.4) {
    fraud_flags.push({
      rule_id: 'CROSS_RENT_TO_REVENUE_CRITICAL',
      severity: 'critical',
      description: `Monthly rent (₹${rent.toLocaleString()}) is dangerously high relative to estimated revenue (₹${est_rev.toLocaleString()}).`,
    });
  }

  const fraud_score = fraud_flags.length > 0
    ? Math.min(fraud_flags.reduce((sum, f) => {
        const w: Record<string, number> = { low: 0.15, medium: 0.4, high: 0.7, critical: 1.0 };
        return sum + (w[f.severity as string] ?? 0.4);
      }, 0) / 2.0, 1.0)
    : 0.05;

  const composite_score = Math.max(0, Math.min(1.0, (0.4 * visual_score + 0.35 * geo_score) - 0.25 * fraud_score));

  let decision = 'REVIEW';
  if (composite_score >= 0.65 && !fraud_flags.some((f) => f.severity === 'critical')) decision = 'APPROVE';
  else if (composite_score <= 0.35 || fraud_flags.some((f) => f.severity === 'critical')) decision = 'REJECT';

  let confidence = (1 - Math.abs(visual_score - geo_score)) * (0.5 + 0.5 * Math.abs(composite_score - 0.5));
  if (years >= 5) confidence = Math.min(confidence + 0.1, 0.95);

  const uncertainty_margin = 0.4 - confidence * 0.3;
  const monthly_revenue = Math.round(est_rev);
  const revenue_range = [
    Math.round(monthly_revenue * (1 - uncertainty_margin)),
    Math.round(monthly_revenue * (1 + uncertainty_margin)),
  ];
  const daily_range = [Math.round(revenue_range[0] / 30), Math.round(revenue_range[1] / 30)];
  const income_range = [
    Math.max(1000, Math.round(revenue_range[0] * 0.15) - rent),
    Math.max(2000, Math.round(revenue_range[1] * 0.22) - rent),
  ];

  const credit_score = Math.round(300 + Math.max(0, Math.min(composite_score - 0.1 * fraud_score, 1.0)) * 600);
  const market_share = 0.15 + composite_score * 0.3;

  // Mock AI agent outputs
  const health = Math.round(composite_score * 100);
  const business_insights = {
    business_health_score: health,
    health_grade: health >= 80 ? 'A' : health >= 65 ? 'B' : health >= 50 ? 'C' : health >= 35 ? 'D' : 'F',
    top_problems: [
      visual_score < 0.5 ? 'Low shelf occupancy — shelves appear under-stocked' : 'Moderate shelf density could be improved',
      geo_score < 0.5 ? 'High competition within 300m radius' : 'Market saturation is manageable',
      'Limited SKU diversity detected in product mix',
    ],
    top_opportunities: [
      'Add high-margin FMCG items: biscuits, chips, instant noodles',
      'Install UPI QR code to attract digital-first customers',
      'Stock seasonal items 2 weeks before festivals for higher margins',
    ],
    inventory_recommendations: [
      { category: 'FMCG', action: 'Add Parle-G, Lay\'s, Maggi noodles', reason: 'High velocity, 25-35% margin' },
      { category: 'Staples', action: 'Expand rice and dal variety (5kg packs)', reason: 'Core daily demand driver' },
      { category: 'Beverages', action: 'Stock cold drinks and water bottles', reason: 'Impulse purchase, fast moving' },
    ],
    revenue_growth_strategy: `Focus on high-margin FMCG items and offer home delivery within 500m radius. 
    Install a digital display of today\'s offers. Target ₹${Math.round(est_rev * 1.15).toLocaleString('en-IN')} monthly 
    by stocking 15-20 new fast-moving SKUs.`,
    expected_revenue_increase_pct: Math.min(35, Math.max(5, Math.round((1 - composite_score) * 40))),
    risk_assessment: `Store shows ${decision === 'APPROVE' ? 'low to moderate' : decision === 'REVIEW' ? 'moderate' : 'high'} risk. Revenue is ${decision === 'APPROVE' ? 'stable and consistent' : 'uncertain and needs verification'}.`,
    quick_wins: ['Install UPI QR code today', 'Add 5 fast-moving snack SKUs this week'],
    long_term_plays: ['Build WhatsApp ordering list for regular customers'],
    fallback: true,
  };

  const recommended_loan = Math.round(Math.min(4 * monthly_revenue, 3 * income_range[1] * 12) * (0.5 + 0.7 * composite_score));
  const rate = decision === 'APPROVE' ? 18 : decision === 'REVIEW' ? 22 : 26;
  const loan_advice = {
    recommended_loan_inr: recommended_loan,
    minimum_loan_inr: Math.round(recommended_loan * 0.5),
    maximum_loan_inr: Math.round(recommended_loan * 1.5),
    reasoning: `Based on an estimated monthly revenue of ₹${monthly_revenue.toLocaleString('en-IN')} and an AI credit score of ${credit_score}/900, a loan of ₹${recommended_loan.toLocaleString('en-IN')} is recommended. The composite quality score of ${composite_score.toFixed(2)} reflects ${decision === 'APPROVE' ? 'a well-stocked, well-located store' : 'areas requiring improvement'}. Risk has been priced into the ${rate}% interest rate.`,
    key_strengths: [geo_score > 0.5 ? 'Strong location with good footfall potential' : 'Manageable competition in area', 'Consistent daily revenue pattern detected'],
    key_risks: [fraud_flags.length > 0 ? 'Active fraud/anomaly flags require field verification' : 'No formal credit history available', 'Revenue depends on consistent inventory restocking'],
    suggested_tenure_months: 12,
    interest_rate_pct: rate,
    monthly_emi_inr: Math.round((recommended_loan * (1 + rate / 100)) / 12),
    approval_conditions: fraud_flags.length > 0 ? 'Field officer to verify store physically before disbursement' : 'Submit 3 months UPI transaction history',
    lender_verdict: decision === 'APPROVE' ? 'APPROVE' : decision === 'REVIEW' ? 'CONDITIONAL_APPROVE' : 'REFER_TO_BRANCH',
    next_steps: 'Submit KYC documents and UPI history to nearest branch for final approval.',
    fallback: true,
  };

  const report_markdown = `# KiranaGPT Underwriting Report

**Store ID:** MOCK-${Math.random().toString(36).slice(2, 6).toUpperCase()}  
**Report Date:** ${new Date().toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' })}  
**Assessment:** ${decision === 'APPROVE' ? '✅ APPROVE' : decision === 'REVIEW' ? '⚠️ REVIEW' : '❌ REJECT'}

---

## Executive Summary

This kirana store has received an underwriting decision of **${decision}** based on multi-modal AI analysis 
of 5 store images and GPS location. Monthly revenue is estimated at ₹${revenue_range[0].toLocaleString('en-IN')}–₹${revenue_range[1].toLocaleString('en-IN')} 
with a confidence level of ${(confidence * 100).toFixed(1)}%.

## Store Quality Assessment

### Visual Intelligence
YOLOv8 computer vision analysis indicates a visual quality score of ${(visual_score * 100).toFixed(0)}/100. 
Shelf occupancy and product density are ${visual_score > 0.6 ? 'good' : 'moderate and can be improved'}.

### Location Intelligence
Geospatial analysis shows a location score of ${(geo_score * 100).toFixed(0)}/100, factoring population density, 
POI proximity, and competitor count within 300m.

## Risk Assessment

${fraud_flags.length > 0 ? fraud_flags.map(f => `- **${f.rule_id}** [${(f.severity as string).toUpperCase()}]: ${f.description}`).join('\n') : 'No significant fraud or anomaly flags detected.'}

## Business Recommendations

- Stock high-turnover FMCG items: biscuits, chips, instant noodles (25-35% margin)
- Enable UPI payments via QR code to attract digital customers
- Maintain consistent shelf stocking — low SDI reduces credit score
- Track daily sales via a notebook or app to build formal credit history
- Consider a local delivery service within 500m radius for repeat orders

## Loan Recommendation

Recommended loan: **₹${recommended_loan.toLocaleString('en-IN')}** over **12 months** at **${rate}% p.a.**  
Monthly EMI: ₹${Math.round((recommended_loan * (1 + rate / 100)) / 12).toLocaleString('en-IN')}.  
Verdict: **${decision === 'APPROVE' ? 'APPROVE' : 'CONDITIONAL APPROVE — field verification required'}**.

## Disclaimer
*This report is AI-generated by KiranaGPT for indicative purposes only.*`;

  return {
    store_id: `MOCK-${Math.random().toString(36).slice(2, 6).toUpperCase()}`,
    visual_score, geo_score, sku_score: 0.76, competition_score: 0.65,
    fraud_score, composite_score, decision, confidence,
    fraud_flags, risk_flags,
    recommendation: decision === 'APPROVE' ? 'approved' : decision === 'REJECT' ? 'rejected' : 'needs_verification',
    monthly_revenue_range: revenue_range,
    monthly_income_range: income_range,
    daily_sales_range: daily_range,
    confidence_score: confidence,
    ml_outputs: { credit_score, market_share },
    business_insights,
    loan_advice,
    report_markdown,
    agents_run: ['business_advisor', 'loan_advisor', 'report_agent'],
    ai_powered: true,
    agent_elapsed_s: 4.2,
  };
}

// ============================================================
// NORMALIZATION
// ============================================================

function normalize(raw: Record<string, unknown>, req: UnderwriteRequest): Record<string, unknown> {
  const output = (raw.underwriting_output as Record<string, unknown>) || raw;

  const rawDecision = (output.decision || output.recommendation || 'review') as string;
  const decisionMap: Record<string, string> = {
    APPROVE: 'approve', REVIEW: 'review', REJECT: 'reject',
    approved: 'approve', needs_verification: 'review', rejected: 'reject',
  };
  const decision = decisionMap[rawDecision] || rawDecision.toLowerCase();

  const revenueRange = (output.monthly_revenue_range as number[]) ?? [0, 0];
  const incomeRange = (output.monthly_income_range as number[]) ?? [0, 0];
  const monthly_revenue = Math.round((revenueRange[0] + revenueRange[1]) / 2) || (output.monthly_revenue as number) || 220000;
  const monthly_profit = Math.round((incomeRange[0] + incomeRange[1]) / 2) || (output.monthly_profit as number) || 35000;
  const confidence = (output.confidence || output.confidence_score || 0.72) as number;
  const location = { lat: req.gps.lat, lng: req.gps.lng, accuracy: 10 };

  const scores = [
    { name: 'SDI', label: 'Shelf Density Index', score: Math.round(((output.visual_score as number) ?? 0.8) * 100), weight: 0.2 },
    { name: 'SKU', label: 'SKU Diversity Score', score: Math.round(((output.sku_score as number) ?? 0.75) * 100), weight: 0.2 },
    { name: 'Geo', label: 'Catchment & Footfall', score: Math.round(((output.geo_score as number) ?? 0.85) * 100), weight: 0.25 },
    { name: 'Comp', label: 'Competition Density', score: Math.round(((output.competition_score as number) ?? 0.6) * 100), weight: 0.15 },
    { name: 'Fraud', label: 'Fraud Resilience', score: Math.round((1 - ((output.fraud_score as number) ?? 0)) * 100), weight: 0.2 },
  ];

  const mlOutputs = (raw.ml_outputs as Record<string, number>) || {};
  const creditScoreVal = mlOutputs.credit_score || 600;
  const yearsInOperation = req.optional?.years_in_operation ?? 2;
  const creditFactor = Math.max(0, Math.min((creditScoreVal - 300) / 600, 1.0));
  const ageFactor = Math.max(0, Math.min(yearsInOperation / 5.0, 1.0));
  const visualFactor = (output.visual_score as number) ?? 0.7;
  const fraudFactor = Math.max(0, 1.0 - ((output.fraud_score as number) ?? 0.05));
  const quality = 0.3 * creditFactor + 0.2 * ageFactor + 0.3 * visualFactor + 0.2 * fraudFactor;
  const riskMultiplier = 0.5 + 0.7 * quality;
  const revenueBase = monthly_revenue || 100000;
  const profitBase = monthly_profit || 20000;
  const revenueCap = 4 * revenueBase;
  const profitCap = 3 * (12 * profitBase);
  const baseEligibleLoan = Math.min(revenueCap, profitCap);
  const recommendedLoan = Math.round(baseEligibleLoan * riskMultiplier);
  const emi = Math.round((recommendedLoan * 1.18) / 12);

  // Use loan_advice from AI agent if available
  const loanAdvice = raw.loan_advice as Record<string, unknown> | undefined;
  const loan_sizing = {
    recommended: loanAdvice?.recommended_loan_inr as number || recommendedLoan,
    minimum: loanAdvice?.minimum_loan_inr as number || Math.round(recommendedLoan * 0.5),
    maximum: loanAdvice?.maximum_loan_inr as number || Math.round(recommendedLoan * 1.5),
    tenure_months: loanAdvice?.suggested_tenure_months as number || 12,
    interest_rate: loanAdvice?.interest_rate_pct as number || 18,
    emi: loanAdvice?.monthly_emi_inr as number || emi,
  };

  const pipelineFlags = ((output.fraud_flags as Record<string, unknown>[]) ?? []).map((f) => {
    if (typeof f === 'string') return { code: f, severity: 'medium' as const, description: f };
    return {
      code: (f.rule_id || f.code || 'FLAG') as string,
      severity: (f.severity || 'medium') as 'low' | 'medium' | 'high' | 'critical',
      description: (f.description || '') as string,
    };
  });
  const riskFlagArr = ((output.risk_flags as string[]) ?? []).map((r) => ({
    code: r,
    severity: 'medium' as const,
    description: r.replace(/_/g, ' '),
  }));
  const allFlags = [...pipelineFlags, ...riskFlagArr];
  const compositeScore = (output.composite_score as number) ?? 0.5;
  const risk_score = Math.round((1 - compositeScore) * 100);

  return {
    ...output,
    decision, location, feature_scores: scores, loan_sizing,
    monthly_revenue, monthly_profit, confidence, risk_score,
    store_name: (output.store_id as string) ?? 'Unknown Store',
    owner_name: 'Store Owner',
    id: Math.random().toString(36).slice(2, 10).toUpperCase(),
    created_at: new Date().toISOString(),
    images_count: req.images.length,
    fraud_flags: allFlags,
    breakdown: (output.breakdown as Record<string, number>) ?? { visual_contribution: 0, geo_contribution: 0, fraud_penalty: 0 },
    metadata: (output.metadata as Record<string, unknown>) ?? {},
    // AI agent outputs (pass through if present)
    business_insights: raw.business_insights,
    loan_advice: raw.loan_advice,
    report_markdown: raw.report_markdown,
    agents_run: raw.agents_run,
    agent_elapsed_s: raw.agent_elapsed_s,
    ai_powered: raw.ai_powered,
  };
}

// ============================================================
// MAIN API CALL
// ============================================================

export async function submitUnderwrite(
  req: UnderwriteRequest & { useAI?: boolean }
): Promise<UnderwriteApiResponse> {
  try {
    if (!req.images || req.images.length < 5) {
      throw new Error('Please upload all 5 required images');
    }

    const mockMode = process.env.NEXT_PUBLIC_MOCK_MODE === 'true' || !process.env.NEXT_PUBLIC_API_BASE_URL;

    let raw: Record<string, unknown>;

    if (mockMode) {
      await new Promise((resolve) => setTimeout(resolve, 2000));
      raw = getMockUnderwrite(req);
    } else {
      const formData = new FormData();
      formData.append('front', req.images[0]);
      formData.append('billing_area', req.images[1]);
      formData.append('left_wall', req.images[2]);
      formData.append('centre_wall', req.images[3]);
      formData.append('right_wall', req.images[4]);
      formData.append('lat', req.gps.lat.toString());
      formData.append('lng', req.gps.lng.toString());
      if (req.optional?.shop_size != null) formData.append('shop_size', req.optional.shop_size.toString());
      if (req.optional?.rent != null) formData.append('rent', req.optional.rent.toString());
      if (req.optional?.years_in_operation != null) formData.append('years_in_operation', req.optional.years_in_operation.toString());

      const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
      // Use /ai-insights for full agentic experience, fallback to /underwrite
      const endpoint = req.useAI !== false ? '/ai-insights' : '/underwrite';

      const res = await fetch(`${apiBase}${endpoint}`, { method: 'POST', body: formData });
      if (!res.ok) {
        const errorText = await res.text();
        throw new Error(`Backend error ${res.status}: ${errorText}`);
      }
      raw = await res.json();
      if (raw.error) throw new Error(raw.error as string);
    }

    const normalized = normalize(raw, req);
    return { success: true, data: normalized as Parameters<typeof normalize>[0] & import('../types/underwriting').UnderwritingResult };
  } catch (err) {
    return { success: false, error: err instanceof Error ? err.message : 'Unknown error' };
  }
}

// ============================================================
// HISTORY
// ============================================================

export async function getHistory(): Promise<HistoryApiResponse> {
  try {
    const rows = await fetchHistory();
    return { success: true, data: rows };
  } catch (err) {
    return { success: false, error: err instanceof Error ? err.message : 'Failed to load history' };
  }
}

export async function addLocation(lat: number, lng: number, metadata?: Record<string, unknown>) {
  try {
    const { data, error } = await supabase.from('locations').insert([
      { latitude: lat, longitude: lng, metadata, created_at: new Date().toISOString() },
    ]);
    if (error) return { success: false, error: error.message };
    return { success: true, data };
  } catch (err) {
    return { success: false, error: err instanceof Error ? err.message : 'Failed to add location' };
  }
}
