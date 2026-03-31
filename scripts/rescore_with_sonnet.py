"""
Rescore companies that scored 0 or have bad what_they_do using Sonnet (knows these companies by name).
Run: python scripts/rescore_with_sonnet.py
"""
import os
import sys
import json
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

import anthropic
from supabase import create_client
from agent.discover_from_rss import RACHITA_PROFILE_SHORT, _extract_sector

s = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Get companies with score <= 10 or "unable" in what_they_do
low = s.table("companies").select("id, name, attention_score, what_they_do").lte("attention_score", 10).execute().data or []
bad_text = s.table("companies").select("id, name, attention_score, what_they_do").ilike("what_they_do", "%unable%").execute().data or []
to_rescore = list({r["id"]: r for r in low + bad_text}.values())
print(f"Rescoring {len(to_rescore)} companies with Sonnet...\n")

for item in to_rescore:
    name = item["name"]
    prompt = f"""You are evaluating whether a startup is worth tracking for Rachita Kumar.

RACHITA PROFILE:
{RACHITA_PROFILE_SHORT}

COMPANY: {name}

Use your knowledge of this company. Score 0-100 for attention worthiness.
- 80-100: Perfect fit, reach out now
- 60-79: Worth watching
- 40-59: Tangential
- 0-39: Not a fit

Return ONLY valid JSON, no markdown:
{{"attention_score": <int>, "what_they_do": "<one sentence describing what they build>", "recommendation": "reach_out_now|watch|drop"}}"""

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()
        result = json.loads(raw)
        attention = result.get("attention_score", 0)
        what = result.get("what_they_do", "")
        sector = _extract_sector(what + " " + name)
        s.table("companies").update({
            "attention_score": attention,
            "what_they_do": what,
            "sector": sector,
        }).eq("id", item["id"]).execute()
        print(f"  {name}: {attention}/100 — {what[:70]}")
    except Exception as e:
        print(f"  ERROR {name}: {e}")
    time.sleep(0.3)

print(f"\nDone. {len(to_rescore)} companies rescored.")
