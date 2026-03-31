"""
Re-backfill radar sectors with corrected taxonomy.
Run: python scripts/backfill_radar_sectors.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()
from supabase import create_client

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

SECTORS = {
    "Gynger":               "Fintech",           # embedded financing / payments for tech purchasing
    "Momentic":             "Developer tools",   # AI-powered software testing / QA
    "The General Intelligence Company of New York": "Enterprise AI",
    "Unlimited Industries": "Industrial AI",     # construction automation
    "Dryft":                "Industrial AI",     # manufacturing operations AI
    "Sphinx":               "Fintech",           # AML / KYC compliance agents for banks
    "Fibr AI":              "Enterprise AI",     # agentic web personalization
    "Northstar":            "Fintech",           # AI finance / data platform
    "Sim Studio":           "Developer tools",   # open-source AI agent workflow builder
    "Tutor":                "Enterprise AI",
    "Obin AI":              "AI employees",      # agentic workforce for financial institutions
    "Arva":                 "Fintech",           # AML / KYB / KYC compliance agents
    "duvo.ai":              "AI employees",      # AI workforce for retail operations
    "Runlayer":             "Developer tools",   # MCP security + enterprise infrastructure
    "1mind":                "AI employees",      # AI superhumans for sales / revenue
    "AIR Platforms":        "Fintech",           # AI credit ratings
    "Adam":                 "Developer tools",   # AI CAD / 3D design copilot
    "Trigger.dev":          "Developer tools",   # background jobs / AI task workflows
    "truthsystems":         "Legal AI",          # AI governance for law firms
    "Asymmetric Security":  "Cybersecurity AI",  # AI incident response and forensics
    "Endra":                "Industrial AI",     # MEP design automation
    "Wonderful":            "AI employees",      # AI customer service agents at scale
    "Genspark":             "Enterprise AI",     # AI workspace / productivity suite
    "Tempo":                "Fintech",           # blockchain payments (Stripe-backed)
    "TwinMind":             "Enterprise AI",     # AI second brain / meeting assistant
    "HeyGen":               "Video AI",          # text-to-video, AI avatar
    "OpenFX":               "Fintech",           # real-time cross-border FX payments
    "Replit":               "Vibe coding",       # AI coding platform / app builder
}

def run():
    res = supabase.table("radar").select("id, company_name, sector").execute()
    companies = {r["company_name"]: r for r in res.data}

    updated = 0
    for company, sector in SECTORS.items():
        if company in companies:
            old = companies[company].get("sector") or "none"
            supabase.table("radar").update({"sector": sector}).eq("id", companies[company]["id"]).execute()
            print(f"  {company}: {old} → {sector}")
            updated += 1
        else:
            print(f"  ? not found: {company}")

    print(f"\nDone. {updated} companies updated.")

if __name__ == "__main__":
    run()
