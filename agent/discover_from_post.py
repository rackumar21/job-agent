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
    """Use Claude to extract company names from post text or plain company name input."""
    prompt = f"""Extract all company names from the text below.

The input may be:
- A LinkedIn or Twitter post mentioning hiring startups
- A plain list of company names (one per line, comma separated, or space separated)
- A single company name typed directly (e.g. "Cekura" or "Klarity AI")

TEXT:
{text[:8000]}

Rules:
- If the input looks like a plain company name or list of names, return them directly
- Resolve Twitter/X handles to company names (e.g. @warpdotco → Warp, @hedra_labs → Hedra)
- Exclude: individual people's names, VCs/investors, generic words like "startup" or "company"
- Only include actual company names, not roles or job titles

Return ONLY a JSON array of company name strings. No markdown, no explanation.
Example: ["Warp", "Anthropic", "Kaizen"]
If nothing looks like a company name, return [].
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

    added = []       # newly added to DB
    already = []     # already tracked

    for company in companies:
        if is_already_tracked(company):
            already.append(company)
            continue

        # Find ATS slugs (no score gate — pipeline handles scoring)
        ashby_slug = find_ashby_slug(company)
        gh_slug = None if ashby_slug else find_greenhouse_slug(company)

        row = {
            "name": company,
            "source": "post",
            "radar_status": "watching",
        }
        if ashby_slug:
            row["ashby_slug"] = ashby_slug
        if gh_slug:
            row["greenhouse_slug"] = gh_slug

        try:
            supabase.table("companies").insert(row).execute()
            added.append(company)
        except Exception:
            already.append(company)  # likely duplicate

    return {
        "companies_found": companies,
        "added": added,
        "already_known": already,
        # Legacy keys for backward compat
        "added_ashby": added,
        "added_greenhouse": [],
        "added_to_radar": [],
        "no_ats_found": [],
        "added_ashby_slugs": {},
        "added_greenhouse_slugs": {},
    }
