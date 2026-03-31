"""
LinkedIn Profile Monitor — watches specific curators for new hiring posts.

Tracked profiles post regularly about startups hiring. When a new post is detected,
it runs through the full company extraction + scoring pipeline automatically.

Run standalone: python agent/monitor_linkedin.py
Scheduled: runs every 6 hours via scheduler.py
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv
from apify_client import ApifyClient

load_dotenv()

# ---------------------------------------------------------------------------
# Profiles to monitor
# ---------------------------------------------------------------------------

MONITORED_PROFILES = [
    {
        "name": "Jordan Carver",
        "profile_id": "jordancarver",
        "url": "https://www.linkedin.com/in/jordancarver/",
        "why": "Posts weekly lists of startups that raised $10M+, actively hiring",
    },
    {
        "name": "Anant GT",
        "profile_id": "anantgtcornell",
        "url": "https://www.linkedin.com/in/anantgtcornell/",
        "why": "Posts curated lists of startups hiring across AI/tech",
    },
    {
        "name": "Bella Nazzari",
        "profile_id": "bellanazzari",
        "url": "https://www.linkedin.com/in/bellanazzari/",
        "why": "Runs Open to Work newsletter, posts curated hiring lists from Twitter/X",
    },
    {
        "name": "Jordan Mazer",
        "profile_id": "jordanmazer",
        "url": "https://www.linkedin.com/in/jordanmazer/",
        "why": "Posts about startup hiring and job opportunities",
    },
]

SEEN_PATH = Path(__file__).parent.parent / "data" / "linkedin_seen.json"


def load_seen() -> set:
    if SEEN_PATH.exists():
        return set(json.loads(SEEN_PATH.read_text()))
    return set()


def save_seen(seen: set):
    SEEN_PATH.write_text(json.dumps(list(seen), indent=2))


def fetch_recent_posts(profile_url: str) -> list:
    """Use Apify LinkedIn Posts Scraper to get recent posts from a profile."""
    apify_key = os.getenv("APIFY_API_KEY")
    if not apify_key:
        print("  ✗ No APIFY_API_KEY set")
        return []
    try:
        apify = ApifyClient(apify_key)
        run = apify.actor("curious_coder/linkedin-post-scraper").call(
            run_input={
                "profileUrls": [profile_url],
                "maxPosts": 5,
            }
        )
        return list(apify.dataset(run["defaultDatasetId"]).iterate_items())
    except Exception as e:
        print(f"  ✗ Apify error: {e}")
        return []


def run_linkedin_monitor() -> dict:
    """Check all monitored profiles for new posts. Process any new ones."""
    from agent.discover_from_post import extract_company_names, process_post

    seen = load_seen()
    total_companies = 0
    total_new = 0
    new_posts_found = []

    for profile in MONITORED_PROFILES:
        print(f"\n--- Checking {profile['name']} ---")
        posts = fetch_recent_posts(profile["url"])
        print(f"  {len(posts)} recent posts fetched")

        for post in posts:
            post_id = post.get("id") or post.get("url") or str(post.get("timestamp", ""))
            if not post_id or post_id in seen:
                continue

            text = post.get("text") or post.get("content") or ""
            post_url = post.get("url") or post.get("postUrl") or ""

            if len(text) < 50:
                continue

            # Only process posts that look like hiring lists
            hiring_signals = ["hiring", "startups", "raised", "series", "seed", "looking for", "open roles", "job"]
            if not any(sig in text.lower() for sig in hiring_signals):
                seen.add(post_id)
                continue

            print(f"\n  📌 New hiring post from {profile['name']}:")
            print(f"     {text[:200]}...")

            # Run through full pipeline
            result = process_post(url=post_url or None, text=text)
            companies_found = result.get("companies_found", [])
            added = (
                result.get("added_ashby", []) +
                result.get("added_greenhouse", []) +
                result.get("added_to_radar", [])
            )

            print(f"     Found {len(companies_found)} companies, added {len(added)} new")
            total_companies += len(companies_found)
            total_new += len(added)
            new_posts_found.append({
                "author": profile["name"],
                "text_preview": text[:300],
                "companies_found": len(companies_found),
                "companies_added": len(added),
            })

            seen.add(post_id)

    save_seen(seen)
    print(f"\nLinkedIn monitor done. {len(new_posts_found)} new posts. {total_new} companies added.")
    return {
        "posts_processed": len(new_posts_found),
        "companies_found": total_companies,
        "companies_added": total_new,
        "posts": new_posts_found,
    }


if __name__ == "__main__":
    run_linkedin_monitor()
