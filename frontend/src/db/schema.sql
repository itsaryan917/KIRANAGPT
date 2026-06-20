-- KiraNA Underwriting System — Supabase Schema
-- Run this in your Supabase SQL editor

create extension if not exists "uuid-ossp";

create table if not exists public.underwriting_results (
  id             text primary key,
  store_name     text not null,
  owner_name     text not null,
  monthly_revenue numeric(14,2) not null,
  monthly_profit  numeric(14,2) not null,
  confidence      numeric(5,4) not null check (confidence >= 0 and confidence <= 1),
  risk_score      integer not null check (risk_score >= 0 and risk_score <= 100),
  decision        text not null check (decision in ('approve', 'review', 'reject')),
  fraud_flags     jsonb not null default '[]'::jsonb,
  loan_sizing     jsonb not null,
  feature_scores  jsonb not null default '[]'::jsonb,
  location        jsonb not null,
  images_count    integer not null default 0,
  created_at      timestamptz not null default now()
);

-- Indexes
create index if not exists idx_uw_created_at on public.underwriting_results (created_at desc);
create index if not exists idx_uw_decision   on public.underwriting_results (decision);
create index if not exists idx_uw_risk_score on public.underwriting_results (risk_score);

-- Row Level Security
alter table public.underwriting_results enable row level security;

-- Allow all authenticated reads (adjust per your RBAC needs)
create policy "Allow authenticated read" on public.underwriting_results
  for select using (true);

create policy "Allow authenticated insert" on public.underwriting_results
  for insert with check (true);

-- View: summary for history table
create or replace view public.underwriting_summary as
select
  id,
  store_name,
  owner_name,
  monthly_revenue,
  confidence,
  decision,
  risk_score,
  created_at,
  (loan_sizing->>'recommended')::numeric as loan_amount
from public.underwriting_results
order by created_at desc;
