"""
One-time cleanup: mark jobs with non-US location as skip.
Checks score_breakdown.location_fit <= 2 OR score_reasoning mentions non-US locations.
Run: python scripts/cleanup_locations.py
"""
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

NON_US_SIGNALS = [
    "stockholm", "sweden", "berlin", "germany", "london", "uk", "europe",
    "amsterdam", "netherlands", "paris", "france", "zurich", "switzerland",
    "copenhagen", "denmark", "oslo", "norway", "helsinki", "finland",
    "toronto", "canada", "sydney", "australia", "singapore", "india",
    "bangalore", "bengaluru", "tokyo", "japan",
]

def run():
    res = supabase.table("jobs").select(
        "id, company_name, title, score_breakdown, score_reasoning, status"
    ).neq("status", "skip").execute()

    jobs = res.data or []
    print(f"Checking {len(jobs)} active jobs for non-US location...\n")

    skipped = 0
    for job in jobs:
        bd = job.get("score_breakdown") or {}
        location_fit = bd.get("location_fit")
        reasoning = (job.get("score_reasoning") or "").lower()

        should_skip = False
        reason = ""

        if location_fit is not None and location_fit <= 2:
            should_skip = True
            reason = f"location_fit={location_fit}"

        if not should_skip:
            for signal in NON_US_SIGNALS:
                if signal in reasoning:
                    should_skip = True
                    reason = f"'{signal}' in reasoning"
                    break

        if should_skip:
            supabase.table("jobs").update({"status": "skip"}).eq("id", job["id"]).execute()
            print(f"  SKIPPED [{job['company_name']}] {job['title']} — {reason}")
            skipped += 1

    print(f"\nDone. {skipped} jobs marked as skip.")

if __name__ == "__main__":
    run()
