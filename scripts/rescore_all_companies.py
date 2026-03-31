"""
Three-step company cleanup:
  1. Delete obvious non-targets (big tech, clearly wrong fits)
  2. Re-score manual target companies that have score=50 placeholder + no description
  3. Score LinkedIn-sourced "maybe" companies, drop anything below 60

Run: python scripts/rescore_all_companies.py
"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

import anthropic
from supabase import create_client
from agent.discover_from_rss import RACHITA_PROFILE_SHORT, SECTORS, _extract_stage_from_funding, _fetch_feedback_examples, _fetch_skip_examples, web_search_company

s = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# ---------------------------------------------------------------------------
# Step 1: Delete obvious non-targets
# ---------------------------------------------------------------------------

DELETE_LIST = [
    "Airbnb", "Dropbox", "Reddit", "Okta", "Datadog", "Replit", "Notion",
    "Robinhood", "Flexport", "Nabis", "SimplyInsured", "Valerie Health",
    "Metropolis", "Applied Intuition", "Baba", "Eragon",
]

print("=" * 55)
print("STEP 1: Deleting obvious non-targets")
print("=" * 55)
deleted = 0
for name in DELETE_LIST:
    r = s.table("companies").delete().ilike("name", name).execute()
    if r.data:
        print(f"  ✗ Deleted: {name}")
        deleted += 1
    else:
        print(f"  — Not found: {name}")
print(f"\nDeleted {deleted} companies.\n")


# ---------------------------------------------------------------------------
# Shared scoring function
# ---------------------------------------------------------------------------

def score_company(name: str, context: str = "") -> dict:
    """Score a single company with Sonnet. Enriches with web search if needed."""
    if len(context.strip()) < 100:
        print(f"    🔍 Web searching {name}...")
        web_ctx = web_search_company(name)
        if web_ctx:
            context = web_ctx

    feedback_examples = _fetch_feedback_examples()
    skip_examples = _fetch_skip_examples()
    sectors_list = ", ".join(SECTORS)

    prompt = f"""You are evaluating whether a startup is worth tracking for Rachita Kumar.

RACHITA'S PROFILE:
{RACHITA_PROFILE_SHORT}

{feedback_examples}

{skip_examples}

COMPANY: {name}
CONTEXT: {context[:1500]}

Score 0-100 for attention worthiness. Be strict.
Use your own knowledge of this company — you likely know it well.

Also assign the best sector from: {sectors_list}
And the current stage: Pre-Seed, Seed, Series A, Series B, Series C, Series D+, Growth, Public, or empty string.

Return ONLY valid JSON, no markdown:
{{"attention_score": <0-100>, "what_they_do": "<one sentence: what this company builds>", "recommendation": "reach_out_now|watch|drop", "sector": "<from list>", "stage": "<stage or empty>"}}"""

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()
        result = json.loads(raw)
        # Validate sector
        if result.get("sector") not in SECTORS:
            result["sector"] = "Enterprise AI"
        return result
    except Exception as e:
        print(f"    ✗ Scoring error for {name}: {e}")
        return None


# ---------------------------------------------------------------------------
# Step 2: Re-score manual target companies (score=50, no description)
# ---------------------------------------------------------------------------

print("=" * 55)
print("STEP 2: Re-scoring manual target companies")
print("=" * 55)

manual_no_desc = s.table("companies").select(
    "id, name, sector, funding_info, source_url"
).eq("attention_score", 50).eq("source", "manual").execute().data or []

print(f"Found {len(manual_no_desc)} manual companies with placeholder score.\n")

rescored = 0
for item in manual_no_desc:
    name = item["name"]
    print(f"  → {name}")
    result = score_company(name)
    if not result:
        continue

    score = result["attention_score"]
    what = result["what_they_do"]
    sector = result["sector"]
    stage = result.get("stage", "")

    s.table("companies").update({
        "attention_score": score,
        "what_they_do": what,
        "sector": sector,
        "stage": stage or None,
    }).eq("id", item["id"]).execute()

    print(f"     {score}/100 · {sector} · {stage} — {what[:65]}")
    rescored += 1
    time.sleep(0.3)

print(f"\nRescored {rescored} manual companies.\n")


# ---------------------------------------------------------------------------
# Step 3: Score LinkedIn "maybe" companies (no score, no description)
# ---------------------------------------------------------------------------

print("=" * 55)
print("STEP 3: Scoring LinkedIn-sourced maybe companies")
print("=" * 55)

MAYBE_LIST = [
    "Mercury", "Valon", "Perplexity", "truthsystems", "Legora",
    "Gumloop", "Ambrook", "Bluedot", "Glimpse", "Overtone",
    "Runlayer", "Serval", "Virio", "Active Site",
    # Plus any other linkedin_apify with no score
]

# Also catch any remaining linkedin_apify companies with no score
remaining = s.table("companies").select(
    "id, name, source"
).eq("source", "linkedin_apify").is_("attention_score", "null").execute().data or []
remaining_names = [r["name"] for r in remaining if r["name"] not in MAYBE_LIST + DELETE_LIST]
all_maybes = MAYBE_LIST + remaining_names

# Filter to only ones that still exist
existing = s.table("companies").select("id, name").execute().data or []
existing_names = {r["name"] for r in existing}
to_score = [n for n in all_maybes if n in existing_names]

print(f"Scoring {len(to_score)} LinkedIn-sourced companies...\n")

kept = dropped = 0
for name in to_score:
    print(f"  → {name}")
    result = score_company(name)
    if not result:
        continue

    score = result["attention_score"]
    what = result["what_they_do"]
    sector = result["sector"]
    stage = result.get("stage", "")
    rec = result.get("recommendation", "drop")

    if rec == "drop" or score < 60:
        s.table("companies").delete().ilike("name", name).execute()
        print(f"     {score}/100 — DROPPED ({sector}): {what[:50]}")
        dropped += 1
    else:
        s.table("companies").update({
            "attention_score": score,
            "what_they_do": what,
            "sector": sector,
            "stage": stage or None,
            "radar_status": "watching",
        }).ilike("name", name).execute()
        print(f"     {score}/100 · {sector} · {stage} — KEPT: {what[:55]}")
        kept += 1
    time.sleep(0.3)

print(f"\nKept {kept}, dropped {dropped} LinkedIn companies.")
print("\n✅ All done.")
