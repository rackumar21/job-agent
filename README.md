# Job Search Agent

An autonomous AI-powered job search system that discovers, scores, and tracks PM roles across 100+ companies — replacing 10+ hours/week of manual job hunting with a single dashboard.

## What It Does

**Discovers roles automatically.** Polls Ashby, Greenhouse, Lever, and Workable job boards every Monday. Scans TechCrunch funding news, LinkedIn hiring posts, and newsletters to surface new companies before they hit job boards.

**Scores every role with AI.** A two-stage scoring pipeline: a keyword pre-filter drops obvious non-fits (free), then Claude Sonnet scores remaining roles on 5 weighted dimensions — role fit, company fit, end-user layer, growth signal, and location. The system learns from my actions: applied roles become positive benchmarks, skipped roles become negative signals.

**Tailors resumes per job.** ATS analysis compares my resume against each job description — identifies keyword gaps, generates bullet-point rewrites, and lets me copy tailored versions directly into my resume. Rewrites are length-constrained to preserve single-page formatting.

**Routes and tracks everything.** Roles scoring 75+ go to Open Roles. Companies with no open PM roles go to On Radar with a drafted outreach message in my voice. Tracks application status, outreach, and follow-ups across all stages. Nothing is sent automatically — the agent drafts, I review, I send.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        React Dashboard                       │
│  Open Roles · On Radar · Pipeline · Outreach · Applied · Resume │
└──────────────────────────┬──────────────────────────────────┘
                           │ Supabase real-time
┌──────────────────────────┴──────────────────────────────────┐
│                      FastAPI Backend                         │
│  ATS analysis · Pipeline trigger · Outreach generation       │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│                     Agent Layer (Python)                      │
│                                                              │
│  discover.py ──── Polls 4 ATS platforms (Ashby, Greenhouse,  │
│                   Lever, Workable) with parallel slug discovery│
│                                                              │
│  score.py ─────── Two-stage scoring: keyword filter (free)   │
│                   + Claude Sonnet (5 dimensions, cached)      │
│                                                              │
│  ats.py ───────── Resume vs JD analysis with Claude Haiku    │
│                   (prompt-cached for 90% cost reduction)      │
│                                                              │
│  prep.py ──────── Outreach message generation in my voice     │
│                                                              │
│  discover_from_rss.py ── RSS scan (TechCrunch, Next Play)    │
│                          + company scoring + sector tagging   │
│                                                              │
│  pipeline.py ──── Orchestrates: discover → score → route      │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│                    Supabase (PostgreSQL)                      │
│  companies · jobs · applications · outreach · signals · logs │
└─────────────────────────────────────────────────────────────┘
```

## What Makes It Agentic

This isn't a script that runs a search query. It makes decisions:

- **Behavioral learning.** The scoring model adapts. When I apply to a job, similar roles get boosted. When I skip one and say "too infra-heavy," future infra roles get penalized. The agent builds a preference model from my actions.
- **Multi-source discovery.** Doesn't just poll job boards. Scans funding news to find companies *before* they post roles. Monitors newsletters and LinkedIn posts. Tries multiple slug patterns to find ATS boards (company-name, company-name-ai, companyai).
- **Autonomous routing.** Each discovered role gets classified, scored, and routed without intervention. High-fit roles appear in Open Roles. Companies without PM openings get outreach drafts. Everything lands in the right bucket.
- **Cost-optimized AI.** Resume is cached in Claude's system prompt (90% cost reduction on repeated ATS analysis). Keyword pre-filter eliminates ~70% of roles before they hit Claude. Parallel processing with 16-worker thread pools.

## Tech Stack

| Layer | Stack |
|-------|-------|
| Frontend | React 18, Tailwind CSS, Vite |
| Backend | FastAPI, Python 3.9 |
| Database | Supabase (PostgreSQL + real-time) |
| AI | Claude Sonnet (scoring), Claude Haiku (ATS analysis), prompt caching |
| Scheduling | APScheduler (daily discovery, RSS scans, weekly briefs) |
| Deployment | Render (single service: FastAPI serves React dist/) |

## Dashboard

**7 tabs:**
- **Open Roles** — Scored jobs with filters (role type, sector, stage, score band, week)
- **On Radar** — Companies with drafted outreach, no open PM roles
- **Pipeline** — Jobs queued for application with outreach messages
- **Outreach** — Sent messages with follow-up tracking
- **Applied** — Submitted applications with status
- **Sources** — Add companies/URLs, trigger funding scans
- **Resume** — ATS analysis + resume tailoring per job

## Setup

```bash
# Clone and install
git clone https://github.com/rackumar21/job-agent.git
cd job-agent
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Frontend
cd frontend && npm install && cd ..

# Configure (create .env with your keys)
cp .env.example .env
# Add: SUPABASE_URL, SUPABASE_KEY, ANTHROPIC_API_KEY

# Add your resume
# Place your resume at profile/resume.md and profile/resume.docx

# Run
python3 -m uvicorn api.main:app --port 8001  # Backend
cd frontend && npm run dev                     # Frontend (localhost:3001)
```

## Cost

Running this agent costs ~$3-5/month in Claude API calls. Prompt caching reduces ATS analysis cost by 90%. The keyword pre-filter eliminates most roles before they hit Claude.

## License

MIT
