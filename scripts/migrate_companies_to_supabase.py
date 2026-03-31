"""
Migrate hardcoded ASHBY_COMPANIES + GREENHOUSE_COMPANIES dicts into the companies table.
Run ONCE after adding ashby_slug and greenhouse_slug columns:

  ALTER TABLE companies ADD COLUMN ashby_slug TEXT;
  ALTER TABLE companies ADD COLUMN greenhouse_slug TEXT;
  ALTER TABLE companies ADD COLUMN skip BOOLEAN DEFAULT false;

Run: python scripts/migrate_companies_to_supabase.py
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()
from supabase import create_client

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# Source of truth — hardcoded dicts being retired
ASHBY = {
    "decagon":      "Decagon",
    "sierra":       "Sierra",
    "harvey":       "Harvey",
    "listenlabs":   "Listen Labs",
    "writer":       "Writer",
    "ema":          "Ema",
    "assembledhq":  "Assembled",
    "lindy":        "Lindy AI",
    "nooks":        "Nooks",
    "vanta":        "Vanta",
    "mercor":       "Mercor",
    "paraform":     "Paraform",
    "tavus":        "Tavus",
    "elevenlabs":   "Eleven Labs",
    "vapi":         "Vapi",
    "sesame":       "Sesame",
    "lovable":      "Lovable",
    "casca":        "Casca",
    "juicebox":     "JuiceBox",
    "contextual":   "Contextual AI",
    "bland":        "Bland AI",
    "ramp":         "Ramp",
    "n8n":          "n8n",
    "fathom":       "Fathom",
    "arcade":       "Arcade",
    "rillet":       "Rillet",
    "method":       "Method",
    "atlan":        "Atlan",
    "character":    "Character AI",
    "agentmail":    "AgentMail",
    "artisan":      "Artisan",
}

GREENHOUSE = {
    "gleanwork":    "Glean",
    "hebbia":       "Hebbia",
    "intercom":     "Intercom",
    "humeai":       "Hume",
    "scaleai":      "Scale AI",
    "stripe":       "Stripe",
    "descript":     "Descript",
    "typeface":     "Typeface",
    "pallet":       "Pallet",
}

SKIP = {"Scale AI"}  # companies to skip polling (wrong fit, confirmed)


def run():
    # Load existing companies by name
    res = supabase.table("companies").select("id, name, ashby_slug, greenhouse_slug").execute()
    existing = {r["name"]: r for r in (res.data or [])}

    upserted = 0
    inserted = 0

    # Ashby companies
    for slug, name in ASHBY.items():
        skip = name in SKIP
        if name in existing:
            supabase.table("companies").update({
                "ashby_slug": slug,
                "skip": skip,
            }).eq("name", name).execute()
            print(f"  updated  {name} → ashby_slug={slug}")
            upserted += 1
        else:
            supabase.table("companies").insert({
                "name": name,
                "ashby_slug": slug,
                "skip": skip,
                "source": "manual",
            }).execute()
            print(f"  inserted {name} → ashby_slug={slug}")
            inserted += 1

    # Greenhouse companies
    for slug, name in GREENHOUSE.items():
        skip = name in SKIP
        if name in existing:
            supabase.table("companies").update({
                "greenhouse_slug": slug,
                "skip": skip,
            }).eq("name", name).execute()
            print(f"  updated  {name} → greenhouse_slug={slug}")
            upserted += 1
        else:
            supabase.table("companies").insert({
                "name": name,
                "greenhouse_slug": slug,
                "skip": skip,
                "source": "manual",
            }).execute()
            print(f"  inserted {name} → greenhouse_slug={slug}")
            inserted += 1

    print(f"\nDone. {upserted} updated, {inserted} inserted.")
    print("You can now remove ASHBY_COMPANIES and GREENHOUSE_COMPANIES dicts from agent/discover.py")


if __name__ == "__main__":
    run()
