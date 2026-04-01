"""
RSS-based company discovery.
Polls Next Play (hiring lists) and TechCrunch (funding news).

For each new post:
  - Extracts company names using Claude Haiku
  - Checks Ashby/Greenhouse for matching PM/ops roles
  - If roles found → saves to jobs table (existing scoring flow picks them up)
  - If no roles → scores the company with Sonnet + web context → saves to companies table

Run standalone: python agent/discover_from_rss.py
"""

import os
import re
import json
import httpx
import anthropic
import xml.etree.ElementTree as ET
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client
from datetime import datetime, timezone

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

RSS_SEEN_PATH = Path(__file__).parent.parent / "data" / "rss_seen.json"

RSS_FEEDS = [
    {
        "url": "https://nextplayso.substack.com/feed",
        "name": "Next Play",
        "type": "hiring_list",
    },
    {
        "url": "https://techcrunch.com/category/venture/feed/",
        "name": "TechCrunch",
        "type": "funding_news",
    },
    {
        "url": "https://bellanazzari.substack.com/feed",
        "name": "Open to Work",
        "type": "hiring_list",
    },
]

RACHITA_PROFILE_SHORT = """
Rachita Kumar — Senior PM at PayPal (checkout, 0-to-1 App Switch) + Founding PM at TruthSeek
(voice AI, LLM evals, enterprise clients). Finance background (PE/IB). Builder (Lunar, this agent).

TARGETS (inferred from actual applications + stated preferences):
- Commerce AI: AI for retail, eCommerce, checkout, shopping experiences (Rokt, Firework, Flip) — HIGH FIT given PayPal checkout background (App Switch, +450bps CVR)
- AI agents replacing human workers: customer support AI (Decagon, Sierra), sales AI, compliance AI (Arva, Obin AI)
- Enterprise AI: knowledge management (Glean), workflow automation (Assembled), evaluation (Scale AI)
- Fintech: consumer personal finance (EarnIn), B2B fintech infrastructure with strong product layer (Plaid), payments/FX
- Legal AI: workflow automation for law firms and legal teams (Harvey, Supio, truthsystems) — HIGH interest given finance/compliance background
- Finance workflow AI: contract data extraction, AP/AR automation, financial document processing, accounting AI sold to CFOs and finance teams (Klarity, Ramp, Brex, Zip) — STRONG FIT; candidate has 5+ years in PE/IB/finance and deeply understands the buyer
- Voice AI: conversational AI, voice agents, qualitative research, conversation intelligence (Listen Labs, TruthSeek, Giga) — HIGH interest given her TruthSeek background building LLM voice interview agents
- HR/recruiting AI: people data, talent intelligence (Juicebox, Pallet)
- Video AI: AI-generated media, avatar platforms (HeyGen, Tavus)
- Industrial AI: manufacturing, MEP, construction automation — fine if PM scope is customer-facing

NOT A FIT (score below 35):
- Dev Infra / Coding AI: tools FOR software engineers (Cursor, GitHub Copilot, Vercel, infra APIs, dbt, Fivetran) — no business/consumer end-user layer
- Cybersecurity / threat detection / incident response — completely different domain
- Clinical Health AI: EHR, drug discovery, radiology, clinical decision support, medical diagnosis — not her background
- Pure infrastructure (MLOps, DevOps, cloud infra) — no product layer
- Big tech / non-AI incumbents

GOOD FIT:
- Vibe coding / AI app builders (Lovable, Bolt, v0, Emergent) — consumer AI with real end users
- Consumer Health: female health apps (Flo, Clue, Maven), mental health, wellness, nutrition AI — fit; candidate built Lunar (AI health companion with Claude) in this exact space
- Fintech includes insurtech, insurance AI, benefits tech, payments, lending, FX — NOT Clinical Health AI
- Data / Analytics = BI and insights for business users (CFOs, ops teams) — fit; data pipeline infra for engineers = Dev Infra = not fit

KEY SIGNALS FOR HIGH SCORE:
- AI replacing a human worker in a business workflow = strong green flag
- Finance/fintech domain = strong green flag (her PE/IB background is directly relevant)
- Enterprise B2B with real end customers (not just developers) = strong green flag
- Seed-Series B stage = ideal (50-300 people)
- PM role involves direct customer contact, not just internal roadmap

Location: SF Bay Area or NYC preferred. Open to remote.
"""

# Canonical sector list — used across the whole system
SECTORS = [
    "AI employees",
    "Voice AI",
    "Video AI",
    "Vibe coding",
    "AI Platform",
    "Fintech",
    "Legal AI",
    "Clinical Health AI",
    "Consumer Health",
    "Cybersecurity AI",
    "Dev Infra / Coding AI",
    "Industrial AI",
    "Enterprise AI",
    "HR / Recruiting",
    "Data / Analytics",
    "Commerce AI",
    "Other",
]


# ---------------------------------------------------------------------------
# RSS Parsing
# ---------------------------------------------------------------------------

def load_seen() -> set:
    if RSS_SEEN_PATH.exists():
        return set(json.loads(RSS_SEEN_PATH.read_text()))
    return set()


def save_seen(seen: set):
    RSS_SEEN_PATH.write_text(json.dumps(list(seen), indent=2))


def parse_feed(url: str) -> list:
    """Parse RSS feed. Returns list of {title, link, content}."""
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = httpx.get(url, headers=headers, timeout=15, follow_redirects=True)
        r.raise_for_status()
    except Exception as e:
        print(f"  ✗ Feed fetch failed: {e}")
        return []

    try:
        root = ET.fromstring(r.text)
    except ET.ParseError as e:
        print(f"  ✗ XML parse failed: {e}")
        return []

    ns = {"content": "http://purl.org/rss/1.0/modules/content/"}
    items = []
    for item in root.findall(".//item"):
        title = item.findtext("title", "").strip()
        link = item.findtext("link", "").strip()
        description = item.findtext("description", "")
        content_el = item.find("content:encoded", ns)
        content = content_el.text if content_el is not None else description
        content = re.sub(r"<[^>]+>", " ", content or "")
        content = re.sub(r"\s+", " ", content).strip()
        if title and link:
            items.append({"title": title, "link": link, "content": content[:6000]})
    return items


def fetch_article_text(url: str) -> str:
    """Fetch full article text when RSS content is thin."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = httpx.get(url, headers=headers, timeout=12, follow_redirects=True)
        if r.status_code == 200:
            html = r.text
            # Strip script/style/head blocks before tag removal (critical for Substack posts)
            html = re.sub(r"<(script|style|head)[^>]*>.*?</(script|style|head)>", " ", html, flags=re.DOTALL | re.IGNORECASE)
            html = html.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:10000]
    except Exception:
        pass
    return ""


# ---------------------------------------------------------------------------
# Company Extraction
# ---------------------------------------------------------------------------

def extract_companies_from_post(title: str, content: str, post_type: str) -> list:
    """Claude Haiku extracts company names from a post."""
    if post_type == "hiring_list":
        prompt = f"""This is a newsletter that curates tweets from founders/employees announcing they're hiring.

POST TITLE: {title}
POST CONTENT: {content[:8000]}

Extract every company that is actively hiring based on the tweet content.
Use your knowledge to identify companies from:
- Explicit company names ("join us at Anthropic", "Stripe is hiring")
- Twitter handles (@warpdotco = Warp, @hedra_labs = Hedra, @kalshi = Kalshi, @joinkaizen = Kaizen, @tryshortcutai = Shortcut AI)
- Founder/employee accounts posting "we're hiring" — use your knowledge to identify what company they work at
- Company descriptions in the tweet text

Only include companies that are explicitly hiring. Exclude: VCs, investors, individual people who aren't announcing a job opening at a specific company.

Return ONLY a JSON array of company name strings. Use the real company name, not the Twitter handle.
Example: ["Warp", "Anthropic", "Kaizen", "Hedra", "Kalshi", "Shortcut"]
If none found, return [].
No markdown, no explanation."""
    else:
        prompt = f"""This is a tech news article about a startup funding round.

TITLE: {title}
CONTENT: {content[:2000]}

Extract the company name that raised funding. Return ONLY a JSON array with one element.
Example: ["Acme AI"]
If no company found, return [].
No markdown, no explanation."""

    # Use Sonnet for hiring_list (needs world knowledge to resolve founders/handles to companies)
    # Use Haiku for funding_news (just extracting a company name from structured news text)
    model = "claude-sonnet-4-6" if post_type == "hiring_list" else "claude-haiku-4-5-20251001"
    try:
        msg = client.messages.create(
            model=model,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception as e:
        print(f"    ✗ Extract error: {e}")
        return []


def extract_funding_info(title: str, content: str) -> str:
    """Pull funding amount/round from article text."""
    patterns = [
        r"\$(\d+\.?\d*[MB])\s*(Series\s+[A-D]|Seed|Pre-seed|growth)",
        r"(Series\s+[A-D]|Seed)\s+.*?\$(\d+\.?\d*[MB])",
        r"raised\s+\$(\d+\.?\d*[MB])",
    ]
    combined = title + " " + content[:500]
    for p in patterns:
        m = re.search(p, combined, re.IGNORECASE)
        if m:
            return m.group(0).strip()
    return ""


# ---------------------------------------------------------------------------
# ATS Slug Discovery (reusing logic from discover_from_post)
# ---------------------------------------------------------------------------

def slug_candidates(company_name: str) -> list:
    name = company_name.lower()
    for suffix in [" ai", " labs", " hq", " inc", " corp", ".ai", ".io"]:
        name = name.replace(suffix, "")
    name = name.strip()
    no_spaces = name.replace(" ", "")
    hyphenated = name.replace(" ", "-")
    first_word = name.split()[0] if " " in name else name
    return list(dict.fromkeys([no_spaces, hyphenated, first_word, name]))


def find_ashby_jobs(company_name: str) -> tuple:
    """Returns (slug, matching_jobs_list) or (None, [])."""
    from agent.discover import get_role_type, passes_location_filter, passes_no_list_filter, save_job, get_company_id
    for slug in slug_candidates(company_name):
        try:
            r = httpx.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}", timeout=6)
            if r.status_code == 200:
                jobs = r.json().get("jobs", [])
                company_id = get_company_id(company_name)
                new_jobs = []
                for job in jobs:
                    title = job.get("title", "")
                    location = job.get("location", "")
                    job_url = job.get("jobUrl", "")
                    jd_text = job.get("descriptionPlain", "")[:4000]
                    if not passes_location_filter(location):
                        continue
                    role_type = get_role_type(title)
                    if not role_type or not passes_no_list_filter(title):
                        continue
                    saved = save_job(company_name, company_id, title, job_url, "rss_ashby", role_type, jd_text)
                    if saved:
                        new_jobs.append(title)
                return slug, new_jobs
        except Exception:
            pass
    return None, []


def find_greenhouse_jobs(company_name: str) -> tuple:
    """Returns (slug, matching_jobs_list) or (None, [])."""
    from agent.discover import get_role_type, passes_location_filter, passes_no_list_filter, save_job, get_company_id
    import re as _re
    for slug in slug_candidates(company_name):
        try:
            r = httpx.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", timeout=6)
            if r.status_code == 200:
                jobs = r.json().get("jobs", [])
                company_id = get_company_id(company_name)
                seen = set()
                new_jobs = []
                for job in jobs:
                    title = job.get("title", "")
                    location = job.get("offices", [{}])[0].get("name", "") if job.get("offices") else ""
                    job_url = job.get("absolute_url", "")
                    if title in seen or not passes_location_filter(location):
                        continue
                    seen.add(title)
                    role_type = get_role_type(title)
                    if not role_type or not passes_no_list_filter(title):
                        continue
                    jd_text = ""
                    job_id = job.get("id")
                    if job_id:
                        try:
                            jd_r = httpx.get(
                                f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs/{job_id}",
                                timeout=6,
                            )
                            if jd_r.status_code == 200:
                                raw_html = jd_r.json().get("content", "")
                                jd_text = _re.sub(r"<[^>]+>", " ", raw_html).strip()[:4000]
                        except Exception:
                            pass
                    saved = save_job(company_name, company_id, title, job_url, "rss_greenhouse", role_type, jd_text)
                    if saved:
                        new_jobs.append(title)
                return slug, new_jobs
        except Exception:
            pass
    return None, []


# ---------------------------------------------------------------------------
# Web search — lightweight context enrichment for unknown companies
# ---------------------------------------------------------------------------

def web_search_company(company_name: str) -> str:
    """
    Quick DuckDuckGo search to get context about an unknown company.
    Returns a short text snippet (< 1500 chars). Falls back to empty string.
    """
    try:
        query = company_name.replace(" ", "+") + "+startup+product"
        url = f"https://html.duckduckgo.com/html/?q={query}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        }
        r = httpx.get(url, headers=headers, timeout=8, follow_redirects=True)
        if r.status_code != 200:
            return ""
        # Extract result snippets — DuckDuckGo HTML puts them in .result__snippet divs
        snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', r.text, re.DOTALL)
        if not snippets:
            # Broader fallback: strip all HTML and take first 1500 chars
            text = re.sub(r"<[^>]+>", " ", r.text)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:1500]
        clean = []
        for s in snippets[:4]:
            clean.append(re.sub(r"<[^>]+>", "", s).strip())
        return " ".join(clean)[:1500]
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Feedback signal loading — feeds into scoring prompt
# ---------------------------------------------------------------------------

def _fetch_feedback_examples() -> str:
    """
    Load companies Rachita has marked as good_fit or not_for_me from the
    companies table. Used as calibration examples in the scoring prompt.
    """
    try:
        res = (
            supabase.table("companies")
            .select("name, what_they_do, sector, attention_score, feedback")
            .not_.is_("feedback", "null")
            .limit(20)
            .execute()
        )
        items = res.data or []
        if not items:
            return ""
        lines = ["CALIBRATION EXAMPLES (from Rachita's actual ratings):"]
        for item in items:
            fb = item.get("feedback", "")
            label = "GOOD FIT" if fb == "good_fit" else "NOT A FIT"
            name = item.get("name", "")
            what = item.get("what_they_do", "")
            score = item.get("attention_score", "?")
            sector = item.get("sector", "")
            lines.append(f"  [{label}] {name} ({sector}, score {score}): {what}")
        return "\n".join(lines)
    except Exception:
        return ""


def _fetch_skip_examples() -> str:
    """
    Load recently skipped jobs from the jobs table.
    Teaches the scorer what sectors/companies Rachita actively dismisses.
    """
    try:
        res = (
            supabase.table("jobs")
            .select("company_name, title, score_breakdown")
            .eq("status", "skip")
            .limit(30)
            .execute()
        )
        items = res.data or []
        if not items:
            return ""
        lines = ["RECENTLY SKIPPED JOBS (Rachita dismissed these — learn the pattern):"]
        for item in items:
            bd = item.get("score_breakdown") or {}
            sector = bd.get("sector", "")
            skip_reason = bd.get("skip_reason", "")
            company = item.get("company_name", "")
            title = item.get("title", "")
            line = f"  [SKIPPED] {company} — {title}"
            if sector:
                line += f" (sector: {sector})"
            if skip_reason:
                line += f" | reason: {skip_reason}"
            lines.append(line)
        return "\n".join(lines)
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Stage inference
# ---------------------------------------------------------------------------

def _extract_stage_from_funding(funding_info: str, context: str) -> str:
    """
    Infer company stage from explicit round labels first, then from amount.
    More reliable than pure keyword matching.
    """
    text = (funding_info + " " + context[:500]).lower()

    # Explicit stage labels (most reliable)
    stage_patterns = [
        ("Pre-Seed", ["pre-seed", "pre seed"]),
        ("Seed",     ["seed round", "seed funding", "seed stage", "seed-stage",
                      "seed-backed", "seed extension"]),
        ("Series A", ["series a"]),
        ("Series B", ["series b"]),
        ("Series C", ["series c"]),
        ("Series D", ["series d"]),
        ("Series E", ["series e"]),
        ("Growth",   ["growth round", "growth equity", "growth stage"]),
        ("Public",   ["ipo", "nasdaq:", "nyse:", "publicly traded", "went public"]),
    ]
    for stage, patterns in stage_patterns:
        if any(p in text for p in patterns):
            return stage

    # Infer from funding amount when no explicit label
    amount_match = re.search(r"\$(\d+\.?\d*)([MB])", funding_info, re.IGNORECASE)
    if amount_match:
        amount = float(amount_match.group(1))
        unit = amount_match.group(2).upper()
        usd_m = amount if unit == "M" else amount / 1_000_000
        if usd_m < 3:
            return "Pre-Seed"
        elif usd_m < 15:
            return "Seed"
        elif usd_m < 40:
            return "Series A"
        elif usd_m < 80:
            return "Series B"
        elif usd_m < 200:
            return "Series C"
        else:
            return "Series D+"

    return ""


def _extract_investors(text: str) -> str:
    patterns = [
        r"led by ([A-Z][^,.]{3,40})",
        r"backed by ([A-Z][^,.]{3,40})",
        r"([A-Z][a-zA-Z\s]+(?:Ventures|Capital|Partners|Invest|VC|Fund)[^,.]{0,20}) led",
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(1).strip()[:80]
    return ""


# ---------------------------------------------------------------------------
# Sector extraction — keyword fallback only
# Use Claude's sector assignment from scoring as the primary source.
# This is only called when Claude doesn't return a sector.
# ---------------------------------------------------------------------------

def _extract_sector(text: str) -> str:
    """
    Keyword-based sector fallback. Only used when Claude doesn't return a sector.
    Keywords are intentionally specific to avoid false matches.
    """
    text_lower = text.lower()
    sector_keywords = [
        ("AI employees",     ["ai workforce", "ai worker", "ai employee", "ai superhuman",
                              "ai sales rep", "digital worker", "agentic workforce"]),
        ("Voice AI",         ["voice ai", "voice agent", "voice interview", "speech ai",
                              "conversational voice", "voice-based", "audio ai"]),
        ("Video AI",         ["video generation", "text-to-video", "video ai", "synthetic video",
                              "ai video", "talking head"]),
        ("Vibe coding",      ["ai coding", "no-code app builder", "low-code platform",
                              "text-to-app", "text-to-code"]),
        ("Fintech",          ["fintech", "payments platform", "neobank", "banking platform",
                              "lending platform", "cross-border payments", "stablecoin",
                              "embedded finance", "aml platform", "kyc automation", "kyb"]),
        ("Legal AI",         ["legal ai", "law firm automation", "contract review",
                              "legal workflow", "litigation ai", "legal tech"]),
        ("Health AI",        ["health ai", "medical ai", "clinical ai", "healthcare platform",
                              "patient care", "ehr ai", "mental health ai"]),
        # Intentionally narrow to avoid false positives:
        ("Cybersecurity AI", ["cybersecurity platform", "threat detection ai",
                              "incident response ai", "vulnerability scanner"]),
        ("Dev Infra / Coding AI",  ["developer platform", "api infrastructure", "devtools",
                              "model context protocol", "mcp server"]),
        ("Industrial AI",    ["manufacturing ai", "construction ai", "mep automation",
                              "industrial automation", "supply chain ai"]),
        ("HR / Recruiting",  ["recruiting platform", "talent acquisition ai",
                              "hr ai platform", "hiring platform", "people intelligence"]),
        ("Data / Analytics", ["data platform", "analytics platform",
                              "business intelligence ai", "data pipeline ai"]),
        ("Enterprise AI",    ["enterprise ai platform", "b2b ai", "ai workspace",
                              "workflow automation ai", "business automation"]),
    ]
    for label, keywords in sector_keywords:
        if any(kw in text_lower for kw in keywords):
            return label
    return "Enterprise AI"  # default fallback


# ---------------------------------------------------------------------------
# Scoring — uses Sonnet + web context + all feedback signals
# ---------------------------------------------------------------------------

def score_company_for_radar(company_name: str, funding_info: str, context: str) -> dict:
    """
    Score whether this company is worth Rachita tracking.
    Uses Sonnet (knows most companies by name) + web search for unknown ones.
    Returns dict with: attention_score, what_they_do, recommendation, sector, stage
    """
    # Enrich context with web search if we have little to work with
    if len(context.strip()) < 300:
        print(f"    🔍 Web search for context on {company_name}...")
        web_ctx = web_search_company(company_name)
        if web_ctx:
            context = web_ctx + "\n\n" + context

    feedback_examples = _fetch_feedback_examples()
    skip_examples = _fetch_skip_examples()

    sectors_list = ", ".join(SECTORS)

    prompt = f"""You are evaluating whether a startup is worth tracking for Rachita Kumar, even if they have no open PM role right now.

RACHITA'S PROFILE:
{RACHITA_PROFILE_SHORT}

{feedback_examples}

{skip_examples}

COMPANY: {company_name}
FUNDING INFO: {funding_info or "unknown"}
CONTEXT (from newsletter/article/web):
{context[:2000]}

Score this company 0-100 for "attention worthiness":
- 80-100: Rachita should reach out NOW even without a job posting. Perfect domain fit, right stage.
- 60-79: Worth watching. Strong PM culture, right domain, would be a good role.
- 40-59: Possible. Large established company with strong PM track record, or tangential AI fit.
- 0-39: Not a fit. Drop.

Good fits (score 60+): AI agents, voice AI, vertical AI SaaS, enterprise AI (meeting intelligence, productivity, knowledge management), fintech, B2B automation, revenue intelligence, customer success AI, recruiting AI, legal AI, sales AI.
Also score 50+ if: well-known B2B SaaS with strong PM culture even if not AI-native (e.g. Airtable, Notion, Linear, Figma, Stripe, Brex — companies where PMs do real product work and company is respected).
Bad fits (score below 35): pure dev infra, coding assistants, cybersecurity, health AI, defense, climate tech, pure infra/cloud, hardware only.
Use your own knowledge of this company (you likely know it) — don't rely only on the context above.

Also:
- Pick the BEST sector from this list: {sectors_list}
- Infer the stage if not explicit: Pre-Seed, Seed, Series A, Series B, Series C, Series D+, Growth, Public

Return ONLY valid JSON, no markdown:
{{"attention_score": <0-100>, "what_they_do": "<one sentence: what this company builds>", "recommendation": "reach_out_now|watch|drop", "sector": "<sector from list above>", "stage": "<stage or empty string>"}}"""

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw.strip())
        # Validate sector against canonical list
        if result.get("sector") not in SECTORS:
            result["sector"] = _extract_sector(
                result.get("what_they_do", "") + " " + company_name
            )
        return result
    except Exception as e:
        print(f"    ✗ Scoring error: {e}")
        return {
            "attention_score": 0,
            "what_they_do": "",
            "recommendation": "drop",
            "sector": "",
            "stage": "",
        }


# ---------------------------------------------------------------------------
# Relationship message generation
# ---------------------------------------------------------------------------

def generate_relationship_message(company_name: str, why_interesting: str, context: str) -> str:
    """Generate a relationship-building message. No mention of jobs."""
    prompt = f"""Write a short LinkedIn message from Rachita Kumar to someone at {company_name}.

RACHITA'S PROFILE:
{RACHITA_PROFILE_SHORT}

ABOUT THIS COMPANY: {why_interesting}
ADDITIONAL CONTEXT: {context[:1000]}

STYLE — study these real messages Rachita has sent and match her voice exactly:

Example 1 (specific product insight):
"Hi Dhwani! As the founding PM of a voice AI startup, I ran evals on conversation quality (follow-up questions, staying on topic, goal coverage). But standard benchmarks measure one response at a time. For Cartesia's SSMs, how do you do evals for a 30-minute call or when a user talks over the agent?"

Example 2 (parallel background):
"Hi Alfred. I was the founding PM at a voice AI user research platform for SMBs in India, very similar to what Listen Labs is building. I'm excited about this space and have been following Listen Labs' growth. I see that you're hiring for a founding PM, I'd love to chat."

Example 3 (product feedback, used the product):
"Hi Naman. I've enjoyed using Littlebird, I'm no longer copy pasting screenshots across screens! One little feedback: the 'update ready to install' prompt keeps interrupting the experience and asks for admin password, which feels jarring for a tool that's supposed to run quietly in the background."

Example 4 (domain insight from her work):
"Hi Michael, I'm a PM at PayPal and was the founding team PM at a voice AI user research startup (TruthSeek). While building TruthSeek, I realized that getting enterprises to trust AI-led workflows in regulated industries isn't a sales problem, it's a product design problem. Our clients wouldn't take AI-generated research to leadership meetings until we built an evidence layer: every insight linked to a verbatim quote and a playable audio timestamp."

Rules:
- Start with "Hi [Name]." — first name only, keep the period
- Lead with something SPECIFIC about their product or domain — a real observation, a parallel from her work, or a question that shows she understands the problem
- Connect ONE specific thing from her background (TruthSeek evals, PayPal checkout scale, Lunar solo build, finance/PE background) — with concrete detail, not a vague claim
- End with a light ask: "would love to connect" or "happy to share what I learned" or "would love to chat"
- NEVER mention applying for a role or looking for a job
- NEVER use: genuinely, really (as filler), amazing, passionate, thrilled, incredible, super, very excited, love what you're building
- NEVER use em dashes or hyphens as dashes
- 60-120 words. Conversational, direct, no corporate language

Return ONLY the message text."""

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=250,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Save to companies table
# ---------------------------------------------------------------------------

def save_to_companies(
    company_name: str,
    ashby_slug: str,
    greenhouse_slug: str,
    source: str,
    source_url: str,
    funding_info: str,
    what_they_do: str,
    relationship_message: str,
    attention_score: int = None,
    sector: str = None,
    stage: str = None,
    investors: str = None,
):
    """Save company to companies table (single source of truth). Skip if already there."""
    try:
        existing = supabase.table("companies").select("id").eq("name", company_name).execute()
        if existing.data:
            return False
        row = {
            "name": company_name,
            "source": source,
            "source_url": source_url,
            "funding_info": funding_info,
            "what_they_do": what_they_do,
            "relationship_message": relationship_message,
            "radar_status": "watching",
        }
        if ashby_slug:
            row["ashby_slug"] = ashby_slug
        if greenhouse_slug:
            row["greenhouse_slug"] = greenhouse_slug
        if attention_score is not None:
            row["attention_score"] = attention_score
        if sector:
            row["sector"] = sector
        if stage:
            row["stage"] = stage
        if investors:
            row["investors"] = investors
        supabase.table("companies").insert(row).execute()
        return True
    except Exception as e:
        print(f"    ✗ Companies save error: {e}")
        return False


# ---------------------------------------------------------------------------
# Process a single company
# ---------------------------------------------------------------------------

def process_company(
    company_name: str,
    source: str,
    source_url: str,
    funding_info: str,
    context: str,
) -> str:
    """
    Score company first. Only check job boards if it passes.
    Returns: 'roles_found', 'added_to_radar', 'dropped', 'duplicate'
    """
    # Step 1: Score the company — gate everything on fit
    scored = score_company_for_radar(company_name, funding_info, context)
    attention = scored.get("attention_score", 0)
    what_they_do = scored.get("what_they_do", "")
    rec = scored.get("recommendation", "drop")

    if rec == "drop" or attention < 60:
        print(f"    — Low fit ({attention}/100), dropping {company_name}")
        return "dropped"

    print(f"    ✓ {company_name} scored {attention}/100 — checking for open roles...")

    sector = scored.get("sector") or _extract_sector(what_they_do + " " + company_name)
    stage = (
        scored.get("stage")
        or _extract_stage_from_funding(funding_info, context[:500])
    )
    investors = _extract_investors(context[:500])

    # Step 2: Only now check job boards — company already passed the quality bar
    ashby_slug, ashby_jobs = find_ashby_jobs(company_name)
    if ashby_jobs:
        print(f"    🚀 {len(ashby_jobs)} role(s) → Open Roles: {', '.join(ashby_jobs)}")
        # Save to companies table so it's tracked going forward
        save_to_companies(
            company_name=company_name,
            ashby_slug=ashby_slug,
            greenhouse_slug=None,
            source=source,
            source_url=source_url,
            funding_info=funding_info,
            what_they_do=what_they_do,
            relationship_message="",
            attention_score=attention,
            sector=sector,
            stage=stage,
            investors=investors,
        )
        return "roles_found"

    gh_slug, gh_jobs = find_greenhouse_jobs(company_name)
    if gh_jobs:
        print(f"    🚀 {len(gh_jobs)} role(s) → Open Roles: {', '.join(gh_jobs)}")
        save_to_companies(
            company_name=company_name,
            ashby_slug=None,
            greenhouse_slug=gh_slug,
            source=source,
            source_url=source_url,
            funding_info=funding_info,
            what_they_do=what_they_do,
            relationship_message="",
            attention_score=attention,
            sector=sector,
            stage=stage,
            investors=investors,
        )
        return "roles_found"

    # Step 3: No open roles — add to radar with outreach message
    rel_msg = generate_relationship_message(company_name, what_they_do, context)

    added = save_to_companies(
        company_name=company_name,
        ashby_slug=ashby_slug,
        greenhouse_slug=gh_slug,
        source=source,
        source_url=source_url,
        funding_info=funding_info,
        what_they_do=what_they_do,
        relationship_message=rel_msg,
        attention_score=attention,
        sector=sector,
        stage=stage,
        investors=investors,
    )

    if added:
        print(f"    🔭 {attention}/100 · {sector} · {stage} → Radar: {what_they_do[:60]}")
        return "added_to_radar"
    else:
        print(f"    — Already in companies table")
        return "duplicate"


# ---------------------------------------------------------------------------
# Main RSS scan
# ---------------------------------------------------------------------------

def extract_companies_from_rss() -> list:
    """
    Discovery-only RSS scan: extract company names, add to DB with basic info.
    Does NOT score, route, or generate outreach — pipeline handles that separately.
    Returns list of newly added company names.
    """
    seen = load_seen()
    new_companies: list = []

    for feed in RSS_FEEDS:
        items = parse_feed(feed["url"])
        for item in items:
            url = item["link"]
            title = item["title"]
            if url in seen:
                continue
            if feed["type"] == "funding_news":
                funding_keywords = ["raises", "raised", "funding", "series", "seed", "million"]
                if not any(kw in title.lower() for kw in funding_keywords):
                    seen.add(url)
                    continue
            content = item["content"]
            if len(content) < 200:
                content = fetch_article_text(url)
            companies = extract_companies_from_post(title, content, feed["type"])
            if not companies:
                seen.add(url)
                continue
            funding_info = extract_funding_info(title, content) if feed["type"] == "funding_news" else ""
            for company in companies:
                added = save_to_companies(
                    company_name=company,
                    ashby_slug=None,
                    greenhouse_slug=None,
                    source=feed["name"],
                    source_url=url,
                    funding_info=funding_info,
                    what_they_do="",
                    relationship_message="",
                    attention_score=None,
                )
                if added:
                    new_companies.append(company)
            seen.add(url)

    save_seen(seen)
    return new_companies


def run_rss_scan():
    print("\n=== RSS Funding Scan ===")
    seen = load_seen()
    total_roles = 0
    total_radar = 0
    new_companies: list = []

    for feed in RSS_FEEDS:
        print(f"\n--- {feed['name']} ---")
        items = parse_feed(feed["url"])
        print(f"  {len(items)} posts found")

        for item in items:
            url = item["link"]
            title = item["title"]

            if url in seen:
                continue

            if feed["type"] == "funding_news":
                funding_keywords = ["raises", "raised", "funding", "series", "seed", "million"]
                if not any(kw in title.lower() for kw in funding_keywords):
                    seen.add(url)
                    continue

            print(f"\n  📄 {title}")

            content = item["content"]
            if len(content) < 200:
                content = fetch_article_text(url)

            companies = extract_companies_from_post(title, content, feed["type"])
            if not companies:
                seen.add(url)
                continue

            print(f"  Found {len(companies)} companies: {', '.join(companies[:8])}{'...' if len(companies) > 8 else ''}")

            funding_info = extract_funding_info(title, content) if feed["type"] == "funding_news" else ""

            for company in companies:
                print(f"  → {company}")
                result = process_company(
                    company_name=company,
                    source=feed["name"],
                    source_url=url,
                    funding_info=funding_info,
                    context=content[:2000],
                )
                if result == "roles_found":
                    total_roles += 1
                    new_companies.append(company)
                elif result == "added_to_radar":
                    total_radar += 1
                    new_companies.append(company)

            seen.add(url)

    save_seen(seen)
    print(f"\nDone. {total_roles} new roles in Open Roles. {total_radar} companies added to Radar.")
    return {"roles_found": total_roles, "radar_added": total_radar, "new_companies": new_companies}


if __name__ == "__main__":
    run_rss_scan()
