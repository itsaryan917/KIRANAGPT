-- KiraNA Underwriting System — Seed Data
-- Run after schema.sql to populate sample records

insert into public.underwriting_results
  (id, store_name, owner_name, monthly_revenue, monthly_profit, confidence, risk_score, decision, fraud_flags, loan_sizing, feature_scores, location, images_count, created_at)
values
(
  'ABC123DEF',
  'Patel Provisions',
  'Suresh Patel',
  142000,
  24500,
  0.83,
  22,
  'approve',
  '[]'::jsonb,
  '{"recommended":147000,"minimum":73500,"maximum":220500,"tenure_months":12,"interest_rate":18.5,"emi":14393}'::jsonb,
  '[
    {"name":"Stock Density","score":88,"weight":0.25,"label":"Stock Density"},
    {"name":"Shelf Utilization","score":76,"weight":0.2,"label":"Shelf Utilization"},
    {"name":"Footfall Proxy","score":82,"weight":0.2,"label":"Footfall Proxy"},
    {"name":"Store Cleanliness","score":79,"weight":0.15,"label":"Store Cleanliness"},
    {"name":"Digital Payment Signs","score":65,"weight":0.1,"label":"Digital Payment Signs"},
    {"name":"Signage Quality","score":71,"weight":0.1,"label":"Signage Quality"}
  ]'::jsonb,
  '{"lat":19.0760,"lng":72.8777,"accuracy":12}'::jsonb,
  5,
  now() - interval '2 days'
),
(
  'GHI456JKL',
  'Singh Kirana',
  'Gurpreet Singh',
  88000,
  13200,
  0.61,
  48,
  'review',
  '[{"code":"REVENUE_SPIKE","severity":"low","description":"Declared revenue 40% above 6-month trailing average"}]'::jsonb,
  '{"recommended":79200,"minimum":39600,"maximum":118800,"tenure_months":12,"interest_rate":18.5,"emi":7751}'::jsonb,
  '[
    {"name":"Stock Density","score":62,"weight":0.25,"label":"Stock Density"},
    {"name":"Shelf Utilization","score":55,"weight":0.2,"label":"Shelf Utilization"},
    {"name":"Footfall Proxy","score":68,"weight":0.2,"label":"Footfall Proxy"},
    {"name":"Store Cleanliness","score":58,"weight":0.15,"label":"Store Cleanliness"},
    {"name":"Digital Payment Signs","score":45,"weight":0.1,"label":"Digital Payment Signs"},
    {"name":"Signage Quality","score":50,"weight":0.1,"label":"Signage Quality"}
  ]'::jsonb,
  '{"lat":28.6139,"lng":77.2090,"accuracy":18}'::jsonb,
  5,
  now() - interval '5 days'
),
(
  'MNO789PQR',
  'Kumar General Store',
  'Rajesh Kumar',
  55000,
  7700,
  0.38,
  76,
  'reject',
  '[
    {"code":"LOCATION_MISMATCH","severity":"high","description":"GPS coordinates differ from registered address by >2km"},
    {"code":"LOW_STOCK_DENSITY","severity":"medium","description":"Shelf utilization below minimum threshold for loan eligibility"}
  ]'::jsonb,
  '{"recommended":46200,"minimum":23100,"maximum":69300,"tenure_months":12,"interest_rate":18.5,"emi":4522}'::jsonb,
  '[
    {"name":"Stock Density","score":32,"weight":0.25,"label":"Stock Density"},
    {"name":"Shelf Utilization","score":28,"weight":0.2,"label":"Shelf Utilization"},
    {"name":"Footfall Proxy","score":41,"weight":0.2,"label":"Footfall Proxy"},
    {"name":"Store Cleanliness","score":45,"weight":0.15,"label":"Store Cleanliness"},
    {"name":"Digital Payment Signs","score":22,"weight":0.1,"label":"Digital Payment Signs"},
    {"name":"Signage Quality","score":35,"weight":0.1,"label":"Signage Quality"}
  ]'::jsonb,
  '{"lat":13.0827,"lng":80.2707,"accuracy":25}'::jsonb,
  5,
  now() - interval '8 days'
);
