"""
Loads companies directly into Supabase.
Run once: python scripts/load_companies.py
"""

import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

COMPANIES = [
    # name, tier, domain, stage, funding, india_angle, hiring_status, no_list
    # TIER 1 — Top targets
    ("Decagon", 1, "conversational_ai", "Series D", "$481M", False, "yes", False),
    ("Sierra", 1, "conversational_ai", "Series C", "$635M", False, "yes", False),
    ("Harvey", 1, "legal_ai", "Series E", "$806M", False, "yes", False),
    ("Listen Labs", 1, "research_ai", "Series B", "$96M", False, "yes", False),
    ("Glean", 1, "knowledge_ai", "Series F", "$768M", True, "yes", False),
    ("Hebbia", 1, "document_ai", "Series B", "$161M", False, "yes", False),
    ("Writer", 1, "enterprise_ai", "Series C", "$326M", False, "yes", False),

    # APPLIED — currently in pipeline
    ("Tavus", 2, "video_ai", "Series B", "$80M", False, "yes", False),
    ("Ema", 2, "enterprise_ai", "Series A", "$75M", True, "yes", False),
    ("Hume", 2, "voice_ai", "Series B", "$77M", False, "yes", False),
    ("Assembled", 2, "conversational_ai", "Series B", "$91M", False, "yes", False),
    ("EarnIn", 2, "fintech", "Series D", "$600M+", False, "yes", False),
    ("Plaid", 2, "fintech", "Series D", "$734M", False, "yes", False),
    ("Pallet", 2, "hr_ai", "Series A", "$15M", False, "yes", False),
    ("Klarity", 2, "document_ai", "Series B", "$50M", False, "yes", False),
    ("Alex", 2, "hr_ai", "Series A", "$20M", False, "yes", False),
    ("Air Apps", 2, "productivity_ai", "Series A", "$36M", False, "yes", False),
    ("Gem", 2, "hr_ai", "Series C", "$100M", False, "yes", False),
    ("Voice Cursor", 2, "voice_ai", "Seed", None, False, "yes", False),
    ("JuiceBox", 2, "hr_ai", "Series A", "$16M", False, "yes", False),
    ("HappyRobot", 2, "conversational_ai", "Series A", "$15M", False, "yes", False),
    ("Mercor", 2, "hr_ai", "Series C", "$482M", False, "yes", False),
    ("Paraform", 2, "hr_ai", "Series A", "$20M", False, "yes", False),
    ("Casca", 2, "fintech", "Series A", "$10M", False, "yes", False),
    ("Raspberry AI", 2, "other", "Series A", "$24M", False, "yes", False),
    ("Harper", 2, "fintech", "Series A", "$47M", False, "yes", False),
    ("Nooks", 2, "sales_ai", "Series B", "$43M", False, "yes", False),
    ("GigaAi", 2, "voice_ai", "Series A", "$61M", True, "yes", False),
    ("Character AI", 2, "productivity_ai", "Series C", "$150M", False, "yes", False),
    ("Supio", 2, "legal_ai", "Series A", "$25M", False, "yes", False),
    ("Tarro", 2, "other", "Series B", "$50M", False, "yes", False),
    ("Scale AI", 2, "enterprise_ai", "Series F", "$1.6B", False, "yes", False),
    ("Tessera Labs", 2, "enterprise_ai", "unknown", None, False, "yes", False),
    ("Arcade", 2, "productivity_ai", "Series B", "$30M", False, "yes", False),
    ("Accordion", 2, "fintech", "Series B", "$100M", False, "yes", False),
    ("Rillet", 2, "fintech", "Series A", "$18M", False, "yes", False),
    ("Typeface", 2, "marketing_ai", "Series B", "$165M", False, "yes", False),
    ("Rippling", 2, "hr_ai", "Series G", "$1.2B", False, "yes", False),
    ("Zearch", 2, "enterprise_ai", "Seed", None, False, "yes", False),
    ("Zingroll", 2, "other", "unknown", None, False, "yes", False),
    ("Bounce", 2, "other", "unknown", None, False, "yes", False),
    ("Method", 2, "fintech", "Series B", "$41M", False, "yes", False),
    ("AgentMail", 2, "enterprise_ai", "Series A", "$8M", False, "no", False),
    ("Littlebird", 2, "hr_ai", "Series A", "$10M", False, "no", False),

    # WATCHING
    ("OpenAI", 3, "enterprise_ai", "private", "$17B", False, "unknown", False),
    ("Stripe", 3, "fintech", "private", "$9.4B", False, "unknown", False),
    ("Ramp", 3, "fintech", "Series F", "$1.7B", False, "unknown", False),
    ("Eleven Labs", 3, "voice_ai", "Series D", "$781M", False, "no", False),
    ("Vapi", 3, "voice_ai", "Series A", "$22M", False, "no", False),
    ("Sesame", 3, "voice_ai", "Series B", "$250M", False, "no", False),
    ("Lovable", 3, "vibe_coding", "Series C", "$330M", False, "no", False),
    ("Descript", 3, "video_ai", "Series C", "$100M", False, "unknown", False),

    # NO OPEN ROLE — check back
    ("Norm AI", 2, "legal_ai", "Series C", "$201M", False, "no", False),
    ("Contextual AI", 2, "enterprise_ai", "Series A", "$100M", False, "no", False),
    ("Vanta", 2, "enterprise_ai", "Series D", "$504M", False, "no", False),
    ("Ironclad", 2, "legal_ai", "Series E", "$333M", False, "no", False),
    ("Bland AI", 2, "voice_ai", "Series B", "$62M", False, "no", False),
    ("Oscilar", 2, "fintech", "seed", "$20M", False, "no", False),
    ("Clay", 2, "sales_ai", "Series B", "$62M", False, "no", False),
    ("Atlan", 2, "data_ai", "Series C", "$206M", True, "no", False),
    ("Rogo", 2, "fintech", "Series C", "$165M", False, "no", False),
    ("FurtherAI", 2, "fintech", "Series A", "$25M", True, "no", False),
    ("WisdomAI", 2, "data_ai", "Series A", "$50M", True, "no", False),
    ("Sequence", 2, "fintech", "Series A", "$20M", False, "no", False),
    ("Lindy AI", 2, "workflow_ai", "Series B", "$49.9M", False, "no", False),
    ("Fireflies.ai", 2, "meeting_ai", "unicorn", None, True, "no", False),
    ("Fathom", 2, "meeting_ai", "Series A", "$17M", False, "no", False),
    ("n8n", 2, "workflow_ai", "Series C", "$240M", False, "no", False),
    ("Intercom", 2, "conversational_ai", "Series D", "$240M", False, "unknown", False),

    # NO LIST — excluded
    ("Greptile", 2, "coding_ai", "Series A", "$25M", False, "yes", True),
    ("Abridge", 2, "health_ai", "Series E", "$800M", False, "yes", True),
    ("Hippocratic AI", 2, "health_ai", "Series C", "$404M", False, "yes", True),
    ("Augment Code", 2, "coding_ai", "Series B", "$252M", False, "yes", True),
    ("Cognition", 2, "coding_ai", "Series C", "$900M", False, "yes", True),
    ("Poolside", 2, "coding_ai", "Series B", "$500M", False, "yes", True),
    ("Snorkel AI", 2, "data_ai", "Series D", "$237M", False, "yes", True),
    ("Anyscale", 2, "other", "Series C", "$99M", False, "yes", True),
    ("Groq", 2, "other", "Series C", "$1.3B", False, "yes", True),
]

# Application status map
APP_STATUS = {
    "Decagon": "applied", "Sierra": "applied", "Listen Labs": "applied",
    "Glean": "rejected", "Ema": "applied", "Hume": "applied",
    "Assembled": "applied", "EarnIn": "applied", "Plaid": "applied",
    "Pallet": "applied", "Klarity": "applied", "Alex": "applied",
    "Air Apps": "applied", "Gem": "applied", "Voice Cursor": "applied",
    "JuiceBox": "applied", "HappyRobot": "applied", "Mercor": "applied",
    "Paraform": "applied", "Casca": "applied", "Raspberry AI": "applied",
    "Harper": "applied", "Nooks": "applied", "Sierra": "applied",
    "GigaAi": "applied", "Character AI": "applied", "Supio": "applied",
    "Tarro": "applied", "Scale AI": "applied", "Tessera Labs": "applied",
    "Arcade": "applied", "Accordion": "applied", "Rillet": "applied",
    "Typeface": "applied", "Rippling": "applied", "Zearch": "applied",
    "Zingroll": "applied", "Bounce": "applied", "Method": "applied",
    "Tavus": "applied", "Cartesia": "rejected", "Outset": "rejected",
    "Leena AI": "interviewing",
}

def load():
    inserted = 0
    for row in COMPANIES:
        name, tier, domain, stage, funding, india, hiring, no_list = row

        app_status = APP_STATUS.get(name)
        notes = f"Application status: {app_status}" if app_status else None

        data = {
            "name": name,
            "tier": tier,
            "domain": domain,
            "stage": stage,
            "funding_amount": funding,
            "india_angle": india,
            "hiring_status": hiring,
            "no_list": no_list,
            "no_list_reason": "excluded per preferences" if no_list else None,
            "source": "manual",
        }

        try:
            supabase.table("companies").upsert(data, on_conflict="name").execute()
            status = "NO LIST" if no_list else app_status or "watching"
            print(f"  ✓ {name} [{status}]")
            inserted += 1
        except Exception as e:
            print(f"  ✗ {name}: {e}")

    # Also add Leena AI (interviewing)
    supabase.table("companies").upsert({
        "name": "Leena AI",
        "tier": 1,
        "domain": "enterprise_ai",
        "stage": "Series B",
        "funding_amount": "$30M",
        "india_angle": True,
        "hiring_status": "yes",
        "no_list": False,
        "source": "manual",
    }, on_conflict="name").execute()
    print(f"  ✓ Leena AI [interviewing]")
    inserted += 1

    print(f"\nDone. {inserted} companies loaded into Supabase.")

if __name__ == "__main__":
    print("Loading companies into Supabase...")
    load()
