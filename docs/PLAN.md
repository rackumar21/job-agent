# Job Agent — Plan

## Completed (April 1, 2026)
- [x] React + Vite + Tailwind frontend replacing Streamlit
- [x] 6-tab layout: Open Roles, On Radar, Pipeline, Outreach, Applied, Sources
- [x] JobCard component with score badges, actions, expandable details
- [x] "How this agent works" collapsible with 4-card layout
- [x] Sources page: extract from post, funding scan, add anything
- [x] Background pipeline processing (no HTTP timeouts)
- [x] Parallel company processing (4 workers) and slug discovery (16 workers)
- [x] Lever + Workable ATS support
- [x] Web search fallback for companies with no ATS
- [x] rescore=True for manual pipeline runs
- [x] Auto-discover ATS slugs for new companies
- [x] Render deployment (https://job-agent-2h5u.onrender.com)
- [x] FastAPI serves React dist/ (single deployment)
- [x] /test-dashboard skill for health checks
- [x] Workflow result shows plain English (not raw JSON)

## In Progress
- [ ] Interview prep doc for job agent architecture
- [ ] Fix Render deployment lag (sometimes needs manual clear cache)
- [ ] Verify all companies have descriptions (what_they_do)

## Completed (April 2, 2026)
- [x] Resume tab: paste URL or JD text, run ATS analysis, review/edit rewrite suggestions, copy tailored bullets
- [x] ATS endpoint scrapes JDs from Ashby/Greenhouse/Lever/Workable/generic URLs
- [x] ATS button on job cards links to Resume tab with job pre-loaded
- [x] /ats CLI skill for quick ATS analysis from terminal
- [x] README with architecture diagram, features, setup
- [x] Removed sensitive files from git (resume, preferences, .env.local)
- [x] Added Job Search Agent to portfolio site (rachita-portfolio)
- [x] resume.md synced with actual .docx content

## Next Up
- [ ] Interview prep document (architecture, what makes it agentic, v2 scope, challenges)
- [ ] Behavioral signals in scoring (applied/skipped jobs inform future scores)
- [ ] Monday brief generation
- [ ] Webhook callbacks from Apify instead of polling
- [ ] Purge sensitive files from git history (git filter-repo)
