# Job Agent — Decision Log

## 1. React + Vite + Tailwind over Streamlit
**Chose**: React frontend with Vite bundler and Tailwind CSS
**Rejected**: Streamlit (original dashboard)
**Why**: Streamlit is great for prototyping but limited for real product UX. Cards, filters, expandable sections, action buttons all needed custom UI. React gives full control over layout and interactions. Tailwind keeps styling fast without a design system.

## 2. Supabase JS client direct from frontend
**Chose**: Frontend reads/writes Supabase directly (anon key + RLS)
**Rejected**: All reads through FastAPI
**Why**: Faster development, real-time updates, fewer API endpoints to maintain. FastAPI only used for Python-heavy ops (Claude calls, pipeline runs). Anon key is safe with Row Level Security.

## 3. Background pipeline processing with polling
**Chose**: API returns immediately, runs pipeline in background thread, frontend polls every 3s
**Rejected**: Synchronous HTTP request that blocks until done
**Why**: Processing 24 companies takes 2-5 minutes (Claude API calls + HTTP slug discovery). Blocking the request times out and hangs the UI. Background + polling keeps the page responsive.

## 4. Two-stage job scoring (keyword pre-filter + Claude)
**Chose**: Free keyword regex filter first, then Claude Sonnet for survivors
**Rejected**: Claude scores every job
**Why**: ~30% of jobs are obvious non-fits (SWE, data engineer, clinical). Filtering them before Claude saves $0.03/job. At 50-100 jobs/week, this saves $150-500/month.

## 5. Four ATS platforms + web search fallback
**Chose**: Ashby + Greenhouse + Lever + Workable + Claude Haiku web search
**Rejected**: Ashby + Greenhouse only
**Why**: Many startups use Lever or Workable. Without them, pipeline couldn't find jobs for ~40% of companies. Web search catches the rest (companies using custom careers pages).

## 6. rescore=True for manual runs, score gate stays
**Chose**: Manual pipeline runs always re-score companies with latest rubric, but still skip companies below score 40
**Rejected**: (a) force=True that bypasses score gate entirely, (b) never re-score
**Why**: Rubric evolves (e.g., added B2B SaaS). Old scores become stale. But the score gate must stay to avoid wasting Claude calls on irrelevant companies. Low-scoring companies still go to Radar with details.

## 7. Render for deployment
**Chose**: Render (free tier, auto-deploy from GitHub)
**Rejected**: Railway (GitHub app integration didn't work), Vercel (can't host Python backend)
**Why**: Render detected Python + Node automatically, supports custom build/start commands, free tier sufficient for demo link. Cold start (~50s) acceptable for interview demo.

## 8. Serve React build from FastAPI (single deployment)
**Chose**: FastAPI serves React dist/ as static files, one URL for everything
**Rejected**: Separate frontend (Vercel) + backend (Render) deployments
**Why**: Simpler. One URL, one deployment, no CORS issues. Frontend fetch('/api/...') goes to same origin.

## 9. Parallel slug discovery (16 workers)
**Chose**: ThreadPoolExecutor with 16 workers, all slug patterns across all 4 ATS checked simultaneously
**Rejected**: Sequential slug checking
**Why**: Sequential = 4 slugs × 4 platforms × 3s timeout = 48s per company. Parallel = ~3s per company. For 24 companies, saves ~18 minutes.

## 10. No auto-send, no auto-apply
**Chose**: Agent drafts everything, Rachita reviews and executes manually
**Rejected**: Auto-send LinkedIn messages, auto-apply to jobs
**Why**: Quality over volume. Bad outreach damages reputation. The agent's job is to surface the right opportunities and draft the right words. The human decides what gets sent.
