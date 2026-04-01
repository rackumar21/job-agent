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
    """Try common slug patterns on Ashby, Greenhouse, Lever, and Workable."""
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

    def try_lever(s):
        try:
            r = httpx.get(f"https://api.lever.co/v0/postings/{s}", timeout=3)
            if r.status_code == 200 and isinstance(r.json(), list):
                return ("lever", s)
        except Exception:
            pass
        return None

    def try_workable(s):
        try:
            r = httpx.get(f"https://apply.workable.com/api/v1/widget/accounts/{s}", timeout=3)
            if r.status_code == 200 and r.json().get("jobs") is not None:
                return ("workable", s)
        except Exception:
            pass
        return None

    with ThreadPoolExecutor(max_workers=16) as pool:
        futures = []
        for s in slugs_to_try:
            futures.append(pool.submit(try_ashby, s))
            futures.append(pool.submit(try_greenhouse, s))
            futures.append(pool.submit(try_lever, s))
            futures.append(pool.submit(try_workable, s))
        for f in as_completed(futures):
            result = f.result()
            if result and result[0] not in found:
                found[result[0]] = result[1]
    return found


def _poll_lever(company_name: str, company_id: str, slug: str) -> list:
    """Poll Lever for PM/ops roles."""
    import httpx, re
    try:
        r = httpx.get(f"https://api.lever.co/v0/postings/{slug}", timeout=8)
        if r.status_code != 200:
            return []
        jobs = r.json()
        from agent.discover import get_role_type, passes_location_filter, save_job
        new_roles = []
        for job in jobs:
            title = job.get("text", "")
            location = job.get("categories", {}).get("location", "")
            url = job.get("hostedUrl", "")
            jd_text = re.sub(r"<[^>]+>", " ", job.get("descriptionPlain", "") or job.get("description", ""))[:4000]
            role_type = get_role_type(title)
            if not role_type or not passes_location_filter(location):
                continue
            saved = save_job(company_name, company_id, title, url, "lever", role_type, jd_text)
            if saved:
                new_roles.append({"company": company_name, "title": title})
        return new_roles
    except Exception:
        return []


def _poll_workable(company_name: str, company_id: str, slug: str) -> list:
    """Poll Workable for PM/ops roles."""
    import httpx
    try:
        r = httpx.get(f"https://apply.workable.com/api/v1/widget/accounts/{slug}", timeout=8)
        if r.status_code != 200:
            return []
        jobs = r.json().get("jobs", [])
        from agent.discover import get_role_type, passes_location_filter, save_job
        new_roles = []
        for job in jobs:
            title = job.get("title", "")
            location = job.get("city", "") + ", " + job.get("country", "")
            url = job.get("url", "") or f"https://apply.workable.com/{slug}/j/{job.get('shortcode', '')}/"
            jd_text = job.get("description", "")[:4000]
            role_type = get_role_type(title)
            if not role_type or not passes_location_filter(location):
                continue
            saved = save_job(company_name, company_id, title, url, "workable", role_type, jd_text)
            if saved:
                new_roles.append({"company": company_name, "title": title})
        return new_roles
    except Exception:
        return []


def _web_search_careers(company_name: str, company_id: str) -> list:
    """Fallback: web search for PM roles at a company when no ATS found."""
    import anthropic, os, json
    try:
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": f"""Search for open Product Manager, Strategy, or Operations roles at {company_name}.

Check their careers page, LinkedIn, and job boards. Return ONLY a JSON array of jobs found:
[{{"title": "...", "url": "..."}}]

If no relevant PM/strategy/ops roles found, return [].
No markdown, no explanation."""}],
        )
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        jobs = json.loads(raw)
        if not jobs:
            return []
        from agent.discover import save_job
        new_roles = []
        for job in jobs[:3]:
            title = job.get("title", "")
            url = job.get("url", "")
            if title and url:
                saved = save_job(company_name, company_id, title, url, "web_search", "pm", "")
                if saved:
                    new_roles.append({"company": company_name, "title": title})
        return new_roles
    except Exception:
        return []


def _process_one_company(name: str, rescore: bool = False, force_search: bool = False) -> dict:
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
    lever_slug      = co.get("lever_slug")
    workable_slug   = co.get("workable_slug")
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

    # Step 2: Low-scoring companies skip job search (unless manually added)
    if attn < RADAR_THRESHOLD and not force_search:
        return {"status": "radar", "company": name, "score": attn}

    # Step 2b: Auto-discover ATS slugs if missing
    if not ashby_slug and not greenhouse_slug and not lever_slug and not workable_slug:
        discovered = _discover_ats_slugs(name)
        for ats, slug_val in discovered.items():
            if ats == "ashby" and not ashby_slug:
                ashby_slug = slug_val
            elif ats == "greenhouse" and not greenhouse_slug:
                greenhouse_slug = slug_val
            elif ats == "lever" and not lever_slug:
                lever_slug = slug_val
            elif ats == "workable" and not workable_slug:
                workable_slug = slug_val
        slug_updates = {}
        if ashby_slug: slug_updates["ashby_slug"] = ashby_slug
        if greenhouse_slug: slug_updates["greenhouse_slug"] = greenhouse_slug
        if lever_slug: slug_updates["lever_slug"] = lever_slug
        if workable_slug: slug_updates["workable_slug"] = workable_slug
        if slug_updates:
            supabase.table("companies").update(slug_updates).eq("id", co["id"]).execute()

    # Step 3: Poll for open roles
    roles = []
    if ashby_slug or greenhouse_slug:
        roles = poll_specific_companies(
            ashby_slugs=[ashby_slug] if ashby_slug else [],
            greenhouse_slugs=[greenhouse_slug] if greenhouse_slug else [],
        )
    if not roles and lever_slug:
        roles = _poll_lever(name, co["id"], lever_slug)
    if not roles and workable_slug:
        roles = _poll_workable(name, co["id"], workable_slug)
    # Fallback: web search for careers page if no ATS found
    if not roles and not ashby_slug and not greenhouse_slug and not lever_slug and not workable_slug:
        roles = _web_search_careers(name, co["id"])

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


def run_pipeline_for_companies(company_names: list, rescore: bool = False, force_search: bool = True) -> dict:
    """
    Run the full pipeline for a specific list of companies (by name).
    Processes up to 4 companies in parallel for speed.
    force_search=True (default for manual runs): always search for jobs even if score is low.
    """
    from agent.score import score_new_jobs

    results: dict = {"open_roles": [], "radar_added": [], "skipped": []}
    has_new_roles = False

    with ThreadPoolExecutor(max_workers=4) as pool:
        future_to_name = {
            pool.submit(_process_one_company, name, rescore, force_search): name
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
