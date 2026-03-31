"""
Discover companies from a LinkedIn or Twitter/X post URL (or pasted text).

Flow:
  1. Fetch post content from URL (or use pasted text as fallback)
  2. Claude extracts company names from the post
  3. For each company not already tracked:
     a. Try Ashby + Greenhouse to find their job board slug
     b. Write slug to companies table (single source of truth)
     c. If slug found → poll for open roles → jobs go to Open Roles tab
     d. If no slug found → score company for radar → add to companies table → shows in Radar
"""

import os
import re
import json
import httpx
import anthropic
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))


def fetch_post_text(url: str) -> str:
    """Try to fetch post text from URL. Returns empty string if blocked."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    try:
        resp = httpx.get(url, headers=headers, follow_redirects=True, timeout=10)
        if resp.status_code == 200:
            html = resp.text
            # Strip script/style/head blocks entirely before tag removal
            html = re.sub(r"<(script|style|head)[^>]*>.*?</(script|style|head)>", " ", html, flags=re.DOTALL | re.IGNORECASE)
            # Decode common HTML entities
            html = html.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'")
            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:12000]
        return ""
    except Exception:
        return ""


def extract_company_names(text: str) -> list:
    """Use Claude to extract company names from post text."""
    prompt = f"""Extract all company names mentioned in this post. These are startup or tech company names that are hiring.

POST TEXT:
{text[:8000]}

Rules:
- Resolve Twitter/X handles to company names (e.g. @warpdotco → Warp, @hedra_labs → Hedra, @joinkaizen → Kaizen, @tryshortcutai → Shortcut)
- Include companies mentioned as hiring, even if just "we're hiring" in a tweet
- Exclude: individual people's names, VCs/investors, generic words
- Only include actual company names, not roles or job titles

Return ONLY a JSON array of company name strings. No markdown, no explanation.
Example: ["Warp", "Anthropic", "Kaizen", "Hedra", "Shortcut"]
If no companies found, return [].
"""
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    try:
        return json.loads(raw)
    except Exception:
        return []


def slug_candidates(company_name: str) -> list:
    """Generate likely ATS slug variations for a company name."""
    name = company_name.lower()
    for suffix in [" ai", " labs", " hq", " inc", " corp", ".ai", ".io"]:
        name = name.replace(suffix, "")
    name = name.strip()
    no_spaces = name.replace(" ", "")
    hyphenated = name.replace(" ", "-")
    first_word = name.split()[0] if " " in name else name
    return list(dict.fromkeys([no_spaces, hyphenated, first_word, name]))


def find_ashby_slug(company_name: str):
    for slug in slug_candidates(company_name):
        try:
            resp = httpx.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}", timeout=6)
            if resp.status_code == 200 and resp.json().get("jobs") is not None:
                return slug
        except Exception:
            pass
    return None


def find_greenhouse_slug(company_name: str):
    for slug in slug_candidates(company_name):
        try:
            resp = httpx.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", timeout=6)
            if resp.status_code == 200:
                return slug
        except Exception:
            pass
    return None


def is_already_tracked(company_name: str) -> bool:
    """Check if company is already in the companies table."""
    res = supabase.table("companies").select("id").ilike("name", company_name).execute()
    return bool(res.data)


def process_post(url: str = None, text: str = None) -> dict:
    """
    Main entry point. Pass either a URL or raw text (or both).
    Returns summary of what happened for each company found.
    """
    # Step 1: Get post text
    if url and not text:
        text = fetch_post_text(url)
        if not text:
            return {
                "error": "Could not fetch post content. LinkedIn requires login. Paste the post text directly instead.",
                "companies_found": [], "added_ashby": [], "added_greenhouse": [],
                "added_to_radar": [], "no_ats_found": [], "already_known": [],
                "added_ashby_slugs": {}, "added_greenhouse_slugs": {},
            }

    if not text:
        return {"error": "No text or URL provided.", "companies_found": [], "added_ashby": [],
                "added_greenhouse": [], "added_to_radar": [], "no_ats_found": [], "already_known": [],
                "added_ashby_slugs": {}, "added_greenhouse_slugs": {}}

    # Step 2: Extract company names
    companies = extract_company_names(text)

    added_ashby = []
    added_greenhouse = []
    added_to_radar = []
    no_ats = []
    already = []
    added_ashby_slugs = {}
    added_greenhouse_slugs = {}

    from agent.discover_from_rss import score_company_for_radar, generate_relationship_message

    for company in companies:
        if is_already_tracked(company):
            already.append(company)
            continue

        # Step 1: Score company first — quality gate before anything else
        scored = score_company_for_radar(company, "", text[:1000])
        attention = scored.get("attention_score", 0)
        what_they_do = scored.get("what_they_do", "")
        sector = scored.get("sector", "") or None
        stage = scored.get("stage", "") or None

        if attention < 60:
            print(f"  — Dropping {company} (score {attention}/100 — not a fit)")
            continue

        # Step 2: Company passed — now check ATS for open roles
        # Step 2a: Try Ashby
        ashby_slug = find_ashby_slug(company)
        if ashby_slug:
            rel_msg = generate_relationship_message(company, what_they_do, text[:500])
            supabase.table("companies").insert({
                "name": company,
                "ashby_slug": ashby_slug,
                "source": "post",
                "attention_score": attention,
                "what_they_do": what_they_do,
                "sector": sector,
                "stage": stage,
                "relationship_message": rel_msg or None,
            }).execute()
            added_ashby.append(company)
            added_ashby_slugs[ashby_slug] = company
            continue

        # Step 2b: Try Greenhouse
        gh_slug = find_greenhouse_slug(company)
        if gh_slug:
            rel_msg = generate_relationship_message(company, what_they_do, text[:500])
            supabase.table("companies").insert({
                "name": company,
                "greenhouse_slug": gh_slug,
                "source": "post",
                "attention_score": attention,
                "what_they_do": what_they_do,
                "sector": sector,
                "stage": stage,
                "relationship_message": rel_msg or None,
            }).execute()
            added_greenhouse.append(company)
            added_greenhouse_slugs[gh_slug] = company
            continue

        # Step 2c: No ATS — add to radar
        rel_msg = generate_relationship_message(company, what_they_do, text[:500])
        supabase.table("companies").insert({
            "name": company,
            "source": "post",
            "attention_score": attention,
            "what_they_do": what_they_do,
            "sector": sector,
            "stage": stage,
            "relationship_message": rel_msg or None,
            "radar_status": "watching",
        }).execute()

        if attention >= 60:
            added_to_radar.append(f"{company} ({attention}/100 — {sector})")
        else:
            no_ats.append(f"{company} (score {attention}/100 — below threshold)")

    return {
        "companies_found": companies,
        "added_ashby": added_ashby,
        "added_greenhouse": added_greenhouse,
        "added_to_radar": added_to_radar,
        "no_ats_found": no_ats,
        "already_known": already,
        "added_ashby_slugs": added_ashby_slugs,
        "added_greenhouse_slugs": added_greenhouse_slugs,
    }
