"""
Backfill radar table: add attention_score, what_they_do, sector, stage, investors
for all existing companies that are missing these fields.

Run: python scripts/backfill_radar.py
"""

import os
import sys
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from supabase import create_client
from agent.discover_from_rss import (
    score_company_for_radar,
    _extract_stage,
    _extract_sector,
    _extract_investors,
    RACHITA_PROFILE_SHORT,
)

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))


def backfill():
    res = supabase.table("radar").select("*").execute()
    companies = res.data or []

    needs_backfill = [
        c for c in companies
        if c.get("attention_score") is None or not c.get("sector")
    ]

    print(f"{len(companies)} total radar companies, {len(needs_backfill)} need backfill\n")

    for i, item in enumerate(needs_backfill):
        name = item["company_name"]
        funding_info = item.get("funding_info", "")
        why_existing = item.get("why_interesting", "")
        source_url = item.get("source_url", "")

        print(f"[{i+1}/{len(needs_backfill)}] {name}")

        # Use existing why_interesting as context for re-scoring
        context = f"{why_existing} {funding_info}"

        try:
            scored = score_company_for_radar(name, funding_info, context)
            attention = scored.get("attention_score", 50)
            what_they_do = scored.get("what_they_do", why_existing)
            rec = scored.get("recommendation", "watch")

            stage = _extract_stage(funding_info + " " + context)
            investors = _extract_investors(context)
            sector = _extract_sector(what_they_do + " " + context)

            update = {
                "attention_score": attention,
                "what_they_do": what_they_do,
                "sector": sector,
                "stage": stage or None,
                "investors": investors or None,
            }

            supabase.table("radar").update(update).eq("id", item["id"]).execute()

            print(f"  score={attention} | {sector} | {stage or 'stage unknown'} | {what_they_do[:60]}")

        except Exception as e:
            print(f"  ERROR: {e}")

        # Small delay to avoid Claude rate limits
        time.sleep(0.5)

    print(f"\nDone. {len(needs_backfill)} companies backfilled.")


if __name__ == "__main__":
    backfill()
