# Job Agent — CLAUDE.md

This file is read automatically by Claude Code at the start of every session in this repo.

---

## What this project is

A personal AI-powered job search agent. It monitors 100+ target companies across Ashby/Greenhouse/Lever/Workable, scores jobs against Rachita's profile using Claude, tracks the pipeline, and drafts outreach messages. The dashboard is a React app backed by FastAPI + Supabase.

**Repo:** github.com/rackumar21/job-agent (public)
**Live:** https://job-agent-2h5u.onrender.com (Render free tier — 50s cold start after inactivity)
**Local:** `bash start-dashboard.sh` → API on :8001, Vite frontend on :3001

---

## Who Rachita is

PM with 8+ years (finance + product). Currently at PayPal (checkout team). Targeting PM roles at AI-native companies (50-300 people, post-PMF). This project is both a job search tool AND a portfolio piece — "I built an agent for myself."

---

## Stack

- **Frontend:** React 18 + Vite + Tailwind CSS (`frontend/src/`)
- **Backend:** FastAPI (`api/main.py`)
- **Database:** Supabase (Postgres) — jobs, companies, pipeline, outreach
- **AI:** Claude API — Sonnet for scoring/outreach, Haiku for extraction/ATS
- **Deployment:** Render (auto-deploys on push to main)
- **Scheduling:** Claude Code scheduled agent (Monday 9am) + Python scheduler.py

## How to run locally

```bash
bash start-dashboard.sh
# API: localhost:8001
# Frontend: localhost:3001
```

**Critical:** Always use venv Python, not system Python.
```bash
/Users/rachita/Work/job-agent/venv/bin/python3 -m uvicorn api.main:app --port 8001
```

---

## Project structure

```
api/main.py         — FastAPI endpoints
agent/
  discover.py       — Ashby + Greenhouse polling for tracked companies
  pipeline.py       — orchestrator: score → find ATS slug → poll jobs → route
  score.py          — two-stage scoring (keyword pre-filter + Claude 5 dimensions)
  discover_from_rss.py  — RSS scan (TechCrunch, Next Play, Open to Work)
  discover_from_post.py — extract companies from pasted text/URL
  prep.py           — generate outreach messages
  ats.py            — resume vs JD analysis
frontend/src/
  App.jsx           — nav, header, weekly stats bar
  pages/            — OpenRoles, OnRadar, Pipeline, Outreach, Applied, Sources
  components/       — JobCard, ScoreBadge
scheduler.py        — Python APScheduler (Mon/Thu/Sun polling, Monday brief)
dashboard.py        — old Streamlit dashboard (deprecated, kept for reference)
```

---

## Key conventions

- Every company MUST have `what_they_do`, `sector`, `stage` — this is a data quality rule
- Every job MUST have `company_id` linked
- Background jobs poll via `/api/pipeline/status/{id}` every 3 seconds
- `rescore=True` on manual pipeline runs to re-score with latest rubric
- Resume file: `/Users/rachita/Downloads/RachitaKumar_resume.pdf`

---

## Scoring system

**Job attractiveness score (0-100):**
- 75+ = prep_ready (show in Open Roles)
- 55-74 = borderline (show in Open Roles)
- <55 = skip

**Company attention score (0-100):**
- 40+ = On Radar
- Scores radar companies even before they post a role

**5 scoring dimensions:** role fit (30), company fit (25), end-user layer (20), growth signal (15), location fit (10)

---

## Deployment (Render)

- Auto-deploys on push to main
- Build: `cd frontend && npm install && npm run build && cd .. && pip install -r requirements.txt`
- Start: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
- Env vars: `SUPABASE_URL`, `SUPABASE_KEY`, `ANTHROPIC_API_KEY`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`
- If latest push not picked up: Manual Deploy → Clear build cache and deploy

---

## Scheduled Claude Code agent (Monday 9am)

Set up in Claude Code desktop. Runs 4 steps in sequence:
1. Job board polling (Ashby, Greenhouse, LinkedIn, WATS) + scoring
2. RSS funding scan
3. LinkedIn curator monitor
4. Monday morning brief → `logs/morning_brief.log`

Fires automatically as long as Claude Code is running. Check under Scheduled in the sidebar.

---

## Interview story (for job applications)

Lead with product decisions, not technical fixes:
- What to automate vs. keep human (agent drafts, Rachita approves)
- Attention score for companies before they post roles (non-obvious insight)
- Curation over broad search (LinkedIn broad search produced garbage; switched to trusted curator lists)

Then the technical challenges as proof of depth (JSON markdown stripping, Greenhouse deduplication, Cloudflare blocks, etc.)
