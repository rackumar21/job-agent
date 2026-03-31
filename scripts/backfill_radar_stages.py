"""
Backfill radar table with stage, investors, and funding_info from web research.
Run: python scripts/backfill_radar_stages.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()
from supabase import create_client

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

STAGE_DATA = {
    "Gynger":               {"stage": "Series A", "investors": "PayPal Ventures, Gradient Ventures",                "funding_info": "$20M Series A, Jun 2024"},
    "Momentic":             {"stage": "Series A", "investors": "Standard Capital, Dropbox Ventures, YC",            "funding_info": "$15M Series A, Nov 2025"},
    "Dryft":                {"stage": "Seed",     "investors": "General Catalyst, Neo",                             "funding_info": "$5M Seed, Nov 2025"},
    "Sphinx":               {"stage": "Seed",     "investors": "Cherry Ventures, YC, Rebel Fund",                   "funding_info": "$7.1M Seed, Feb 2026"},
    "Fibr AI":              {"stage": "Seed",     "investors": "Accel, WillowTree Ventures",                        "funding_info": "$7.5M Seed (Accel-led)"},
    "Sim Studio":           {"stage": "Series A", "investors": "Standard Capital, Perplexity Fund, SV Angel, YC",   "funding_info": "$7M Series A, Nov 2025"},
    "Obin AI":              {"stage": "Seed",     "investors": "Motive Partners, Fei-Fei Li (angel)",               "funding_info": "$7M Seed, Mar 2026"},
    "Arva":                 {"stage": "Seed",     "investors": "Google Gradient, YC, Amino Capital",               "funding_info": "$3M Seed, Jan 2025"},
    "duvo.ai":              {"stage": "Seed",     "investors": "Index Ventures, Northzone, Credo Ventures",         "funding_info": "$15M Seed, Dec 2025"},
    "Runlayer":             {"stage": "Seed",     "investors": "Khosla Ventures (Keith Rabois), Felicis",           "funding_info": "$11M Seed, Nov 2025"},
    "1mind":                {"stage": "Series A", "investors": "Battery Ventures, Primary Ventures, Wing VC",       "funding_info": "$40M total, Series A Nov 2025"},
    "AIR Platforms":        {"stage": "Seed",     "investors": "Work-Bench Ventures, Lerer Hippeau",                "funding_info": "$6.1M Seed, Dec 2025"},
    "Adam":                 {"stage": "Seed",     "investors": "TQ Ventures, YC",                                   "funding_info": "$4.1M Seed, Oct 2025"},
    "Trigger.dev":          {"stage": "Series A", "investors": "Standard Capital, YC, Rebel Fund",                  "funding_info": "$16M Series A, Dec 2025"},
    "truthsystems":         {"stage": "Seed",     "investors": "Gradient, Lightspeed, F-Prime, YC, a16z Scout",     "funding_info": "$4M Seed, Oct 2025"},
    "Asymmetric Security":  {"stage": "Pre-Seed", "investors": "Susa Ventures, Halcyon Ventures",                   "funding_info": "$4.2M Pre-Seed, Jan 2026"},
    "Endra":                {"stage": "Seed",     "investors": "Notion Capital, Norrsken VC",                       "funding_info": "$20M Seed, Dec 2025"},
    "Wonderful":            {"stage": "Series B", "investors": "Insight Partners, Index Ventures, IVP, Bessemer",   "funding_info": "$150M Series B, 2026 ($2B valuation)"},
    "Genspark":             {"stage": "Series B", "investors": "Emergence Capital, SBI Investment, LG Technology",  "funding_info": "$275M+ Series B, Nov 2025"},
    "Tempo":                {"stage": "Series A", "investors": "Thrive Capital, Greenoaks, Sequoia, Ribbit Capital", "funding_info": "$500M Series A, Oct 2025 ($5B valuation)"},
    "TwinMind":             {"stage": "Seed",     "investors": "Streamlined Ventures, Sequoia",                     "funding_info": "$5.7M Seed, Sep 2025"},
    "HeyGen":               {"stage": "Series A", "investors": "Benchmark, Thrive Capital, BOND, SV Angel",         "funding_info": "$60M Series A, Jun 2024 ($500M valuation)"},
    "OpenFX":               {"stage": "Seed",     "investors": "Accel, NFX, Lightspeed Faction, Castle Island",     "funding_info": "$23M Seed, May 2025"},
    "Replit":               {"stage": "Series D", "investors": "Georgian, Prysm Capital, a16z, Coatue",             "funding_info": "$400M Series D, Jan 2026 ($9B valuation)"},
}

# False positives in radar to flag — no stage data applies
FALSE_POSITIVES = ["Claude", "next play", "MXV Capital"]

def run():
    res = supabase.table("radar").select("id, company_name").execute()
    companies = {r["company_name"]: r["id"] for r in res.data}

    updated = 0
    for company, data in STAGE_DATA.items():
        if company in companies:
            supabase.table("radar").update({
                "stage": data["stage"],
                "investors": data["investors"],
                "funding_info": data["funding_info"],
            }).eq("id", companies[company]).execute()
            print(f"  {company}: {data['stage']} — {data['funding_info']}")
            updated += 1
        else:
            print(f"  ? not found: {company}")

    print(f"\nUpdated {updated} companies.")
    print(f"\nFalse positives to delete from radar: {', '.join(FALSE_POSITIVES)}")
    print("Delete these manually in the Supabase dashboard or run:")
    for fp in FALSE_POSITIVES:
        if fp in companies:
            print(f"  supabase.table('radar').delete().eq('id', '{companies[fp]}').execute()")

if __name__ == "__main__":
    run()
