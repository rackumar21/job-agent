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

## 11. Copy-paste resume tailoring over .docx download
**Chose**: Show rewrite suggestions with Copy buttons; user pastes into Google Doc
**Rejected**: Generate modified .docx with python-docx text replacement
**Why**: python-docx corrupts complex formatting (blue header boxes expand, spacing breaks). The resume lives in Google Docs, and preserving its exact formatting matters more than automation. Copy-paste is reliable and keeps user in control.

## 12. Programmatic length filter on ATS rewrites
**Chose**: Backend drops any rewrite suggestion longer than 110% of original character count
**Rejected**: Relying only on prompt instructions to constrain length
**Why**: LLMs don't reliably count characters. Even with "MUST be same length or shorter" in the prompt, Haiku consistently generated longer rewrites. Hard code filter is the only reliable guard. 110% threshold (not 100%) avoids dropping good suggestions over a few extra characters.

## 13. Separate Resume tab (not inline on job cards)
**Chose**: Dedicated /resume tab with URL input + ATS report + tailoring UI
**Rejected**: Inline ATS analysis on each job card in Open Roles
**Why**: Resume tailoring needs space (original vs rewrite side by side, editable textareas, approve flow). Job cards are compact. Also needed to support ad-hoc URLs not in the tracked job database. Job cards get an "ATS" button that links to /resume?jobId=X.

## 14. Remove sensitive files from git, keep on disk
**Chose**: git rm --cached for profile/resume.md, about.md, preferences.json, frontend/.env.local; added to .gitignore
**Rejected**: Deleting files entirely, or using git filter-repo to purge history
**Why**: Files are needed locally (ATS reads resume.md, frontend needs .env.local). Purging git history is destructive and not urgent since the repo was already public. The immediate fix is stopping future commits from including them.

## 15. Truthseek landing page: clean hero over photo hero
**Chose**: White background with centered headline, subtitle, and dual CTAs (Get Started Free + Try Live Research Call)
**Rejected**: Full-bleed background photo with overlaid text (original design)
**Why**: Competitor analysis (Genway, others) showed the industry standard is clean hero + product demo preview. Photo hero looked impressive but buried the CTAs and didn't communicate the product. Clean layout with clear CTAs is better for conversion.

## 16. Truthseek: hardcode sign-up URL instead of env var
**Chose**: Hardcode `https://app.truthseek.in/try-now` directly in JSX
**Rejected**: `process.env.NEXT_PUBLIC_WEB_URL` template literal
**Why**: No `.env.local` file existed in the repo, so the env var resolved to empty string, making all sign-up buttons link to just `/try-now` (broken). Hardcoding is more reliable for a URL that doesn't change between environments.

## 17. Truthseek: branch-based PRs over direct pushes
**Chose**: Push changes on `landing-page-redesign` branch, merge via PR, then merge dev->main via PR
**Rejected**: Direct push to dev/main
**Why**: Rachita needs the ability to revert. PRs give a one-click "Revert" button on GitHub. Also creates a clean audit trail of what changed and why.
