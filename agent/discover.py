"""
Discovery module — finds new jobs from multiple sources.
Run standalone: python agent/discover.py
"""

import os
import re
import httpx
from dotenv import load_dotenv
from supabase import create_client
from datetime import datetime
from apify_client import ApifyClient

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# PM titles to include
INCLUDE_PM_TITLES = [
    "product manager", "senior product manager", "sr. product manager",
    "founding pm", "founding product manager", "head of product",
    "product lead", "staff pm",
]
EXCLUDE_PM_TITLES = [
    "principal product manager", "group product manager",
    "director of product", "vp of product", "associate product manager",
    "apm", "product analyst", "product marketing",
    "staff product manager",  # seniority bar too high
    "apac", "emea", "latam", "international",  # regional roles, wrong geography focus
    "new grad", "intern",
]

# Generalist/operator titles that fit Rachita's profile
# (finance background + builder + strategy chops)
INCLUDE_OPERATOR_TITLES = [
    "biz ops", "business operations", "business strategy",
    "chief of staff", "head of strategy", "head of operations",
    "gtm strategy", "go-to-market strategy", "strategic operations",
    "growth strategy", "operations lead", "founding operations",
    "founding generalist", "head of growth",
]

# Operator titles that look like generalist but are actually sales/revenue specific — exclude
EXCLUDE_OPERATOR_TITLES = [
    "sales strategy", "sales operations", "sales ops",
    "revenue operations", "revenue ops", "revops",
    "partnerships strategy", "partnerships operations",
    "sales enablement", "sales planning",
    "account operations", "deal operations",
    "delivery operations", "delivery management",
    "program management", "technical program",
    "project management", "implementation",
    "legal operations", "legal ops",
    "finance and", "financial operations", "strategic finance",  # finance-first roles
    "chief of staff, sales", "chief of staff, marketing",  # function-qualified CoS = not general
    "chief of staff, engineering", "chief of staff, product",
    "apac", "emea", "latam", "international",  # regional focus
]

# Locations that are clearly outside the US — hard filter
NON_US_LOCATIONS = [
    # UK / Ireland
    "london", "dublin", "manchester", "edinburgh", "uk", "united kingdom", "ireland",
    # Western Europe
    "berlin", "munich", "hamburg", "germany", "stockholm", "gothenburg", "sweden",
    "amsterdam", "netherlands", "paris", "france", "zurich", "switzerland",
    "copenhagen", "denmark", "oslo", "norway", "helsinki", "finland",
    "vienna", "austria", "brussels", "belgium", "lisbon", "portugal",
    "madrid", "spain", "barcelona", "milan", "italy", "rome",
    "warsaw", "poland", "prague", "czech",
    # Nordics / other EU catch-alls
    "europe", "emea",
    # Canada / Australia / NZ
    "toronto", "vancouver", "montreal", "canada", "sydney", "melbourne", "australia",
    "auckland", "new zealand",
    # Asia
    "singapore", "bangalore", "bengaluru", "mumbai", "delhi", "india",
    "beijing", "shanghai", "china", "tokyo", "japan", "seoul", "korea",
    "hong kong", "taipei", "taiwan",
    # Latin America
    "apac", "latam", "mexico city", "são paulo", "buenos aires",
]


def passes_location_filter(location: str) -> bool:
    """Returns False if job is clearly outside the US and not remote."""
    if not location:
        return True  # no location = assume US or remote, let scoring handle it
    loc = location.lower()
    if "remote" in loc:
        return True
    if any(non_us in loc for non_us in NON_US_LOCATIONS):
        return False
    return True  # anything else — US city, unknown — let through


# No-list keywords in title or department — skip these
NO_LIST_KEYWORDS = [
    "security", "cybersecurity", "defense", "military",
    "developer tools", "infrastructure", "mlops", "devops",
    "radiology", "clinical", "medical", "health system",
    # Note: "healthcare" and "health" removed — insurtech/health insurance are valid targets
    "coding", "code generation", "developer experience",
]

def _load_companies_from_db():
    """Load all trackable companies from Supabase. Returns (ashby_dict, greenhouse_dict)."""
    try:
        res = supabase.table("companies").select("name, ashby_slug, greenhouse_slug, skip").execute()
        ashby, greenhouse = {}, {}
        for row in (res.data or []):
            if row.get("skip"):
                continue
            name = row["name"]
            if row.get("ashby_slug"):
                ashby[row["ashby_slug"]] = name
            if row.get("greenhouse_slug"):
                greenhouse[row["greenhouse_slug"]] = name
        return ashby, greenhouse
    except Exception as e:
        print(f"  ⚠ Could not load companies from DB: {e}")
        return {}, {}

ASHBY_COMPANIES, GREENHOUSE_COMPANIES = _load_companies_from_db()
SKIP_COMPANIES: set = set()  # filtering handled by DB skip field in _load_companies_from_db


def get_role_type(title: str):
    """Returns 'pm', 'operator', or None (skip this job)."""
    t = title.lower()
    # PM: check exclusions first
    excluded = any(exc in t for exc in EXCLUDE_PM_TITLES)
    if not excluded:
        for inc in INCLUDE_PM_TITLES:
            if inc in t:
                return "pm"
    # Operator/generalist roles — check exclusions first
    if any(exc in t for exc in EXCLUDE_OPERATOR_TITLES):
        return None
    for inc in INCLUDE_OPERATOR_TITLES:
        if inc in t:
            return "operator"
    return None


def passes_seniority_filter(title: str) -> bool:
    return get_role_type(title) is not None


def passes_no_list_filter(title: str, dept: str = "") -> bool:
    combined = (title + " " + dept).lower()
    for kw in NO_LIST_KEYWORDS:
        if kw in combined:
            return False
    return True


def get_company_id(name: str):
    res = supabase.table("companies").select("id").eq("name", name).execute()
    if res.data:
        return res.data[0]["id"]
    return None


def job_exists(url: str) -> bool:
    res = supabase.table("jobs").select("id").eq("url", url).execute()
    return bool(res.data)


def save_job(company_name: str, company_id, title: str, url: str, source: str, role_type: str = "pm", jd_text: str = ""):
    if job_exists(url):
        return False
    data = {
        "company_name": company_name,
        "company_id": company_id,
        "title": title,
        "url": url,
        "source": source,
        "status": "new",
        "jd_text": jd_text or None,
        "score_breakdown": {"role_type": role_type},
    }
    supabase.table("jobs").insert(data).execute()
    return True


def poll_ashby() -> list[dict]:
    found = []
    for slug, company_name in ASHBY_COMPANIES.items():
        if company_name in SKIP_COMPANIES:
            continue
        url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
        try:
            r = httpx.get(url, timeout=10)
            r.raise_for_status()
            data = r.json()
            jobs = data.get("jobs", data.get("jobPostings", []))
            company_id = get_company_id(company_name)

            for job in jobs:
                title = job.get("title", "")
                dept = job.get("department", job.get("departmentName", ""))
                job_url = job.get("jobUrl", "")
                location = job.get("location", "")
                jd_text = job.get("descriptionPlain", "")[:4000]  # cap at 4k chars

                if not passes_location_filter(location):
                    continue

                role_type = get_role_type(title)
                if not role_type:
                    continue
                if not passes_no_list_filter(title, dept):
                    continue

                saved = save_job(company_name, company_id, title, job_url, "ashby", role_type, jd_text)
                status = "NEW" if saved else "exists"
                label = f"[{role_type.upper()}]" if role_type == "operator" else ""
                found.append({"company": company_name, "title": title, "status": status, "role_type": role_type})
                print(f"  {'✓ NEW' if saved else '  ---'} [{company_name}] {title} {label}")

        except Exception as e:
            print(f"  ✗ Ashby/{slug}: {e}")

    return found


def poll_greenhouse() -> list[dict]:
    found = []
    for slug, company_name in GREENHOUSE_COMPANIES.items():
        if company_name in SKIP_COMPANIES:
            continue
        url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
        try:
            r = httpx.get(url, timeout=10)
            r.raise_for_status()
            data = r.json()
            jobs = data.get("jobs", [])
            company_id = get_company_id(company_name)
            seen_titles = set()  # deduplicate within same company (multi-office listings)

            for job in jobs:
                title = job.get("title", "")
                dept = job.get("departments", [{}])[0].get("name", "") if job.get("departments") else ""
                job_url = job.get("absolute_url", "")
                location = job.get("offices", [{}])[0].get("name", "") if job.get("offices") else ""

                if not passes_location_filter(location):
                    continue

                role_type = get_role_type(title)
                if not role_type:
                    continue
                if not passes_no_list_filter(title, dept):
                    continue
                if title.strip() in seen_titles:
                    continue
                seen_titles.add(title.strip())

                # Fetch full JD from Greenhouse per-job endpoint
                jd_text = ""
                job_id = job.get("id")
                if job_id:
                    try:
                        jd_r = httpx.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs/{job_id}", timeout=8)
                        if jd_r.status_code == 200:
                            import re
                            raw_html = jd_r.json().get("content", "")
                            jd_text = re.sub(r"<[^>]+>", " ", raw_html).strip()[:4000]
                    except Exception:
                        pass

                saved = save_job(company_name, company_id, title, job_url, "greenhouse", role_type, jd_text)
                status = "NEW" if saved else "exists"
                label = f"[{role_type.upper()}]" if role_type == "operator" else ""
                found.append({"company": company_name, "title": title, "status": status, "role_type": role_type})
                print(f"  {'✓ NEW' if saved else '  ---'} [{company_name}] {title} {label}")

        except Exception as e:
            print(f"  ✗ Greenhouse/{slug}: {e}")

    return found


# HN Who is Hiring removed — comment threads don't reliably extract structured job data


def poll_linkedin() -> list[dict]:
    """
    Searches LinkedIn for PM and operator jobs at AI/tech startups via Apify.
    Uses very specific search terms to keep results relevant.
    Company size filter: 11-500 employees (no big tech).
    """
    apify_key = os.getenv("APIFY_API_KEY")
    if not apify_key:
        print("  ✗ LinkedIn: APIFY_API_KEY not set")
        return []

    apify = ApifyClient(apify_key)
    found = []

    # LinkedIn URL params:
    # location=United States = US-wide (target companies can be anywhere in US)
    # f_TPR=r604800 = past week
    # f_E=4 = mid-senior level
    # f_CS=2,3,4 = 11-50, 51-200, 201-500 employees (no big tech)
    import urllib.parse
    base = (
        "https://www.linkedin.com/jobs/search/"
        "?location=United%20States"
        "&f_TPR=r604800&f_E=4&f_CS=2%2C3%2C4"
        "&keywords="
    )
    search_terms = [
        # Generic PM titles — catches roles at AI startups that don't say "AI" in the title
        "product manager",
        "senior product manager",
        # AI-specific variants
        "product manager AI agent",
        "founding product manager AI",
        "head of product AI startup",
        "product manager enterprise AI",
        "product manager fintech AI",
    ]
    urls = [base + urllib.parse.quote(t) for t in search_terms]

    try:
        print(f"  Running LinkedIn scraper ({len(urls)} searches)...")
        run = apify.actor("curious_coder/linkedin-jobs-scraper").call(
            run_input={"urls": urls, "limit": 25},
            timeout_secs=300,
        )

        items = list(apify.dataset(run["defaultDatasetId"]).iterate_items())
        print(f"  LinkedIn returned {len(items)} raw results")

        seen_urls = set()
        for job in items:
            title = job.get("title", "")
            company = job.get("companyName", "") or ""
            location = job.get("location", "") or ""
            job_url = job.get("link", "") or job.get("applyUrl", "")
            jd_text = (job.get("descriptionText", "") or "")[:4000]
            employees = job.get("companyEmployeesCount") or 0

            # Skip if already seen (dedup across search queries)
            if job_url in seen_urls:
                continue
            seen_urls.add(job_url)

            # Hard filters
            if not passes_location_filter(location):
                continue
            role_type = get_role_type(title)
            if not role_type:
                continue
            if not passes_no_list_filter(title):
                continue

            # Skip obviously large companies (500+ on LinkedIn)
            if employees and employees > 500:
                continue

            # Quality gate: only save jobs from companies already tracked OR that pass company scoring
            # Prevents random unvetted companies from polluting the pipeline
            company_lower = company.lower().strip()
            already_tracked = any(
                company_lower == name.lower().strip()
                for name in list(ASHBY_COMPANIES.keys()) + list(GREENHOUSE_COMPANIES.keys())
            )
            if not already_tracked:
                # Score the company before adding — skip if not a fit
                try:
                    from agent.discover_from_rss import score_company_for_radar
                    scored = score_company_for_radar(company, "", jd_text[:500])
                    if scored.get("attention_score", 0) < 55:
                        print(f"  — Skipping [{company}] — company scored {scored.get('attention_score', 0)}/100")
                        continue
                    print(f"  ✓ [{company}] passed company score: {scored.get('attention_score')}/100")
                except Exception:
                    # If scoring fails, skip unknown companies — don't pollute the pipeline
                    continue

            company_id = get_company_id(company)
            saved = save_job(company, company_id, title, job_url, "linkedin", role_type, jd_text)
            label = f"[{role_type.upper()}]" if role_type == "operator" else ""
            status = "NEW" if saved else "exists"
            found.append({"company": company, "title": title, "status": status})
            print(f"  {'✓ NEW' if saved else '  ---'} [{company}] {title} {label}")

    except Exception as e:
        print(f"  ✗ LinkedIn error: {e}")

    return found


def poll_wats() -> list[dict]:
    """
    Scrapes Work at a Startup (YC job board) for PM/operator roles via Apify.
    Data structure: each item = {company: {...}, jobs: [{title, location, url}]}
    Filters to SF Bay Area, applies our standard title + no-list filters.
    """
    apify_key = os.getenv("APIFY_API_KEY")
    if not apify_key:
        print("  ✗ WATS: APIFY_API_KEY not set")
        return []

    apify = ApifyClient(apify_key)
    found = []

    try:
        print("  Running WATS scraper (YC companies, SF Bay Area, Product roles)...")
        run = apify.actor("artemlazarevm/yc-jobs-scraper").call(
            run_input={
                "role": "Product",
                "filterByLocation": ["San Francisco"],
                "limit": 50,
            },
            timeout_secs=300,
            memory_mbytes=512,
        )

        items = list(apify.dataset(run["defaultDatasetId"]).iterate_items())
        print(f"  WATS: {len(items)} YC companies with Product roles in SF")

        for item in items:
            # Each item is one company with multiple jobs
            company_info = item.get("company", {})
            company = company_info.get("name", "")
            team_size = company_info.get("teamSize", 0)
            yc_batch = company_info.get("ycBatch", "")

            # Skip large companies (unicorns/big players — Airbnb, Stripe already covered)
            if team_size and team_size > 500:
                continue

            for job in item.get("jobs", []):
                title = job.get("title", "")
                location = job.get("location", "") or ""
                job_url = job.get("url", "")
                jd_text = (job.get("description", "") or "")[:4000]

                # Our standard filters
                if not passes_location_filter(location):
                    continue
                role_type = get_role_type(title)
                if not role_type:
                    continue
                if not passes_no_list_filter(title):
                    continue

                company_id = get_company_id(company)
                saved = save_job(company, company_id, title, job_url, "wats", role_type, jd_text)
                label = f"[{role_type.upper()}]" if role_type == "operator" else ""
                status = "NEW" if saved else "exists"
                batch_tag = f" ({yc_batch})" if yc_batch else ""
                found.append({"company": company, "title": title, "status": status})
                print(f"  {'✓ NEW' if saved else '  ---'} [{company}{batch_tag}] {title} {label}")

    except Exception as e:
        print(f"  ✗ WATS error: {e}")

    return found


def poll_specific_companies(ashby_slugs: list = None, greenhouse_slugs: list = None) -> list:
    """Poll only specific companies by slug. Used after adding companies from a post."""
    found = []

    for slug in (ashby_slugs or []):
        company_name = ASHBY_COMPANIES.get(slug, slug)
        if company_name in SKIP_COMPANIES:
            continue
        try:
            r = httpx.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}", timeout=10)
            r.raise_for_status()
            jobs = r.json().get("jobs", [])
            company_id = get_company_id(company_name)
            for job in jobs:
                title = job.get("title", "")
                dept = job.get("department", "")
                job_url = job.get("jobUrl", "")
                location = job.get("location", "")
                jd_text = job.get("descriptionPlain", "")[:4000]
                if not passes_location_filter(location):
                    continue
                role_type = get_role_type(title)
                if not role_type or not passes_no_list_filter(title, dept):
                    continue
                saved = save_job(company_name, company_id, title, job_url, "ashby", role_type, jd_text)
                if saved:
                    found.append({"company": company_name, "title": title})
        except Exception as e:
            print(f"  ✗ Ashby/{slug}: {e}")

    for slug in (greenhouse_slugs or []):
        company_name = GREENHOUSE_COMPANIES.get(slug, slug)
        if company_name in SKIP_COMPANIES:
            continue
        try:
            r = httpx.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", timeout=10)
            r.raise_for_status()
            jobs = r.json().get("jobs", [])
            company_id = get_company_id(company_name)
            seen_titles = set()
            for job in jobs:
                title = job.get("title", "")
                dept = job.get("departments", [{}])[0].get("name", "") if job.get("departments") else ""
                job_url = job.get("absolute_url", "")
                location = job.get("offices", [{}])[0].get("name", "") if job.get("offices") else ""
                if not passes_location_filter(location) or title.strip() in seen_titles:
                    continue
                seen_titles.add(title.strip())
                role_type = get_role_type(title)
                if not role_type or not passes_no_list_filter(title, dept):
                    continue
                jd_text = ""
                job_id = job.get("id")
                if job_id:
                    try:
                        jd_r = httpx.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs/{job_id}", timeout=8)
                        if jd_r.status_code == 200:
                            raw_html = jd_r.json().get("content", "")
                            jd_text = re.sub(r"<[^>]+>", " ", raw_html).strip()[:4000]
                    except Exception:
                        pass
                saved = save_job(company_name, company_id, title, job_url, "greenhouse", role_type, jd_text)
                if saved:
                    found.append({"company": company_name, "title": title})
        except Exception as e:
            print(f"  ✗ Greenhouse/{slug}: {e}")

    return found


def run_discovery():
    print("\n=== Job Discovery ===")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

    print("--- Ashby ---")
    ashby_results = poll_ashby()

    print("\n--- Greenhouse ---")
    greenhouse_results = poll_greenhouse()

    print("\n--- LinkedIn (via Apify) ---")
    linkedin_results = poll_linkedin()

    print("\n--- Work at a Startup (via Apify) ---")
    wats_results = poll_wats()

    all_results = ashby_results + greenhouse_results + linkedin_results + wats_results
    new_jobs = [r for r in all_results if r.get("status") == "NEW"]
    print(f"\nDone. {len(new_jobs)} new jobs found.")
    return new_jobs


if __name__ == "__main__":
    run_discovery()
