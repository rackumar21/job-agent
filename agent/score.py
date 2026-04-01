"""
Scoring module — scores unscored jobs using Claude.
Run standalone: python agent/score.py

Attractiveness score (0-100):
  30 pts  Role-profile fit      — does this role match Rachita's background?
  25 pts  Company fit           — right type/stage/domain of company?
  20 pts  End-user layer        — customer-facing work (not pure infra/internal)?
  15 pts  Growth signal         — company momentum, hiring across functions?
  10 pts  Location fit          — SF Bay / NYC / remote preferred?
"""

import os
import json
import anthropic
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

RACHITA_PROFILE = """
CANDIDATE: Rachita Kumar
Current role: Senior PM, PayPal Branded Checkout (June 2024-present, Santa Clara CA)
  - Shipped App Switch: PayPal's first mobile checkout (0-to-1), +450 bps conversion, $50M incremental TPV
  - A/B conversion program: 6+ concurrent tests/sprint, +300 bps from winners
  - Built Claude-powered internal diagnostic tool (Confluence MCP), used by 10-person PM team

Past experience:
  - Founding PM at TruthSeek (voice AI qualitative research, stealth, alongside PayPal 2024-26)
    - Designed LLM voice interview agent, built eval pipelines, ran live CPG consumer research studies
    - Key metrics: call completion 38%-to-61%, funnel efficiency 3,758-to-7 completions
  - Brex PM (Spend Management, Fall 2023 MBA internship)
  - Walmart GoLocal GTM Strategy (Summer 2023 MBA internship)
  - Madison India Capital (PE, 2019-22): financial modeling, deal execution, portfolio companies
  - Deutsche Bank IB (APAC Energy, 2017-18)
  - Wharton MBA 2022-24 (STEM, Business Analytics + Entrepreneurship, GMAT 750, 98th percentile)
  - SRCC Delhi University (Rank 6/705)

Builder credibility:
  - Built Lunar (AI health companion) solo: React, Supabase, Claude API, Vercel — live product
  - Built PM Interview Coach, Job App Prep CLI, Insight Engine — all public on GitHub
  - Uses Claude Code and Cursor daily; not a software engineer but can build and ship

What she wants:
  - PM or Strategy & Ops role at an AI-native company
  - Sweet spot: 50-300 people, post-PMF, customer-facing PM work (not pure infra)
  - Open to both: 0-to-1 (new product lines) AND 1-to-100 (scaling a product that already works)
  - Companies building AI agents, automation, enterprise AI, fintech AI
  - NOT targeting: Dev Infra / Coding AI (tools for developers), clinical/medical health AI, cybersecurity, pure infra
  - Vibe coding / AI app builders (Lovable, Bolt, v0, Emergent) ARE a fit — consumer AI products with real end users
  - Insurtech and health insurance platforms ARE fine — finance background is directly relevant
  - Location: SF Bay Area or NYC preferred; open to hybrid/remote
  - Has PE/finance background — strong fit for fintech, regulated industries, enterprise

Green flags: founder-adjacent scope, direct customer contact, AI-first product culture, scaling a live AI product
Red flags: PM = roadmap manager, big tech bureaucracy, no end-user layer
"""

SCORING_INSTRUCTIONS = """Score a job posting for Rachita Kumar on a 0-100 scale.

Score on these 5 dimensions (weights shown):

1. Role-profile fit (max 30 pts): Does this role match her 8yr background — finance to PM to AI? For PM roles: is the scope right (0-to-1 OR scaling a live product, customer-facing, not admin PM)? She has both: shipped App Switch from zero, and scaled TruthSeek from early users to CPG clients. For operator roles: does it need finance + strategy + builder skills?

2. Company fit (max 25 pts): Right type/stage? She wants AI-native, post-PMF, 50-300 people. Penalise: big tech, pure infra, no product sense culture.

3. End-user layer (max 20 pts): Does the role involve real customers/users? Penalise: pure internal tooling, infrastructure, B2D (developer-only) roles.

4. Growth signal (max 15 pts): Is the company in a growth moment? Hiring across functions = good signal. Stagnant hiring = lower score.

5. Location fit (max 10 pts): SF Bay Area or NYC = 10 pts. Remote-friendly = 8 pts. Other US = 5 pts. No location info = 5 pts. Outside US only = 2 pts.

Also output:
- ats_gaps: list 5-8 keywords from the JD that Rachita should ensure are in her resume/cover letter
- key_angle: one sentence — the single strongest reason Rachita is a fit for THIS specific role
- red_flags: any genuine concerns (seniority mismatch, wrong domain, etc). Empty list if none.
- recommendation: "apply" | "borderline" | "skip"
  - apply: score >= 75
  - borderline: score 55-74 (surface for human review)
  - skip: score < 55

Also output:
- sector: one of "AI employees" | "Voice AI" | "Video AI" | "Vibe coding" | "Fintech" | "Legal AI" | "Clinical Health AI" | "Consumer Health" | "Cybersecurity AI" | "Dev Infra / Coding AI" | "Industrial AI" | "Enterprise AI" | "HR / Recruiting" | "Data / Analytics" | "Commerce AI" | "AI Platform" | "Other"

Sector definitions:
- AI employees: AI replacing human workers in business workflows (CS agents, sales reps, compliance, back-office automation)
- Voice AI: voice agents, conversational AI, speech intelligence
- Video AI: AI video generation, avatar platforms
- Vibe coding: AI app builders for NON-developers (Lovable, Bolt, v0, Emergent) — consumer/prosumer, end user has no coding skills
- Fintech: payments, lending, FX, B2B fintech, consumer finance, AND insurtech/insurance AI/benefits tech
- Legal AI: law firm workflow, contract analysis, legal automation
- Clinical Health AI: EHR, drug discovery, radiology, clinical decision support, medical diagnosis — NOT a fit
- Consumer Health: consumer health apps, female health (Flo, Clue, Maven), mental health, wellness, nutrition AI — fit, candidate built Lunar (AI health companion) in this space
- Cybersecurity AI: threat detection, incident response — NOT a fit
- Dev Infra / Coding AI: tools FOR software engineers (Cursor, GitHub Copilot, Vercel, infra APIs, data pipelines like Fivetran/dbt) — NOT a fit
- Industrial AI: manufacturing, construction, MEP, robotics, physical process automation
- Enterprise AI: knowledge management, workflow automation, productivity (Glean, Assembled, Notion AI)
- HR / Recruiting: talent intelligence, people data, hiring platforms
- Data / Analytics: BI and insights platforms sold to BUSINESS end-users (CFOs, ops teams) — fit; if the end user is a data engineer, tag as Dev Infra instead
- Commerce AI: AI for retail, eCommerce, checkout, and shopping experiences (Rokt, Firework, Flip, shoppable video, checkout monetisation) — STRONG FIT given candidate's PayPal checkout background (App Switch, +450bps CVR, $50M TPV)
- AI Platform: foundation model labs (Anthropic, OpenAI, Mistral) — borderline; score based on whether the specific role is consumer/enterprise-facing vs developer-facing
- Other: anything that doesn't fit above
- stage: one of "Seed" | "Series A" | "Series B" | "Series C" | "Series D" | "Growth" | "Public" | "" (empty if unknown)

Return ONLY valid JSON, no markdown, no explanation:
{"role_fit": <int 0-30>, "company_fit": <int 0-25>, "end_user_layer": <int 0-20>, "growth_signal": <int 0-15>, "location_fit": <int 0-10>, "total": <sum of above>, "ats_gaps": [<string>], "key_angle": "<string>", "red_flags": [<string>], "recommendation": "<apply|borderline|skip>", "reasoning": "<2-3 sentences plain English>", "sector": "<string>", "stage": "<string>"}"""

# Keep the old name as an alias so callers of the old format still work
SCORING_PROMPT = SCORING_INSTRUCTIONS


def fetch_behavioral_signals() -> str:
    """Fetch applied/skipped/not-for-me signals to inform scoring."""
    try:
        applied = supabase.table("jobs").select("company_name").eq("status", "applied").execute().data or []
        applied_cos = sorted(set(j["company_name"] for j in applied))

        skipped = supabase.table("jobs").select("company_name, title, score_breakdown").eq("status", "skip").execute().data or []
        skipped_reasons = []
        for j in skipped:
            reason = (j.get("score_breakdown") or {}).get("skip_reason", "")
            if reason:
                skipped_reasons.append(f"  - {j['company_name']} ({j['title']}): {reason}")

        not_for_me = supabase.table("companies").select("name, feedback_reason").eq("feedback", "not_for_me").execute().data or []
        nfm_reasons = [f"  - {r['name']}: {r.get('feedback_reason','')}" for r in not_for_me if r.get("feedback_reason")]

        lines = []
        if applied_cos:
            lines.append(f"Companies she applied to (treat as STRONG FIT benchmarks): {', '.join(applied_cos[:15])}")
        if skipped_reasons:
            lines.append("Roles explicitly skipped and why (use to penalise similar roles):")
            lines.extend(skipped_reasons[:10])
        if nfm_reasons:
            lines.append("Companies marked not-for-me and why (use to penalise similar companies):")
            lines.extend(nfm_reasons[:10])
        return "\n".join(lines)
    except Exception:
        return ""


def fetch_unscored_jobs(limit: int = 20):
    res = (
        supabase.table("jobs")
        .select("id, company_name, title, jd_text, url, score_breakdown")
        .is_("attractiveness_score", "null")
        .eq("status", "new")
        .limit(limit)
        .execute()
    )
    return res.data or []


# ---------------------------------------------------------------------------
# Two-stage scoring — keyword pre-filter (Stage 1) before Claude (Stage 2)
# ---------------------------------------------------------------------------

_QUICK_HARD_NO = [
    # Engineering / infra roles — exclude on title match
    "software engineer", " swe ", "data engineer", "data scientist",
    "machine learning engineer", "ml engineer", "infrastructure engineer",
    "devops", "site reliability", " sre ", "security engineer",
    "cybersecurity engineer", "penetration test",
    # Clinical / medical
    "clinical", "physician", "radiolog", "drug discovery", "medical doctor",
    # Defense
    "defense", "military", "dod ",
    # Seniority mismatches
    "associate product manager", " apm ", "rotational pm",
]

_QUICK_PM_TITLE = [
    "product manager", "senior pm", "staff pm", "group pm", "principal pm",
    "product lead", "head of product", "vp of product",
]

_QUICK_OPS_TITLE = [
    "strategy", "operations", "chief of staff", "go-to-market", "gtm",
    "growth", "revenue", "commercial", "customer success", "account",
    "launch", "bizops",
]

_QUICK_DOMAIN_SIGNALS = [
    "ai", "llm", "agent", "voice", "automation", "enterprise", "b2b",
    "fintech", "payment", "checkout", "legal", "saas", "platform",
]


def quick_score(title: str, jd: str) -> int:
    """
    Stage 1: Zero-cost keyword pre-filter. Returns 0-100.
    If score < 30, skip Claude entirely — obvious mismatch.
    """
    title_lower = title.lower()
    text = (title_lower + " " + (jd or "").lower())

    # Hard no on title
    if any(k in title_lower for k in _QUICK_HARD_NO):
        return 0

    score = 25  # base — job made it through seniority/no-list filters upstream

    # Title match
    if any(k in title_lower for k in _QUICK_PM_TITLE):
        score += 35
    elif any(k in title_lower for k in _QUICK_OPS_TITLE):
        score += 20
    else:
        score += 5  # Unknown title type — let Claude decide

    # Domain signal boost (up to +15)
    domain_hits = sum(1 for k in _QUICK_DOMAIN_SIGNALS if k in text)
    score += min(15, domain_hits * 3)

    return min(100, score)


def score_job(job: dict) -> dict:
    title = job["title"]
    company = job["company_name"]
    jd = job.get("jd_text") or "(No job description available — score based on title and company only)"
    role_type = (job.get("score_breakdown") or {}).get("role_type", "pm")

    behavioral = fetch_behavioral_signals()

    # ── Stage 1: keyword pre-filter (free) ──────────────────────────────
    qs = quick_score(title, jd)
    if qs < 30:
        # Return a synthetic skip result — no Claude call needed
        return {
            "role_fit": 0, "company_fit": 0, "end_user_layer": 0,
            "growth_signal": 0, "location_fit": 5, "total": 5,
            "ats_gaps": [], "key_angle": "",
            "red_flags": [f"Quick filter: title '{title}' is not a PM/ops role"],
            "recommendation": "skip",
            "reasoning": f"Keyword pre-filter: title does not match PM/ops profile (score {qs}/100). Skipped without LLM call.",
            "sector": "Other", "stage": "",
        }

    # ── Stage 2: Claude scoring with prompt caching ──────────────────────
    # Static content (profile + scoring instructions) → system prompt, cached
    # Dynamic content (job details + behavioral signals) → user message
    system_content = f"""You are a job fit scorer for Rachita Kumar.

{RACHITA_PROFILE}

{SCORING_INSTRUCTIONS}"""

    user_content = f"""Score this job:

Company: {company}
Title: {title}
Role type: {role_type}
Job description:
{jd[:3500]}

Behavioral signals (from Rachita's actions — use to calibrate scores):
{behavioral or "None yet."}

Return ONLY valid JSON, no markdown."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        system=[{
            "type": "text",
            "text": system_content,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{"role": "user", "content": user_content}],
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    return json.loads(raw)


_NON_US_KEYWORDS = [
    "dach", "germany", "berlin", "munich", "stockholm", "sweden", "london",
    "uk ", " uk,", "united kingdom", "emea", "apac", "latam", "australia",
    "sydney", "melbourne", "toronto", "canada", "india", "singapore",
    "paris", "amsterdam", "dublin", "madrid", "barcelona",
]


def save_score(job_id: str, result: dict, role_type: str, title: str = ""):
    total = result["total"]
    recommendation = result["recommendation"]

    # Hard override: non-US location keyword in title → always skip
    title_lower = title.lower()
    if any(kw in title_lower for kw in _NON_US_KEYWORDS):
        new_status = "skip"
    # Hard override: if location scored as clearly outside US → skip
    elif result.get("location_fit", 10) <= 2:
        new_status = "skip"
    else:
        status_map = {"apply": "prep_ready", "borderline": "borderline", "skip": "skip"}
        new_status = status_map.get(recommendation, "borderline")

    supabase.table("jobs").update({
        "attractiveness_score": total,
        "score_breakdown": {
            "role_type": role_type,
            "role_fit": result["role_fit"],
            "company_fit": result["company_fit"],
            "end_user_layer": result["end_user_layer"],
            "growth_signal": result["growth_signal"],
            "location_fit": result["location_fit"],
            "ats_gaps": result.get("ats_gaps", []),
            "key_angle": result.get("key_angle", ""),
            "red_flags": result.get("red_flags", []),
            "sector": result.get("sector", ""),
            "stage": result.get("stage", ""),
        },
        "score_reasoning": result.get("reasoning", ""),
        "status": new_status,
    }).eq("id", job_id).execute()


def score_new_jobs(limit: int = 20) -> int:
    """Score unscored jobs, return count scored."""
    jobs = fetch_unscored_jobs(limit)
    if not jobs:
        return 0
    scored = 0
    for job in jobs:
        try:
            result = score_job(job)
            role_type = (job.get("score_breakdown") or {}).get("role_type", "pm")
            save_score(job["id"], result, role_type, title=job.get("title", ""))
            scored += 1
        except Exception:
            pass
    return scored


def run_scoring(limit: int = 20):
    print("\n=== Job Scoring ===")
    jobs = fetch_unscored_jobs(limit)

    if not jobs:
        print("No unscored jobs found.")
        return

    print(f"Scoring {len(jobs)} jobs...\n")
    scored = 0

    for job in jobs:
        title = job["title"]
        company = job["company_name"]
        role_type = (job.get("score_breakdown") or {}).get("role_type", "pm")

        try:
            result = score_job(job)
            save_score(job["id"], result, role_type, title=title)
            scored += 1

            total = result["total"]
            rec = result["recommendation"].upper()
            angle = result.get("key_angle", "")
            print(f"  {total:3d}/100  [{rec:9s}]  [{company}] {title}")
            if angle:
                print(f"           -> {angle}")
            if result.get("red_flags"):
                print(f"           ! {'; '.join(result['red_flags'])}")

        except json.JSONDecodeError as e:
            print(f"  ! JSON parse error for [{company}] {title}: {e}")
        except Exception as e:
            print(f"  ! Error scoring [{company}] {title}: {e}")

    print(f"\nDone. {scored}/{len(jobs)} jobs scored.")


if __name__ == "__main__":
    run_scoring()
