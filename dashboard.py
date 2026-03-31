"""
Job Agent Dashboard
Run: streamlit run dashboard.py
"""

import os
import html as html_lib
import streamlit as st
from pathlib import Path
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from supabase import create_client
from collections import defaultdict


# --- Sector taxonomy (fallback keyword matching for jobs without company record) ---
_SECTOR_MAP = [
    ("AI employees",     ["ai workforce", "ai worker", "ai employee", "ai superhuman",
                          "ai sales rep", "digital worker", "agentic workforce", "ai teammate"]),
    ("Voice AI",         ["voice ai", "voice agent", "voice interview", "speech ai", "conversational voice",
                          "voice-based", "audio ai"]),
    ("Video AI",         ["video generation", "text-to-video", "avatar", "video ai", "synthetic video",
                          "ai video", "talking head"]),
    ("Vibe coding",      ["ai coding", "code generation", "ai-powered ide", "no-code", "low-code",
                          "app builder", "replit", "cursor", "copilot", "text-to-app", "text-to-code"]),
    ("Fintech",          ["fintech", "payments", "payment platform", "banking", "lending", "credit rating",
                          "cross-border", "fx ", "stablecoin", "embedded finance", "checkout", "neobank",
                          "financial institution", "aml", "kyc", "kyb"]),
    ("Legal AI",         ["legal", "law firm", "contract", "legal tech", "litigation", "legal compliance",
                          "law ", "attorney", "counsel"]),
    ("Health AI",        ["health", "medical", "clinical", "pharma", "biotech", "patient", "ehr",
                          "healthcare", "wellness", "mental health"]),
    ("Cybersecurity AI", ["cybersecurity", "incident response", "threat detection",
                          "vulnerability scanner", "soc platform"]),
    ("Developer tools",  ["developer platform", "devtools", "api platform", "background jobs",
                          "model context protocol", "sdk ", "deployment platform"]),
    ("Industrial AI",    ["manufacturing", "mep ", "mechanical electrical", "construction", "industrial",
                          "supply chain", "factory", "robotics"]),
    ("Enterprise AI",    ["enterprise ai", "enterprise software", "b2b ai", "ai workspace",
                          "ai platform", "business automation", "workflow automation", "productivity"]),
    ("HR / Recruiting",  ["recruiting", "talent acquisition", "hr platform", "hiring platform", "people ops"]),
    ("Data / Analytics", ["data platform", "analytics", "business intelligence", "data pipeline"]),
]


def _derive_sector(job: dict) -> str:
    bd = job.get("score_breakdown") or {}
    if bd.get("sector"):
        return bd["sector"]
    text = ((job.get("score_reasoning") or "") + " " + bd.get("key_angle", "")).lower()
    for label, keywords in _SECTOR_MAP:
        if any(k in text for k in keywords):
            return label
    return "Other"


def _derive_stage(job: dict) -> str:
    bd = job.get("score_breakdown") or {}
    if bd.get("stage"):
        return bd["stage"]
    text = ((job.get("score_reasoning") or "") + " " + (job.get("jd_text") or "")[:300]).lower()
    stage_patterns = [
        ("Pre-Seed", ["pre-seed", "pre seed"]),
        ("Seed",     ["seed round", "seed funding", "seed stage", "seed-stage", "seed-backed"]),
        ("Series A", ["series a"]),
        ("Series B", ["series b"]),
        ("Series C", ["series c"]),
        ("Series D", ["series d"]),
        ("Series E", ["series e"]),
        ("Public",   ["publicly traded", "nasdaq:", "nyse:", "went public", "ipo completed"]),
    ]
    for stage, patterns in stage_patterns:
        if any(p in text for p in patterns):
            return stage
    return ""


load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

st.set_page_config(page_title="Job Agent", layout="wide", page_icon="🥑")

st.markdown("""
<style>
.score-high { color: #16a34a; font-weight: 700; }
.score-mid  { color: #ca8a04; font-weight: 700; }
.score-low  { color: #dc2626; font-weight: 600; }
.score-none { color: #9ca3af; }
.tag { background: #f3f4f6; border-radius: 4px; padding: 2px 8px; font-size: 0.8em; margin-right: 4px; }
/* Remove default Streamlit top padding */
.block-container { padding-top: 1rem !important; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

@st.cache_data(ttl=30)
def load_jobs():
    return supabase.table("jobs").select(
        "id, company_name, title, url, status, attractiveness_score, "
        "score_breakdown, score_reasoning, source, created_at, prep_materials"
    ).order("attractiveness_score", desc=True, nullsfirst=False).execute().data or []


@st.cache_data(ttl=30)
def load_company_lookup():
    try:
        rows = supabase.table("companies").select(
            "name, what_they_do, sector, stage, attention_score, feedback"
        ).execute().data or []
        return {r["name"]: r for r in rows}
    except Exception:
        return {}


@st.cache_data(ttl=30)
def load_radar():
    """Companies scored ≥55 (below threshold are dropped per design)."""
    try:
        return (
            supabase.table("companies")
            .select("*")
            .gte("attention_score", 55)
            .order("attention_score", desc=True, nullsfirst=False)
            .execute()
            .data or []
        )
    except Exception:
        return []


def fmt_date_mdy(iso_or_str: str) -> str:
    """Format ISO timestamp or any date string as MM/DD/YY for display."""
    if not iso_or_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_or_str.replace("Z", "+00:00"))
        return dt.strftime("%-m/%-d/%y")
    except Exception:
        return iso_or_str[:10]


def update_job_status(job_id, new_status):
    supabase.table("jobs").update({"status": new_status}).eq("id", job_id).execute()
    st.session_state.setdefault("hidden_job_ids", set()).add(job_id)
    st.cache_data.clear()


def mark_applied(job_id, bd):
    bd["applied_at"] = datetime.now(timezone.utc).isoformat()
    supabase.table("jobs").update(
        {"status": "applied", "score_breakdown": bd}
    ).eq("id", job_id).execute()
    st.session_state.setdefault("hidden_job_ids", set()).add(job_id)
    st.cache_data.clear()


def mark_reached_out(job_id, bd):
    bd["reached_out_at"] = datetime.now(timezone.utc).isoformat()
    supabase.table("jobs").update({"score_breakdown": bd}).eq("id", job_id).execute()
    # Don't hide — just update state so the button shows as active
    st.session_state.setdefault("reached_out_ids", set()).add(job_id)


def update_radar_status(company_id, new_status, company_name: str = ""):
    supabase.table("companies").update({"radar_status": new_status}).eq("id", company_id).execute()
    st.session_state.setdefault("hidden_company_ids", set()).add(company_id)
    if company_name:
        st.session_state.setdefault("hidden_company_names", set()).add(company_name)
    st.cache_data.clear()


# ---------------------------------------------------------------------------
# Load data + enrich jobs with company-level sector/stage
# ---------------------------------------------------------------------------

jobs = load_jobs()
company_lookup = load_company_lookup()
radar_all = load_radar()

# Enrich all jobs with company-level sector/stage (authoritative — from companies table)
for j in jobs:
    co = company_lookup.get(j["company_name"], {})
    j["_sector"] = co.get("sector") or _derive_sector(j)
    j["_stage"] = co.get("stage") or _derive_stage(j)


# ---------------------------------------------------------------------------
# Header + stats
# ---------------------------------------------------------------------------

col_stats, col_refresh = st.columns([5, 1])
with col_refresh:
    st.write("")
    if st.button("↻ Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

_today_utc = datetime.now(timezone.utc)
_last_monday = (_today_utc - timedelta(days=_today_utc.weekday())).replace(
    hour=0, minute=0, second=0, microsecond=0
)

# Compute this week stats (used in "This week" line below metrics)
try:
    _new_jobs_wk = (
        supabase.table("jobs")
        .select("id", count="exact")
        .gte("created_at", _last_monday.isoformat())
        .execute()
        .count or 0
    )
    _new_radar = (
        supabase.table("companies")
        .select("id", count="exact")
        .gte("created_at", _last_monday.isoformat())
        .not_.is_("attention_score", "null")
        .or_("feedback.is.null,feedback.neq.not_for_me")
        .execute()
        .count or 0
    )
except Exception:
    _new_jobs_wk = 0
    _new_radar = 0

_total_cos = len(company_lookup) or 70

st.markdown(f"""
<details style="border:1px solid #e5e7eb; border-radius:8px; padding:6px 16px 10px 16px; margin-bottom:8px;">
<summary style="font-size:1.08rem; font-weight:600; cursor:pointer; padding:6px 0; list-style:none; display:flex; align-items:center; gap:6px;">
<span style="font-size:0.85em; color:#6b7280;">▶</span> How this agent works
</summary>
<table style="width:100%; border-collapse:collapse; font-size:0.92em; margin-top:8px;">
<tr>
<td style="padding:10px 14px; vertical-align:top; width:25%">
<div style="font-size:1.4em">🏢 → 🔍</div>
<strong>Discovers companies automatically</strong><br>
<span style="color:#6b7280">Every Monday, I poll all {_total_cos}+ tracked company job boards (Ashby, Greenhouse) for open roles. The agent also scans funding news, LinkedIn hiring posts, and newsletters to find new AI-native companies worth adding.</span>
</td>
<td style="padding:10px 14px; vertical-align:top; width:25%">
<div style="font-size:1.4em">🤖 → 📊</div>
<strong>Scores every role and company with Claude</strong><br>
<span style="color:#6b7280">Each role is scored on 5 dimensions: role fit, company fit, end-user layer, growth signal, location. Scoring learns from my actions: companies I apply to become positive benchmarks; roles I skip teach it what to filter out.</span>
</td>
<td style="padding:10px 14px; vertical-align:top; width:25%">
<div style="font-size:1.4em">📂 vs 🔭</div>
<strong>Routes to Open Roles or On Radar</strong><br>
<span style="color:#6b7280">Roles that pass scoring go to Open Roles. Companies with no open roles go to On Radar, the proactive pipeline. Every radar company gets a drafted outreach message written in my voice, based on real messages I've sent before.</span>
</td>
<td style="padding:10px 14px; vertical-align:top; width:25%">
<div style="font-size:1.4em">📋 → ✅</div>
<strong>Tracks everything, drafts everything</strong><br>
<span style="color:#6b7280">Monitors follow-ups on applications and outreach. Generates a Monday brief with my to-do list for the week. Nothing is sent automatically. The agent drafts, I review, I send.</span>
</td>
</tr>
</table>
</details>
""", unsafe_allow_html=True)

_stat_hidden_j  = st.session_state.get("hidden_job_ids", set())
_stat_hidden_cn = st.session_state.get("hidden_company_names", set())
_stat_hidden_ci = st.session_state.get("hidden_company_ids", set())

open_count     = sum(1 for j in jobs if j.get("status") in ["prep_ready", "borderline", "new"] and j.get("id") not in _stat_hidden_j)
pipeline_count = sum(1 for j in jobs if j.get("status") == "pipeline" and j.get("id") not in _stat_hidden_j)
_ro_jobs       = sum(1 for j in jobs if (j.get("score_breakdown") or {}).get("reached_out_at") and j.get("id") not in _stat_hidden_j)
_ro_radar      = sum(1 for r in radar_all if r.get("radar_status") == "reached_out" and r.get("id") not in _stat_hidden_ci)
ro_count       = _ro_jobs + _ro_radar
applied_count  = sum(1 for j in jobs if j.get("status") == "applied" and j.get("id") not in _stat_hidden_j)

radar_count = sum(
    1 for r in radar_all
    if r.get("feedback") != "not_for_me"
    and r.get("radar_status") not in ("reached_out", "applied")
    and r.get("id") not in _stat_hidden_ci
)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("📂 Open Roles", open_count)
c2.metric("🔭 On Radar", radar_count)
c3.metric("📋 Pipeline", pipeline_count)
c4.metric("📧 Reached Out", ro_count)
c5.metric("✅ Applied", applied_count)

st.markdown(f"**This week: {_new_jobs_wk} new roles · {_new_radar} new companies on radar.**")

st.divider()

# ---------------------------------------------------------------------------
# Pipeline runner helper (used in Sources tab, defined here for global access)
# ---------------------------------------------------------------------------

def _render_pipeline_runner(source_key: str):
    _queue  = st.session_state.get("pipeline_queue", [])
    _result = st.session_state.get("pipeline_result")
    _source = st.session_state.get("pipeline_source")
    if _source != source_key:
        return
    if _result:
        _open  = _result["open_roles"]
        _radar = _result["radar_added"]
        _skip  = _result["skipped"]
        _by_co: dict = {}
        for r in _open:
            _by_co.setdefault(r["company"], []).append(r["title"])
        for co_name, titles in _by_co.items():
            st.success(f"**{co_name}**: {len(titles)} role(s) found → Open Roles ({', '.join(titles)})")
        for r in _radar:
            st.success(f"**{r['company']}**: no open roles → On Radar ({r['score']}/100) with outreach draft")
        for r in _skip:
            st.warning(f"**{r['company']}**: not a fit ({r['score']}/100) → skipped")
        if not _open and not _radar and not _skip:
            st.info("Workflow ran — nothing new to add.")
        if st.button("✕ Clear", key=f"pipeline_clear_{source_key}"):
            st.session_state.pop("pipeline_result", None)
            st.session_state.pop("pipeline_source", None)
            st.rerun()
    elif _queue:
        st.info(f"Added to database: **{', '.join(_queue)}**")
        _pc1, _pc2 = st.columns([3, 1])
        with _pc1:
            _run_targeted = st.button(
                f"▶ Run workflow for these {len(_queue)} companies",
                type="primary", key=f"pipeline_run_targeted_{source_key}",
            )
        with _pc2:
            if st.button("✕ Cancel", key=f"pipeline_cancel_{source_key}"):
                st.session_state.pop("pipeline_queue", None)
                st.session_state.pop("pipeline_source", None)
                st.rerun()
        if _run_targeted:
            with st.spinner(f"Running workflow for {len(_queue)} companies..."):
                from agent.pipeline import run_pipeline_for_companies
                _res = run_pipeline_for_companies(_queue)
            st.session_state.pop("pipeline_queue", None)
            st.session_state["pipeline_result"] = _res
            st.cache_data.clear()
            st.rerun()


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------

_nav_col, _refresh_col = st.columns([9, 1])
with _nav_col:
    nav = st.radio(
        "nav",
        ["📂 Open Roles", "🔭 On Radar", "📋 Pipeline", "📧 Reached Out", "✅ Applied", "📡 Sources"],
        horizontal=True,
        label_visibility="collapsed",
        key="main_nav",
    )
with _refresh_col:
    st.write("")
    _run_all_btn = st.button("↺ Refresh all", help="Run workflow for all companies in database", key="run_all_btn", use_container_width=True)

if _run_all_btn:
    _all_names = [r["name"] for r in supabase.table("companies").select("name").execute().data or []]
    with st.spinner(f"Running workflow for all {len(_all_names)} companies..."):
        from agent.pipeline import run_pipeline_for_companies
        _res = run_pipeline_for_companies(_all_names)
    st.session_state["pipeline_result"] = _res
    st.session_state["pipeline_source"] = "global_refresh"
    st.session_state["main_nav"] = "📡 Sources"
    st.cache_data.clear()
    st.rerun()


# ===========================================================================
# OPEN ROLES
# ===========================================================================

_wk_start = (_today_utc - timedelta(days=_today_utc.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
_this_week_job_ids = set(
    j["id"] for j in jobs
    if j.get("created_at", "") >= _wk_start.isoformat()
)

# ===========================================================================
# SOURCES
# ===========================================================================

if nav == "📡 Sources":

    # Show result from the global refresh button (🔄 in nav bar)
    _render_pipeline_runner("global_refresh")

    st.markdown("#### Add from post URL")
    post_url = st.text_input(
        "Paste a LinkedIn or Twitter/X post URL",
        placeholder="https://www.linkedin.com/posts/... or https://x.com/...",
    )

    st.markdown("#### Or paste post text directly")
    st.caption("Use this if LinkedIn blocks the URL fetch (it often does).")
    post_text = st.text_area(
        "Paste the post text here",
        height=150,
        placeholder="Back with another list of startups hiring...\n\n• Acme AI — $50M Series B\n• Notion — hiring PM\n...",
    )

    if st.button("🔍 Extract and add companies", type="primary"):
        if not post_url and not post_text.strip():
            st.warning("Paste a URL or some post text first.")
        else:
            with st.spinner("Extracting company names..."):
                from agent.discover_from_post import process_post
                result = process_post(url=post_url or None, text=post_text.strip() or None)

            if result.get("error"):
                st.error(result["error"])
                st.info("Try pasting the post text directly in the box above.")
            else:
                found = result.get("companies_found", [])
                newly_added = result.get("added", [])
                already_tracked = result.get("already_known", [])

                if not found:
                    st.warning("No company names found. Try typing just the company name (e.g. 'Gamma') or paste a full LinkedIn post.")
                else:
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.markdown("**Added to dashboard**")
                        if newly_added:
                            for c in newly_added:
                                st.markdown(f"- {c}")
                        else:
                            st.caption("None new")
                    with col_b:
                        st.markdown("**Already tracked**")
                        if already_tracked:
                            for c in already_tracked:
                                st.markdown(f"- {c}")
                        else:
                            st.caption("None")

                    if newly_added:
                        st.session_state["pipeline_queue"] = newly_added
                        st.session_state["pipeline_source"] = "post"
                        st.cache_data.clear()
                        st.rerun()

    _render_pipeline_runner("post")

    st.divider()
    st.markdown("#### Auto-scan funding news")
    st.caption("Pulls from Next Play newsletter + TechCrunch. Extracts companies, then asks you what to do.")
    if st.button("📡 Run funding scan", type="primary"):
        with st.spinner("Scanning Next Play and TechCrunch for new companies..."):
            from agent.discover_from_rss import extract_companies_from_rss
            _rss_new = extract_companies_from_rss()
        if _rss_new:
            st.success(f"Found {len(_rss_new)} new companies: {', '.join(_rss_new)}")
            st.session_state["pipeline_queue"] = _rss_new
            st.session_state["pipeline_source"] = "rss"
            st.cache_data.clear()
            st.rerun()
        else:
            st.info("No new companies found in today's feeds.")

    _render_pipeline_runner("rss")

    st.divider()
    st.markdown("#### Connected systems")
    st.markdown("""
<div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:12px; margin-top:8px">

<div style="background:#f9fafb; border-radius:8px; padding:14px">
<div style="font-size:1.2em; margin-bottom:6px">🏢 Job boards</div>
<b>Ashby</b> · 30+ verified company slugs<br>
<b>Greenhouse</b> · 10+ verified company slugs<br>
<b>Work at a Startup</b> · YC company list via Apify<br>
<span style="color:#6b7280; font-size:0.85em">Polled every Monday 9am PT</span>
</div>

<div style="background:#f9fafb; border-radius:8px; padding:14px">
<div style="font-size:1.2em; margin-bottom:6px">💰 Funding signals</div>
<b>TechCrunch</b> · RSS feed<br>
<b>Next Play newsletter</b> · RSS feed<br>
<b>LinkedIn posts</b> · paste URL or text<br>
<span style="color:#6b7280; font-size:0.85em">Scanned every Monday 9:05am PT</span>
</div>

<div style="background:#f9fafb; border-radius:8px; padding:14px">
<div style="font-size:1.2em; margin-bottom:6px">🤖 AI systems</div>
<b>Claude Haiku</b> · role scoring (5 dimensions)<br>
<b>Claude Sonnet</b> · outreach draft generation<br>
<b>Claude Sonnet</b> · company attention scoring<br>
<span style="color:#6b7280; font-size:0.85em">Learns from applied / skipped signals</span>
</div>

<div style="background:#f9fafb; border-radius:8px; padding:14px">
<div style="font-size:1.2em; margin-bottom:6px">🔵 LinkedIn</div>
<b>Curator monitor</b> · watches accounts posting funded startup lists<br>
<b>Post extraction</b> · paste any post, extracts companies<br>
<span style="color:#6b7280; font-size:0.85em">Monday + Thursday 9:10am PT</span>
</div>

<div style="background:#f9fafb; border-radius:8px; padding:14px">
<div style="font-size:1.2em; margin-bottom:6px">🗄️ Database</div>
<b>Supabase (Postgres)</b><br>
Tables: jobs · companies · signals<br>
Stores: scores, drafts, behavioral signals, application history<br>
<span style="color:#6b7280; font-size:0.85em">Single source of truth</span>
</div>

<div style="background:#f9fafb; border-radius:8px; padding:14px">
<div style="font-size:1.2em; margin-bottom:6px">⏰ Scheduler</div>
<b>APScheduler via launchd</b><br>
Mon 9:00am · Job board polling<br>
Mon 9:05am · RSS scan<br>
Mon+Thu 9:10am · LinkedIn monitor<br>
Mon 10:00am · Monday brief
</div>

</div>
""", unsafe_allow_html=True)


# ===========================================================================
# OPEN ROLES
# ===========================================================================

elif nav == "📂 Open Roles":
    _hidden = st.session_state.get("hidden_job_ids", set())
    discover_jobs = [j for j in jobs if j.get("status") in ["prep_ready", "borderline", "new"] and j.get("id") not in _hidden]

    # Filters — use company_lookup-enriched _sector/_stage (already computed above)
    fc1, fc2, fc3, fc4, fc5 = st.columns([1, 1, 1, 1, 1])
    with fc1:
        role_filter = st.selectbox(
            "Role type", ["All", "PM", "Generalist / Ops"], label_visibility="collapsed"
        )
    with fc2:
        all_sectors = sorted(
            set(j["_sector"] for j in discover_jobs
                if j["_sector"] and j["_sector"] != "Cybersecurity AI")
        )
        sector_filter = st.selectbox(
            "Sector", ["All sectors"] + all_sectors, label_visibility="collapsed"
        )
    with fc3:
        all_stages = sorted(set(j["_stage"] for j in discover_jobs if j["_stage"]))
        stage_filter = st.selectbox(
            "Stage", ["All stages"] + all_stages, label_visibility="collapsed"
        )
    with fc4:
        score_tier = st.selectbox(
            "Score",
            ["All scores", "High (75+)", "Medium (55-74)", "Low (<55)", "Unscored"],
            label_visibility="collapsed",
            key="score_filter_roles",
        )
    with fc5:
        week_filter = st.selectbox(
            "When", ["All time", "🆕 This week"], label_visibility="collapsed",
            key="week_filter_roles",
        )

    if week_filter == "🆕 This week":
        discover_jobs = [j for j in discover_jobs if j.get("id") in _this_week_job_ids]
    if role_filter == "PM":
        discover_jobs = [j for j in discover_jobs
                         if (j.get("score_breakdown") or {}).get("role_type") == "pm"]
    elif role_filter == "Generalist / Ops":
        discover_jobs = [j for j in discover_jobs
                         if (j.get("score_breakdown") or {}).get("role_type") == "operator"]
    if sector_filter != "All sectors":
        discover_jobs = [j for j in discover_jobs if j["_sector"] == sector_filter]
    if stage_filter != "All stages":
        discover_jobs = [j for j in discover_jobs if j["_stage"] == stage_filter]
    if score_tier == "High (75+)":
        discover_jobs = [j for j in discover_jobs if (j.get("attractiveness_score") or 0) >= 75]
    elif score_tier == "Medium (55-74)":
        discover_jobs = [j for j in discover_jobs if 55 <= (j.get("attractiveness_score") or 0) < 75]
    elif score_tier == "Low (<55)":
        discover_jobs = [j for j in discover_jobs if 0 < (j.get("attractiveness_score") or 0) < 55]
    elif score_tier == "Unscored":
        discover_jobs = [j for j in discover_jobs if not j.get("attractiveness_score")]

    if not discover_jobs:
        st.info("No roles matching this filter.")
    else:
        by_company = defaultdict(list)
        for j in discover_jobs:
            by_company[j["company_name"]].append(j)

        def best_score(cjobs):
            return max(j.get("attractiveness_score") or 0 for j in cjobs)

        def is_new(cjobs):
            return any(j.get("id") in _this_week_job_ids for j in cjobs)

        sorted_companies = sorted(by_company.items(), key=lambda x: (is_new(x[1]), best_score(x[1])), reverse=True)

        for company, company_jobs in sorted_companies:
            best = best_score(company_jobs)
            role_count = len(company_jobs)

            badge = "🟢" if best >= 75 else ("🟡" if best >= 55 else ("🔴" if best > 0 else "⚪"))

            co_record = company_lookup.get(company, {})
            co_sector = company_jobs[0]["_sector"]
            co_stage  = company_jobs[0]["_stage"]

            is_new = any(j.get("id") in _this_week_job_ids for j in company_jobs)
            label = f"{badge} **{company}**"
            if is_new:
                label += " · 🆕"
            if co_sector:
                label += f" · {co_sector}"
            if co_stage:
                label += f" · {co_stage}"
            if best > 0:
                label += f" · `{best}/100`"
            if role_count > 1:
                label += f" · {role_count} roles"

            with st.expander(label):
                co_what = co_record.get("what_they_do", "")
                if co_what:
                    st.caption(co_what)

                for job in company_jobs:
                    score  = job.get("attractiveness_score")
                    bd     = job.get("score_breakdown") or {}
                    title  = job["title"]
                    job_id = job["id"]
                    job_url = job.get("url", "")
                    reached_out_at = bd.get("reached_out_at")

                    if score and score >= 75:
                        score_html = f'<span class="score-high">{score}/100</span>'
                    elif score and score >= 55:
                        score_html = f'<span class="score-mid">{score}/100</span>'
                    elif score:
                        score_html = f'<span class="score-low">{score}/100</span>'
                    else:
                        score_html = '<span class="score-none">unscored</span>'

                    safe_title = html_lib.escape(title)
                    st.markdown(
                        f"<strong>{safe_title}</strong> &nbsp; {score_html}",
                        unsafe_allow_html=True,
                    )

                    if score:
                        with st.expander("Score breakdown"):
                            cols = st.columns(5)
                            cols[0].metric("Role fit",  f"{bd.get('role_fit','?')}/30")
                            cols[1].metric("Company",   f"{bd.get('company_fit','?')}/25")
                            cols[2].metric("End-user",  f"{bd.get('end_user_layer','?')}/20")
                            cols[3].metric("Growth",    f"{bd.get('growth_signal','?')}/15")
                            cols[4].metric("Location",  f"{bd.get('location_fit','?')}/10")

                    # Action buttons
                    btn_cols = st.columns([1, 1.3, 1, 1, 0.7])
                    with btn_cols[0]:
                        if st.button("➕ Pipeline", key=f"pipe_{job_id}"):
                            update_job_status(job_id, "pipeline")
                            st.toast(f"Added {company} to pipeline")
                    with btn_cols[1]:
                        ro_sent = bool(reached_out_at)
                        ro_label = "📧 Sent ✓" if ro_sent else "📧 Reached out"
                        if st.button(ro_label, key=f"ro_{job_id}", disabled=ro_sent):
                            mark_reached_out(job_id, bd)
                            st.toast("Marked as reached out. Follow-up reminder in 3 days.")
                    with btn_cols[2]:
                        if st.button("✅ Applied", key=f"applied_{job_id}"):
                            mark_applied(job_id, bd)
                            st.toast(f"Marked {company} as applied")
                    with btn_cols[3]:
                        with st.popover("❌ Skip"):
                            skip_reason = st.text_input(
                                "Reason (optional)",
                                key=f"sr_{job_id}",
                                placeholder="e.g. too infra-heavy, not PM role",
                            )
                            if st.button("Confirm skip", key=f"skip_ok_{job_id}"):
                                bd2 = job.get("score_breakdown") or {}
                                if skip_reason.strip():
                                    bd2["skip_reason"] = skip_reason.strip()
                                    supabase.table("jobs").update(
                                        {"score_breakdown": bd2}
                                    ).eq("id", job_id).execute()
                                update_job_status(job_id, "skip")
                                st.toast("Skipped")
                    with btn_cols[4]:
                        if job_url:
                            st.link_button("↗ View", job_url)

                    st.markdown("---")


# ===========================================================================
# PIPELINE
# ===========================================================================

elif nav == "📋 Pipeline":
    pipeline_jobs = [j for j in jobs if j.get("status") == "pipeline"]

    if not pipeline_jobs:
        st.info("No jobs in pipeline yet. Go to Open Roles and hit '➕ Pipeline'.")
    else:
        needs_prep = sum(1 for j in pipeline_jobs if not j.get("prep_materials"))
        st.caption(f"{len(pipeline_jobs)} jobs in pipeline · {needs_prep} need prep materials.")

        if needs_prep > 0:
            if st.button("⚡ Generate prep for all", type="primary"):
                with st.spinner("Writing outreach messages..."):
                    import subprocess, sys
                    subprocess.run(
                        [sys.executable, "agent/prep.py"],
                        cwd=os.path.dirname(os.path.abspath(__file__)),
                    )
                st.cache_data.clear()
                st.toast("Done. Hit Refresh to see messages.")

        st.divider()

        for job in pipeline_jobs:
            bd   = job.get("score_breakdown") or {}
            score = job.get("attractiveness_score")
            prep = job.get("prep_materials") or {}
            reached_out_at = bd.get("reached_out_at")

            follow_up_flag = ""
            if reached_out_at:
                try:
                    ro_date = datetime.fromisoformat(reached_out_at.replace("Z", "+00:00"))
                    days_since = (datetime.now(timezone.utc) - ro_date).days
                    if days_since >= 3:
                        follow_up_flag = f" · ⏰ Follow up ({days_since}d)"
                except Exception:
                    pass

            score_str  = f"{score}/100" if score else "unscored"
            has_prep   = bool(prep.get("outreach_message"))
            badge      = "📧 " if reached_out_at else ("✉️ " if has_prep else "⏳ ")
            label = f"{badge}**{job['company_name']}** — {job['title']} · `{score_str}`{follow_up_flag}"

            with st.expander(label, expanded=False):
                act_cols = st.columns([1.4, 1.4, 1, 1])
                with act_cols[0]:
                    ro_sent = bool(reached_out_at)
                    ro_label = "📧 Sent ✓" if ro_sent else "📧 Reached out"
                    if st.button(ro_label, key=f"ro2_{job['id']}", disabled=ro_sent):
                        mark_reached_out(job["id"], bd)
                        st.toast("Marked — will remind you to follow up in 3 days")
                with act_cols[1]:
                    if st.button("✅ Applied", key=f"app2_{job['id']}"):
                        mark_applied(job["id"], bd)
                        st.toast(f"Marked {job['company_name']} as applied")
                with act_cols[2]:
                    if job.get("url"):
                        st.link_button("↗ View job", job["url"])

                st.markdown("#### Outreach Message")
                st.caption("Find the right person on LinkedIn. Swap [Name] and send.")

                if has_prep:
                    outreach = prep.get("outreach_message", "")
                    st.text_area(
                        "", value=outreach, height=200,
                        key=f"out_{job['id']}", label_visibility="collapsed",
                    )
                    st.caption(f"{len(outreach)} chars · generated {prep.get('generated_at','')[:10]}")
                    if st.button("↻ Regenerate", key=f"regen_{job['id']}"):
                        with st.spinner("Regenerating..."):
                            from agent.prep import generate_outreach, save_prep
                            new_msg = generate_outreach(job)
                            save_prep(job["id"], new_msg)
                            st.session_state[f"regen_msg_{job['id']}"] = new_msg
                        st.cache_data.clear()
                    rk = f"regen_msg_{job['id']}"
                    if rk in st.session_state:
                        st.text_area(
                            "", value=st.session_state[rk], height=200,
                            key=f"out_new_{job['id']}", label_visibility="collapsed",
                        )
                else:
                    st.caption("No outreach message yet.")
                    if st.button("⚡ Generate now", key=f"prep_{job['id']}"):
                        with st.spinner("Writing outreach message..."):
                            from agent.prep import generate_outreach, save_prep
                            msg = generate_outreach(job)
                            save_prep(job["id"], msg)
                            st.session_state[f"gen_msg_{job['id']}"] = msg
                        st.cache_data.clear()
                    gk = f"gen_msg_{job['id']}"
                    if gk in st.session_state:
                        st.text_area(
                            "", value=st.session_state[gk], height=200,
                            key=f"out_gen_{job['id']}", label_visibility="collapsed",
                        )


# ===========================================================================
# REACHED OUT
# ===========================================================================

elif nav == "📧 Reached Out":
    reached_out_jobs = [
        j for j in jobs if (j.get("score_breakdown") or {}).get("reached_out_at")
    ]
    reached_out_radar = [r for r in radar_all if r.get("radar_status") == "reached_out"]

    total_ro = len(reached_out_jobs) + len(reached_out_radar)

    if not reached_out_jobs and not reached_out_radar:
        st.info(
            "No outreach tracked yet. Hit '📧 Reached out' on any job "
            "in Open Roles or Pipeline, or on a company in On Radar."
        )
    else:
        st.caption(f"{total_ro} companies reached out to.")

        rh1, rh2, rh3, rh4, rh5 = st.columns([2, 2.5, 1.5, 1, 3.5])
        rh1.markdown("**Company**")
        rh2.markdown("**Role**")
        rh3.markdown("**Reached Out**")
        rh4.markdown("**Action**")
        rh5.markdown("**Notes**")
        st.markdown("<hr style='margin:4px 0 8px 0; border-color:#e5e7eb'>", unsafe_allow_html=True)

        for job in reached_out_jobs:
            bd             = job.get("score_breakdown") or {}
            reached_out_at = bd.get("reached_out_at", "")
            notes          = bd.get("reached_out_notes", "")

            ro_date_str = ""
            days_since = None
            try:
                ro_dt = datetime.fromisoformat(reached_out_at.replace("Z", "+00:00"))
                days_since = (datetime.now(timezone.utc) - ro_dt).days
                ro_date_str = fmt_date_mdy(reached_out_at)
            except Exception:
                pass

            nudge = f" ⏰ {days_since}d" if (days_since is not None and days_since >= 3) else ""

            rc1, rc2, rc3, rc4, rc5 = st.columns([2, 2.5, 1.5, 1, 3.5])
            with rc1:
                st.markdown(f"**{job['company_name']}**")
            with rc2:
                url = job.get("url", "")
                st.markdown(f"[{job['title']}]({url})" if url else job["title"])
            with rc3:
                st.markdown(f"{ro_date_str}{nudge}")
            with rc4:
                if st.button("✅", key=f"ro_app_{job['id']}", help="Mark as applied"):
                    mark_applied(job["id"], bd)
                    st.toast(f"Marked {job['company_name']} as applied")
            with rc5:
                ro_notes_key = f"ro_notes_{job['id']}"
                def _save_ro_notes(jid=job["id"], snap=dict(bd)):
                    val = st.session_state.get(f"ro_notes_{jid}", "")
                    snap["reached_out_notes"] = val
                    supabase.table("jobs").update({"score_breakdown": snap}).eq("id", jid).execute()
                    st.cache_data.clear()
                st.text_input("", value=notes, key=ro_notes_key,
                              label_visibility="collapsed",
                              placeholder="e.g. Recruiter replied, follow up Fri",
                              on_change=_save_ro_notes)
            st.markdown("<hr style='margin:4px 0 8px 0; border-color:#e5e7eb'>", unsafe_allow_html=True)

        for r in reached_out_radar:
            rc1, rc2, rc3, rc4, rc5 = st.columns([2, 2.5, 1.5, 1, 3.5])
            with rc1:
                st.markdown(f"**{r['name']}**")
            with rc2:
                st.markdown("<span style='color:#9ca3af'>N/A</span>", unsafe_allow_html=True)
            with rc3:
                st.markdown("")
            with rc4:
                if st.button("✅", key=f"rr_app_{r['id']}", help="Mark as applied"):
                    update_radar_status(r["id"], "applied", r["name"])
                    st.toast(f"Marked {r['name']} as applied")
            with rc5:
                rr_notes_key = f"rr_notes_{r['id']}"
                def _save_rr_notes(rid=r["id"], rname=r["name"]):
                    val = st.session_state.get(f"rr_notes_{rid}", "")
                    supabase.table("companies").update({"radar_notes": val}).eq("id", rid).execute()
                    st.cache_data.clear()
                st.text_input("", value=r.get("radar_notes") or "", key=rr_notes_key,
                              label_visibility="collapsed",
                              placeholder="e.g. Recruiter replied, follow up Fri",
                              on_change=_save_rr_notes)
            st.markdown("<hr style='margin:4px 0 8px 0; border-color:#e5e7eb'>", unsafe_allow_html=True)


# ===========================================================================
# APPLIED
# ===========================================================================

elif nav == "✅ Applied":
    applied_jobs = [j for j in jobs if j.get("status") == "applied"]

    if not applied_jobs:
        st.info("No applications tracked yet.")
    else:
        st.caption(f"{len(applied_jobs)} applications tracked.")
        st.divider()

        # Group by company
        by_co = defaultdict(list)
        for j in applied_jobs:
            by_co[j["company_name"]].append(j)
        # Sort companies by most recent application
        def latest_applied(jlist):
            dates = [(j.get("score_breakdown") or {}).get("applied_at", "") for j in jlist]
            return max(d for d in dates if d) if any(dates) else ""
        sorted_cos = sorted(by_co.items(), key=lambda x: latest_applied(x[1]), reverse=True)

        h1, h2, h3, h4, h5 = st.columns([1.8, 2.2, 1.4, 1.2, 4])
        h1.markdown("**Company**"); h2.markdown("**Role**"); h3.markdown("**Applied On**")
        h4.markdown("**Follow-up**"); h5.markdown("**Notes**")
        st.markdown("---")

        for company, company_jobs in sorted_cos:
            for idx, job in enumerate(company_jobs):
                bd          = job.get("score_breakdown") or {}
                applied_at  = bd.get("applied_at", "")
                apply_notes = bd.get("apply_notes", "")
                followup_at = bd.get("apply_followup_at", "")
                url         = job.get("url", "")

                followup_display = ""
                followup_urgent  = False
                if followup_at:
                    try:
                        fu_dt = datetime.fromisoformat(followup_at.replace("Z", "+00:00"))
                        days_left = (fu_dt - datetime.now(timezone.utc)).days
                        followup_display = "⏰ Due now" if days_left <= 0 else f"In {days_left}d"
                        followup_urgent  = days_left <= 0
                    except Exception:
                        pass

                c1, c2, c3, c4, c5 = st.columns([1.8, 2.2, 1.4, 1.2, 4])
                with c1:
                    # Show company name only on first role, blank for subsequent
                    st.markdown(f"**{company}**" if idx == 0 else "")
                with c2:
                    st.markdown(f"[{job['title']}]({url})" if url else job["title"])
                with c3:
                    date_key = f"appdate_{job['id']}"
                    def _save_date(jid=job["id"], snap=dict(bd)):
                        val = st.session_state.get(f"appdate_{jid}", "")
                        snap["applied_at"] = val
                        supabase.table("jobs").update({"score_breakdown": snap}).eq("id", jid).execute()
                        st.cache_data.clear()
                    st.text_input("", value=fmt_date_mdy(applied_at), key=date_key,
                                  label_visibility="collapsed", placeholder="MM/DD/YY", on_change=_save_date)
                with c4:
                    fu_key = f"fu_cb_{job['id']}"
                    def _toggle_fu(jid=job["id"], snap=dict(bd)):
                        checked = st.session_state.get(f"fu_cb_{jid}", False)
                        snap["apply_followup_at"] = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat() if checked else None
                        supabase.table("jobs").update({"score_breakdown": snap}).eq("id", jid).execute()
                        st.cache_data.clear()
                    st.checkbox("Follow up", value=bool(followup_at), key=fu_key, on_change=_toggle_fu)
                    if followup_display:
                        st.caption(followup_display)
                with c5:
                    notes_key = f"anotes_{job['id']}"
                    def _save_notes(jid=job["id"], snap=dict(bd)):
                        val = st.session_state.get(f"anotes_{jid}", "")
                        snap["apply_notes"] = val
                        supabase.table("jobs").update({"score_breakdown": snap}).eq("id", jid).execute()
                        st.cache_data.clear()
                    st.text_input("", value=apply_notes, key=notes_key,
                                  label_visibility="collapsed", placeholder="Add notes...", on_change=_save_notes)

            st.markdown("---")




# ===========================================================================
# ON RADAR
# ===========================================================================

elif nav == "🔭 On Radar":
    st.caption("Companies worth tracking — sourced from funding news, target lists, and RSS scans.")

    radar_items = radar_all

    if not radar_items:
        st.info("Nothing on radar yet. Run a funding scan in Sources to discover companies.")
    else:
        fcol1, fcol2, fcol3, fcol4 = st.columns(4)
        with fcol1:
            status_filter = st.selectbox(
                "Status",
                ["Not yet contacted", "Has draft", "All", "Reached out", "Applied"],
                label_visibility="collapsed",
            )
        with fcol2:
            all_sectors = sorted(
                set(r.get("sector") for r in radar_items
                    if r.get("sector") and r.get("sector") != "Cybersecurity AI")
            )
            sector_filter_r = st.selectbox(
                "Sector", ["All sectors"] + all_sectors, label_visibility="collapsed"
            )
        with fcol3:
            all_stages = sorted(set(r.get("stage", "") for r in radar_items if r.get("stage")))
            stage_filter_r = st.selectbox(
                "Stage", ["All stages"] + all_stages, label_visibility="collapsed"
            )
        with fcol4:
            score_tier_r = st.selectbox(
                "Score",
                ["All scores", "High (80+)", "Medium (60-79)", "Low (<60)"],
                label_visibility="collapsed",
                key="score_filter_radar",
            )

        _hidden_ids = st.session_state.get("hidden_company_ids", set())
        _hidden_names = st.session_state.get("hidden_company_names", set())
        # Companies with active open roles belong in Open Roles, not On Radar
        _companies_with_open_roles = set(
            j["company_name"] for j in jobs
            if j.get("status") in ("prep_ready", "borderline", "new")
        )
        filtered = [
            r for r in radar_items
            if r.get("feedback") != "not_for_me"
            and r.get("sector") != "Cybersecurity AI"
            and r.get("id") not in _hidden_ids
            and r.get("name") not in _hidden_names
            and r.get("name") not in _companies_with_open_roles
        ]
        if status_filter == "Not yet contacted":
            filtered = [r for r in filtered if r.get("radar_status") not in ("reached_out", "applied")]
        elif status_filter == "Has draft":
            filtered = [r for r in filtered if (r.get("relationship_message") or "").strip() and r.get("radar_status") not in ("reached_out", "applied")]
        elif status_filter == "Reached out":
            filtered = [r for r in filtered if r.get("radar_status") == "reached_out"]
        elif status_filter == "Applied":
            filtered = [r for r in filtered if r.get("radar_status") == "applied"]
        if sector_filter_r != "All sectors":
            filtered = [r for r in filtered if r.get("sector") == sector_filter_r]
        if stage_filter_r != "All stages":
            filtered = [r for r in filtered if r.get("stage") == stage_filter_r]
        if score_tier_r == "High (80+)":
            filtered = [r for r in filtered if (r.get("attention_score") or 0) >= 80]
        elif score_tier_r == "Medium (60-79)":
            filtered = [r for r in filtered if 60 <= (r.get("attention_score") or 0) < 80]
        elif score_tier_r == "Low (<60)":
            filtered = [r for r in filtered if 0 < (r.get("attention_score") or 0) < 60]

        filtered = sorted(
            filtered,
            key=lambda r: (
                (r.get("created_at") or "") >= _wk_start.isoformat(),
                r.get("attention_score") or 0,
            ),
            reverse=True,
        )

        st.caption(f"{len(filtered)} companies")

        for item in filtered:
            company    = item["name"]
            what       = item.get("what_they_do", "")
            funding    = item.get("funding_info", "")
            status     = item.get("radar_status", "watching")
            source_url = item.get("source_url", "")
            msg        = item.get("relationship_message", "")
            score      = item.get("attention_score")
            sector     = item.get("sector", "")
            stage      = item.get("stage", "")
            investors  = item.get("investors", "")

            status_emoji = {
                "reached_out": "✉️ ", "in_conversation": "💬 ", "applied": "✅ "
            }.get(status or "", "")

            is_new_radar = (item.get("created_at") or "") >= _wk_start.isoformat()
            label = f"{status_emoji}**{company}**"
            if is_new_radar:
                label += " · 🆕"
            if sector:
                label += f" · {sector}"
            if stage:
                label += f" · {stage}"
            if score is not None:
                label += f" · `{score}/100`"

            with st.expander(label):
                meta_parts = []
                if funding:
                    meta_parts.append(funding)
                if investors:
                    meta_parts.append(f"backed by {investors}")
                if meta_parts:
                    st.caption(" · ".join(meta_parts))
                if what:
                    st.markdown(f"*{what}*")

                bcols = st.columns([1.3, 1, 1.2, 0.5])
                with bcols[0]:
                    ro_done = (status == "reached_out")
                    if st.button(
                        "✉️ Sent ✓" if ro_done else "✉️ Reached out",
                        key=f"ro_r_{item['id']}",
                        disabled=ro_done,
                    ):
                        update_radar_status(item["id"], "reached_out", company)
                        st.toast(f"Marked {company} as reached out")
                with bcols[1]:
                    if st.button("✅ Applied", key=f"ap_r_{item['id']}"):
                        update_radar_status(item["id"], "applied", company)
                        st.toast(f"Marked {company} as applied")
                with bcols[2]:
                    with st.popover("👎 Not for me"):
                        st.markdown(f"**Why is {company} not a fit?**")
                        nfm_reason = st.selectbox(
                            "Reason",
                            ["Wrong sector", "Wrong stage", "Not AI enough", "Too early / no product yet", "Too late / too big", "Wrong geography", "Other"],
                            key=f"nfm_reason_{item['id']}",
                            label_visibility="collapsed",
                        )
                        if st.button("Confirm", key=f"nfm_confirm_{item['id']}", type="primary"):
                            supabase.table("companies").update({
                                "feedback": "not_for_me",
                                "feedback_reason": nfm_reason,
                            }).eq("id", item["id"]).execute()
                            supabase.table("jobs").update({"status": "skip"}).eq("company_name", company).in_(
                                "status", ["new", "borderline", "prep_ready"]
                            ).execute()
                            st.session_state.setdefault("hidden_company_ids", set()).add(item["id"])
                            st.session_state.setdefault("hidden_job_ids", set()).update(
                                j["id"] for j in jobs if j.get("company_name") == company
                            )
                            st.toast(f"Got it — {company} won't appear again")
                with bcols[3]:
                    if source_url:
                        st.link_button("↗", source_url)

                st.markdown("**Outreach draft**")
                if msg:
                    def _save_radar_msg(iid=item["id"]):
                        val = st.session_state.get(f"rmsg_r_{iid}", "")
                        supabase.table("companies").update({"relationship_message": val}).eq("id", iid).execute()
                        st.cache_data.clear()
                    st.text_area(
                        "", value=msg, height=150,
                        key=f"rmsg_r_{item['id']}", label_visibility="collapsed",
                        on_change=_save_radar_msg,
                    )
                else:
                    if st.button("⚡ Generate draft", key=f"gen_draft_{item['id']}"):
                        with st.spinner("Writing outreach message..."):
                            import anthropic as _anthropic
                            _cl = _anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
                            _gen = _cl.messages.create(
                                model="claude-sonnet-4-6",
                                max_tokens=250,
                                messages=[{"role": "user", "content": f"""Write a short LinkedIn message from Rachita Kumar to someone at {company}.

What {company} does: {what}

Rachita's background: Senior PM at PayPal (shipped App Switch, PayPal's first mobile checkout, +450bps CVR, $50M TPV). Founding PM at TruthSeek (voice AI startup, designed LLM interview agent, ran eval pipelines, delivered live CPG consumer research). Finance background (PE/IB India). Builder: ships solo AI products.

STYLE — match these real messages exactly:
"Hi Dhwani! As the founding PM of a voice AI startup, I ran evals on conversation quality (follow-up questions, staying on topic, goal coverage). But standard benchmarks measure one response at a time. For Cartesia's SSMs, how do you do evals for a 30-minute call or when a user talks over the agent?"

"Hi Naman. I've enjoyed using Littlebird, I'm no longer copy pasting screenshots across screens! One little feedback: the 'update ready to install' prompt keeps interrupting the experience and asks for admin password, which feels jarring for a tool that's supposed to run quietly in the background."

"Hi Michael, I'm a PM at PayPal and was the founding team PM at a voice AI user research startup (TruthSeek). While building TruthSeek, I realized that getting enterprises to trust AI-led workflows in regulated industries isn't a sales problem, it's a product design problem."

Rules:
- Start with "Hi [Name]." (first name only, keep the period)
- Lead with a specific observation about their product or domain, OR a concrete parallel from her work
- ONE experience with real detail, not a list
- End with: "would love to connect" or "would love to chat"
- NEVER mention applying for a job or looking for a role
- NEVER use: genuinely, really (as filler), amazing, passionate, thrilled, incredible, love what you're building
- NEVER use em dashes or hyphens as dashes
- 60-120 words, conversational

Return ONLY the message."""}]
                            ).content[0].text.strip()
                            supabase.table("companies").update({"relationship_message": _gen}).eq("id", item["id"]).execute()
                        st.toast(f"Draft generated for {company}")
                        st.cache_data.clear()
                        st.rerun()
