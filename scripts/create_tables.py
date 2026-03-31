"""
Run this once to create all tables in Supabase.
Usage: python scripts/create_tables.py
"""

import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# We'll create tables via SQL using Supabase's rpc or REST
# Since supabase-py doesn't expose DDL directly, print the SQL to run in Supabase dashboard

SQL = """
-- COMPANIES
create table if not exists companies (
    id uuid primary key default gen_random_uuid(),
    name text not null unique,
    website text,
    tier integer default 2,          -- 1 = top target, 2 = strong, 3 = watch
    source text,                      -- manual, twitter, hn, linkedin, crunchbase, product_hunt
    hiring_status text default 'unknown',  -- yes, no, unknown
    last_checked timestamp,
    attention_score integer,          -- 0-100, for non-hiring companies
    attractiveness_score integer,     -- 0-100, for hiring companies
    stage text,                       -- Series A, B, C etc
    funding_amount text,
    funding_date text,
    domain text,                      -- conversational_ai, fintech, enterprise_saas etc
    company_size text,                -- 1-50, 50-200, 200-500, 500+
    location text,
    india_angle boolean default false,
    no_list boolean default false,    -- true = excluded
    no_list_reason text,
    research_brief jsonb,             -- enriched company data (news, CEO tweets, product info)
    created_at timestamp default now(),
    updated_at timestamp default now()
);

-- JOBS
create table if not exists jobs (
    id uuid primary key default gen_random_uuid(),
    company_id uuid references companies(id),
    company_name text,
    title text,
    url text,
    jd_text text,
    source text,                      -- greenhouse, ashby, linkedin, wellfound, hn
    attractiveness_score integer,     -- 0-100
    score_breakdown jsonb,            -- {role_fit: 28, company_fit: 22, ...}
    score_reasoning text,             -- plain english explanation
    status text default 'new',        -- new, borderline, prep_ready, applied, interviewing, rejected, offer
    seniority_pass boolean,           -- passed seniority filter?
    no_list_pass boolean,             -- passed no-list filter?
    created_at timestamp default now(),
    updated_at timestamp default now()
);

-- APPLICATIONS
create table if not exists applications (
    id uuid primary key default gen_random_uuid(),
    job_id uuid references jobs(id),
    company_id uuid references companies(id),
    company_name text,
    role_title text,
    resume_version text,
    cover_letter text,
    ats_gaps text,                    -- keywords to add
    bullets_to_lead text,             -- which resume bullets to surface first
    outreach_target_name text,
    outreach_target_title text,
    outreach_target_linkedin text,
    warm_path text,                   -- Wharton alum, PayPal connection etc
    applied_at timestamp,
    applied_via text,                 -- linkedin, greenhouse, ashby, email
    follow_up_due timestamp,
    follow_up_sent_at timestamp,
    response_received boolean default false,
    response_date timestamp,
    notes text,
    created_at timestamp default now()
);

-- OUTREACH
create table if not exists outreach (
    id uuid primary key default gen_random_uuid(),
    company_id uuid references companies(id),
    company_name text,
    contact_name text,
    contact_title text,
    contact_linkedin text,
    outreach_type text,               -- founder_note, linkedin_connect, prototype, follow_up
    insight_angle text,               -- what specific observation Rachita has
    message_draft text,
    message_sent text,
    sent_at timestamp,
    response_received boolean default false,
    response_date timestamp,
    next_action text,
    next_action_date timestamp,
    created_at timestamp default now()
);

-- SIGNALS
create table if not exists signals (
    id uuid primary key default gen_random_uuid(),
    source text,                      -- twitter, hn, product_hunt, crunchbase
    raw_content text,
    extracted_company text,
    company_id uuid references companies(id),
    signal_type text,                 -- hiring, funding, launch, other
    processed boolean default false,
    needs_human_help boolean default false,  -- couldn't identify company
    created_at timestamp default now()
);

-- AGENT ACTIONS LOG
create table if not exists agent_actions_log (
    id uuid primary key default gen_random_uuid(),
    action_type text,                 -- score_job, draft_cover_letter, send_outreach, etc
    company_id uuid references companies(id),
    job_id uuid references jobs(id),
    description text,
    outcome text,                     -- success, failed, pending_review
    autonomous boolean default false,
    approved_by_user boolean default false,
    error_message text,
    created_at timestamp default now()
);
"""

print("=" * 60)
print("COPY AND RUN THIS SQL IN SUPABASE:")
print("Go to: supabase.com → your project → SQL Editor → New query")
print("=" * 60)
print(SQL)
print("=" * 60)
print("After running, come back and we'll load your company list.")
