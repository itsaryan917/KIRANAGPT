export interface GpsCoordinates {
  lat: number;
  lng: number;
  accuracy?: number;
}

export interface FeatureScore {
  name: string;
  score: number; // 0-100
  weight: number; // 0-1
  label: string;
}

export interface FraudFlag {
  code: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  description: string;
}

export interface LoanSizing {
  recommended: number;
  minimum: number;
  maximum: number;
  tenure_months: number;
  interest_rate: number;
  emi: number;
}

export interface BusinessInsights {
  business_health_score: number;
  health_grade: string;
  top_problems: string[];
  top_opportunities: string[];
  inventory_recommendations: Array<{ category: string; action: string; reason: string }>;
  revenue_growth_strategy: string;
  expected_revenue_increase_pct: number;
  risk_assessment: string;
  quick_wins: string[];
  long_term_plays: string[];
  fallback?: boolean;
}

export interface LoanAdvice {
  recommended_loan_inr: number;
  minimum_loan_inr: number;
  maximum_loan_inr: number;
  reasoning: string;
  key_strengths: string[];
  key_risks: string[];
  suggested_tenure_months: number;
  interest_rate_pct: number;
  monthly_emi_inr: number;
  approval_conditions: string;
  lender_verdict: string;
  next_steps: string;
  fallback?: boolean;
}

export interface UnderwritingResult {
  id: string;
  store_name: string;
  owner_name: string;
  monthly_revenue: number;
  monthly_profit: number;
  confidence: number; // 0-1
  risk_score: number; // 0-100 (lower is better)
  decision: 'approve' | 'reject' | 'review';
  fraud_flags: FraudFlag[];
  loan_sizing: LoanSizing;
  feature_scores: FeatureScore[];
  created_at: string;
  location: GpsCoordinates;
  images_count: number;
  // AI agent outputs (present when using /ai-insights endpoint)
  business_insights?: BusinessInsights;
  loan_advice?: LoanAdvice;
  report_markdown?: string;
  agents_run?: string[];
  agent_elapsed_s?: number;
  ai_powered?: boolean;
}

export interface UnderwriteRequest {
  images: File[];
  gps: GpsCoordinates;
  optional?: {
    shop_size?: number;
    rent?: number;
    years_in_operation?: number;
  };
  useAI?: boolean;
}

export interface UnderwriteApiResponse {
  success: boolean;
  data?: UnderwritingResult & Record<string, unknown>;
  error?: string;
}

export interface HistoryRecord {
  id: string;
  store_name: string;
  owner_name: string;
  monthly_revenue: number;
  confidence: number;
  decision: 'approve' | 'reject' | 'review';
  risk_score: number;
  created_at: string;
  loan_amount: number;
}

export interface HistoryApiResponse {
  success: boolean;
  data?: HistoryRecord[];
  error?: string;
}

export type UploadStatus = 'idle' | 'uploading' | 'analyzing' | 'done' | 'error';
