"""
pipeline.py — Full end-to-end pipeline for a targeted list of companies.

Sequence:
  1. Score company (attention score) — skip if < 55
  2. Poll Ashby / Greenhouse for open roles (if company has slugs)
  3. Roles found   → score each role  → appear in Open Roles
  4. No roles      → generate outreach draft → appear in On Radar

Call run_pipeline_for_companies(names) with a list of company names that are
already in the companies table.
"""

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

RADAR_THRESHOLD = 40


def _discover_ats_slugs(name: str) -> dict:
    """Try common slug patterns on Ashby and Greenhouse to find a company's ATS."""
    import httpx
    slug = name.lower().replace(" ", "").replace("-", "").replace(".", "").replace(",", "")
    slug_hyphen = name.lower().replace(" ", "-").replace(".", "").replace(",", "")
    slugs_to_try = list(dict.fromkeys([slug, slug_hyphen, slug.replace("ai", ""), slug + "ai"]))
    found = {}

    def try_ashby(s):
        try:
            r = httpx.get(f"https://api.ashbyhq.com/posting-api/job-board/{s}", timeout=3)
            if r.status_code == 200 and r.json().get("jobs") is not None:
                return ("ashby", s)
        except Exception:
            pass
        return None

    def try_greenhouse(s):
        try:
            r = httpx.get(f"https://boards-api.greenhouse.io/v1/boards/{s}/jobs/", timeout=3)
            if r.status_code == 200:
                return ("greenhouse", s)
        except Exception:
            pass
        return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = []
        for s in slugs_to_try:
            futures.append(pool.submit(try_ashby, s))
            futures.append(pool.submit(try_greenhouse, s))
        for f in as_completed(futures):
            result = f.result()
            if result and result[0] not in found:
                found[result[0]] = result[1]
    return found


def _process_one_company(name: str, rescore: bool = False) -> dict:
    """Process a single company through the full pipeline."""
    from agent.discover_from_rss import score_company_for_radar, generate_relationship_message
    from agent.discover import poll_specific_companies

    rows = supabase.table("companies").select("*").eq("name", name).execute().data or []
    if not rows:
        return {"status": "not_found", "company": name}
    co = rows[0]

    what            = co.get("what_they_do") or ""
    ashby_slug      = co.get("ashby_slug")
    greenhouse_slug = co.get("greenhouse_slug")
    attn            = co.get("attention_score")

    # Step 1: Score company
    if attn is None or rescore:
        scored = score_company_for_radar(
            name,
            co.get("funding_info") or "",
            what,
        )
        attn = scored.get("attention_score", 0)
        updates: dict = {"attention_score": attn}
        if scored.get("what_they_do"):
            updates["what_they_do"] = scored["what_they_do"]
            what = scored["what_they_do"]
        if scored.get("sector"):
            updates["sector"] = scored["sector"]
        if scored.get("stage"):
            updates["stage"] = scored["stage"]
        supabase.table("companies").update(updates).eq("id", co["id"]).execute()

    # Step 2: Low-scoring companies still go to Radar (with details) but skip job search
    if attn < RADAR_THRESHOLD:
        return {"status": "radar", "company": name, "score": attn}

    # Step 2b: Auto-discover ATS slugs if missing
    if not ashby_slug and not greenhouse_slug:
        discovered = _discover_ats_slugs(name)
        if discovered.get("ashby"):
            ashby_slug = discovered["ashby"]
            supabase.table("companies").update({"ashby_slug": ashby_slug}).eq("id", co["id"]).execute()
        if discovered.get("greenhouse"):
            greenhouse_slug = discovered["greenhouse"]
            supabase.table("companies").update({"greenhouse_slug": greenhouse_slug}).eq("id", co["id"]).execute()

    # Step 3: Poll for open roles
    roles = []
    if ashby_slug or greenhouse_slug:
        roles = poll_specific_companies(
            ashby_slugs=[ashby_slug] if ashby_slug else [],
            greenhouse_slugs=[greenhouse_slug] if greenhouse_slug else [],
        )

    if roles:
        return {"status": "open_roles", "company": name, "roles": roles}
    else:
        if not co.get("relationship_message"):
            draft = generate_relationship_message(
                name,
                what,
                co.get("funding_info") or "",
            )
            supabase.table("companies").update(
                {"relationship_message": draft}
            ).eq("id", co["id"]).execute()
        return {"status": "radar", "company": name, "score": attn}


def run_pipeline_for_companies(company_names: list, rescore: bool = False) -> dict:
    """
    Run the full pipeline for a specific list of companies (by name).
    Processes up to 4 companies in parallel for speed.
    """
    from agent.score import score_new_jobs

    results: dict = {"open_roles": [], "radar_added": [], "skipped": []}
    has_new_roles = False

    with ThreadPoolExecutor(max_workers=4) as pool:
        future_to_name = {
            pool.submit(_process_one_company, name, rescore): name
            for name in company_names
        }
        for future in as_completed(future_to_name):
            try:
                r = future.result()
                if r["status"] == "skipped":
                    results["skipped"].append({"company": r["company"], "score": r["score"]})
                elif r["status"] == "open_roles":
                    results["open_roles"].extend(r["roles"])
                    has_new_roles = True
                elif r["status"] == "radar":
                    results["radar_added"].append({"company": r["company"], "score": r["score"]})
            except Exception:
                pass

    # Score any new jobs that were found (once, after all polling)
    if has_new_roles:
        score_new_jobs(limit=50)

    return results
