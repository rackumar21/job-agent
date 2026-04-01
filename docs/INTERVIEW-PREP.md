# Job Agent — Interview Prep

## Architecture Overview

### What is it?
An AI agent that automates my job search pipeline: discovers companies from 4 ATS platforms (Ashby, Greenhouse, Lever, Workable) + RSS feeds + LinkedIn, scores every role against my resume, routes to Open Roles or On Radar, and drafts personalized outreach. I review and approve everything. Nothing is sent automatically.

### Stack
- Frontend: React + Vite + Tailwind
- Backend: FastAPI (Python)
- Database: Supabase (Postgres)
- AI: Claude Sonnet (scoring, outreach drafts), Claude Haiku (extraction, ATS analysis)
- Deployment: Render
- Scrapers: Apify (LinkedIn, Work at a Startup)

### Pipeline Flow
```
Sources (Ashby/Greenhouse/Lever/Workable/LinkedIn/RSS)
    → Discover jobs and companies
    → Filter (seniority, location, no-list)
    → Score against my resume (two-stage: keyword pre-filter → Claude Sonnet)
    → Route: 55+ → Open Roles, <55 → skip, no roles → On Radar with draft outreach
    → I review, edit, send manually
```

### What Makes It Agentic
- Autonomous discovery: runs weekly, finds jobs from 4 ATS + RSS + LinkedIn without me triggering it
- Autonomous scoring: evaluates every role on 5 dimensions, learns from my applied/skipped behavior
- Autonomous routing: decides what goes to Open Roles vs On Radar vs skip
- Autonomous drafting: generates personalized outreach in my voice
- Human-in-the-loop: I approve every final action (apply, send message, skip)

---

## Scoring Deep Dive

### Two scoring systems

**Job Scoring (roles found):**
Every job goes through filters first (free, no AI cost):
- Seniority filter: keeps PM, Senior PM, Head of Product, Chief of Staff, Strategy & Ops
- No-list filter: auto-drops defense, cybersecurity, pure dev tools, clinical health
- Location filter: US, remote, or hybrid only

Survivors get scored by Claude Sonnet on 5 dimensions:
- Role fit (30%): does this role match my PM + finance + AI background?
- Company fit (25%): right stage (50-300 people), AI-native, post-PMF?
- End-user layer (20%): real customers using the product (not pure infra)?
- Growth signal (15%): company hiring across functions, momentum?
- Location (10%): SF Bay / NYC / remote?

The scoring prompt includes my full resume (cached for cost efficiency) and behavioral signals (jobs I've applied to as positive benchmarks, jobs I've skipped as negative signals).

**Company Scoring (no roles found):**
- 80-100: reach out NOW, perfect domain fit
- 60-79: worth watching, strong PM culture
- 40-59: possible, tangential fit
- Below 40: low relevance, still saved to On Radar with details

### How growth/hiring signals work
Two sources:
1. The JD text itself: Claude reads signals like "growing team from 5 to 20", "Series B", "first PM hire"
2. What the pipeline already knows: when polling a company's ATS, it sees ALL open roles. 30 open roles across departments = strong growth signal

### Resume caching
The scoring prompt includes my full resume cached in the system prompt. Claude scores each job by comparing the JD against my actual experience. Caching means the resume is sent once and reused for all jobs in a ~5 min window. Without caching: 50 jobs = 50x full resume tokens. With caching: 50 jobs = 1x resume + 50x just the JD = ~90% cheaper.

### ATS slug discovery
A slug is the company's identifier in the ATS URL (e.g., `jobs.ashbyhq.com/decagon` → "decagon" is the slug). There's no central directory, so the pipeline guesses: takes "Arize AI", tries `arizeai`, `arize-ai`, `arize`, `arizeaiai` across all 4 platforms in parallel. 4 slug patterns x 4 ATS = 16 HTTP calls per company, all parallel, done in ~3 seconds.

---

## Q&A

### What would you do differently if you rebuilt from scratch?

**Design the governance model before the discovery pipeline.** I built discovery first because it felt like the hard part. But the real complexity is the decision layer: what happens after you find a job? I retrofitted the human-in-the-loop flow later, which caused issues. The pipeline would score a company, find no roles, and silently drop it. I had no idea what was being dropped or why. I had to redesign so every company gets saved with a score and description. Nothing gets silently dropped anymore. I rebuilt the routing logic three times.

**Instrument the feedback loop from day one.** I have a 55-point threshold for Open Roles, but I don't know if it's calibrated correctly. Am I getting better response rates on 80+ companies versus 60s? I can't tell because I didn't build response tracking into the schema early. The behavioral signals exist (applied/skipped jobs feed into scoring), but I'm missing the closed-loop data: did the outreach work? Did the interview convert?

**Abstract the ATS layer earlier.** Started with Ashby and Greenhouse. 40% of companies weren't on either. Added Lever and Workable later. Each ATS has a different API shape. Ended up with four separate polling functions doing roughly the same thing. If I'd built an adapter interface from the start, adding a new platform would be a 10-line config instead of a 30-line function.

### Specific challenges

- **Slug discovery is guesswork.** No API to look up "what ATS does Company X use?" Try 4 patterns across 4 platforms. Flora's slug was lowercase but company name was capitalized, so jobs had `company_name: "flora"` with no link to the company record. Had to add post-processing to match by slug variants.

- **Scoring latency forced an architecture change.** First version scored synchronously in the HTTP request. 24 companies = 24 Claude calls in sequence = 3+ minute hang. Moved to background processing with polling. Had to build a job status system, frontend polling, and handle partial failures.

- **Company names are messier than expected.** Same company appears as "JuiceBox", "Juicebox", "juicebox" depending on source. Greenhouse returns slugs as company names. LinkedIn has different formatting. More time on name normalization than scoring logic.

### Tradeoffs you made and why

**Cost vs. coverage on scoring.** Two-stage system: free keyword pre-filter drops ~30% of non-fits, only survivors get Claude scoring. Tradeoff: might miss an unconventionally titled role. Set threshold very low (30/100) to minimize false negatives.

**Breadth vs. depth on ATS coverage.** Started with Ashby + Greenhouse, added Lever + Workable + web search. Each platform adds a separate polling function. Could have gone deeper on two instead of wider on four. Chose breadth because missing a company entirely is worse than imperfect parsing.

**Human-in-the-loop vs. full automation.** Agent drafts everything but sends nothing. Could automate LinkedIn messages or auto-apply, but bad outreach damages reputation in ways you can't undo. Tradeoff: slower (review 50+ drafts weekly), but higher quality.

**Speed vs. accuracy on company scoring.** Parallelized to 4 companies at a time. Tradeoff: parallel scoring means can't use one company's result to inform another's. Sequential would let me batch-score contextually.

**Stored scores vs. recomputing.** Companies get scored once and stored. But the rubric evolves (added "B2B SaaS with strong PM culture" after Airtable got 22). Auto-runs use stored scores (fast), manual runs always rescore (accurate). Tradeoff: some radar companies have stale scores from old rubric.

### If you had 2 more days, what would you improve?

**Day 1: Closed-loop feedback.** Add response_received_at, interview_stage tracker, conversion dashboard by score band. Without this, I'm tuning scoring by gut.

**Day 1 afternoon: Score explanation in UI.** The 5-dimension breakdown exists in the database but isn't surfaced. Add expandable section showing role_fit, company_fit scores and the key_angle (one-liner reason I'm a fit).

**Day 2: Company name resolution.** Build a proper normalization layer: deduplicate on domain, use website URL as canonical identifier instead of name string. Eliminates an entire class of bugs.

**Day 2 afternoon: LinkedIn signal integration.** Monitor LinkedIn posts from key people at target companies. CEO posting "doubling the team" is more predictive than an RSS funding announcement.

### Success metric and input levers

**Output metric: interviews-per-week from companies I'm genuinely excited about.**

```
Interviews = Companies discovered x Roles found x Score accuracy x Outreach quality x Response rate
```

Biggest input levers in order:
1. **Outreach quality** (highest leverage): personalized message referencing their specific product challenge = 5% vs 25% response rate
2. **Score accuracy**: miscalibrated scoring = wasting time on wrong companies, missing right ones
3. **Discovery breadth**: can't apply to what you don't find. Adding Lever + Workable expanded coverage ~40%
4. **Timing**: reaching out before a role is posted (On Radar) converts better than applying after 200 others

### What excites you about a company, and what are you looking to join?

What excites me: companies where **the AI isn't the product, it's the unlock.** Decagon doesn't sell "AI." They sell customer support that resolves tickets. Harvey doesn't sell "AI." They sell legal work done in hours instead of weeks.

I get excited when I see the gap between what the product does today and what it could do if someone obsessed over the user experience. Most AI products are impressive demos with terrible day-two retention.

Specifically looking for:
- **50-300 people, post-PMF.** Real customers, real revenue. Small enough that a PM owns the full surface.
- **AI-native, not AI-added.** Built around AI from day one. Not a legacy product with a chatbot.
- **PMs go deep.** Expected to understand model behavior, run evals, write prompts, review outputs.
- **Domain I can contribute to.** Fintech (PayPal), voice AI (TruthSeek), enterprise automation. My background is directly relevant, not adjacent.
- **Global ambitions.** Grew up in India, worked in Indian finance, MBA in US. Companies expanding to India can use that perspective.

Target companies: Decagon, Sierra, Harvey (agent B2B). Ramp, Stripe (fintech + AI). HockeyStack, Mercor (growth-stage, PM-heavy). Common thread: they all need PMs who think like engineers because they've shipped like one.
