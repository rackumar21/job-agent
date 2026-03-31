"""
Job Agent Scheduler
Runs three jobs automatically:

  1. Daily job discovery (7:00am PT) — polls Ashby + Greenhouse for new PM/ops roles
  2. RSS funding scan (every 3 days, 7:15am PT) — scans Next Play + TechCrunch for new companies
  3. Monday morning brief (Mondays 7:30am PT) — logs weekly summary to logs/morning_brief.log

Start: python scheduler.py (or double-click Start Scheduler.command)
Logs:  logs/scheduler.log and logs/morning_brief.log
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

load_dotenv()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

log_dir = Path(__file__).parent / "logs"
log_dir.mkdir(exist_ok=True)
log_file = log_dir / "scheduler.log"
brief_file = log_dir / "morning_brief.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Job 1: Daily job discovery (7:00am PT)
# ---------------------------------------------------------------------------

def job_discovery_job():
    log.info("=== Weekly Job Discovery ===")
    try:
        from agent.discover import poll_ashby, poll_greenhouse, poll_linkedin, poll_wats
        ashby = poll_ashby()
        gh = poll_greenhouse()
        linkedin = poll_linkedin()
        wats = poll_wats()
        all_results = ashby + gh + linkedin + wats
        new_jobs = [r for r in all_results if r.get("status") == "NEW"]
        log.info(
            f"Discovery complete: {len(new_jobs)} new role(s) found "
            f"(Ashby: {sum(1 for r in ashby if r.get('status')=='NEW')}, "
            f"Greenhouse: {sum(1 for r in gh if r.get('status')=='NEW')}, "
            f"LinkedIn: {sum(1 for r in linkedin if r.get('status')=='NEW')}, "
            f"WATS: {sum(1 for r in wats if r.get('status')=='NEW')})"
        )
        if new_jobs:
            from agent.score import score_new_jobs
            scored = score_new_jobs()
            log.info(f"Scored {scored} new job(s)")
    except Exception as e:
        log.error(f"Job discovery failed: {e}", exc_info=True)


# ---------------------------------------------------------------------------
# Job 2: RSS funding scan (every 3 days, 7:15am PT)
# ---------------------------------------------------------------------------

def rss_scan_job():
    log.info("=== RSS Funding Scan ===")
    try:
        from agent.discover_from_rss import run_rss_scan
        result = run_rss_scan()
        log.info(
            f"RSS scan complete: {result['roles_found']} new role(s), "
            f"{result['radar_added']} added to radar"
        )
    except Exception as e:
        log.error(f"RSS scan failed: {e}", exc_info=True)


# ---------------------------------------------------------------------------
# Job 3: Monday morning brief (Mondays 7:30am PT)
# ---------------------------------------------------------------------------

def morning_brief_job():
    log.info("=== Monday Morning Brief ===")
    try:
        # Score any jobs that came in during the 9am discovery runs
        # so the brief reflects everything discovered this morning
        from agent.score import score_new_jobs
        newly_scored = score_new_jobs(limit=50)
        if newly_scored:
            log.info(f"Scored {newly_scored} new job(s) before generating brief")

        brief = generate_morning_brief()
        with open(brief_file, "w") as f:
            f.write(brief)
        log.info(f"Morning brief written to {brief_file}")
        for line in brief.splitlines():
            log.info(line)
    except Exception as e:
        log.error(f"Morning brief failed: {e}", exc_info=True)


def generate_morning_brief() -> str:
    """
    Generate a Monday action brief — up to 10 specific, prioritized to-do items.
    Each item has a clear action and outreach message where applicable.
    """
    import anthropic
    from supabase import create_client
    s = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
    claude = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    now = datetime.now(timezone.utc)
    last_monday = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    lines = [
        f"{'=' * 60}",
        f"  MONDAY BRIEF  —  {now.strftime('%B %d, %Y')}",
        f"{'=' * 60}",
        "",
    ]

    # -----------------------------------------------------------------------
    # Gather raw data
    # -----------------------------------------------------------------------

    # New this week
    new_jobs_wk = (
        s.table("jobs").select("company_name, title, attractiveness_score, status, url, score_breakdown")
        .gte("created_at", last_monday.isoformat())
        .order("attractiveness_score", desc=True, nullsfirst=False)
        .execute().data or []
    )
    new_co_count = s.table("companies").select("id", count="exact").gte("created_at", last_monday.isoformat()).execute().count or 0

    lines.append(f"THIS WEEK: {len(new_jobs_wk)} new roles · {new_co_count} new companies discovered")
    lines.append("")

    # -----------------------------------------------------------------------
    # Build action items — priority ordered
    # -----------------------------------------------------------------------

    action_items = []

    # Priority 1: Application follow-ups overdue
    applied_jobs = (
        s.table("jobs").select("company_name, title, score_breakdown, url")
        .eq("status", "applied").execute().data or []
    )
    for j in applied_jobs:
        bd = j.get("score_breakdown") or {}
        applied_at = bd.get("applied_at", "")
        followup_at = bd.get("apply_followup_at", "")
        if followup_at:
            try:
                fu_dt = datetime.fromisoformat(followup_at.replace("Z", "+00:00"))
                if fu_dt <= now:
                    days = (now - fu_dt).days
                    action_items.append({
                        "priority": 1,
                        "type": "follow_up_application",
                        "company": j["company_name"],
                        "title": j["title"],
                        "note": f"Follow-up was due {days}d ago",
                        "url": j.get("url", ""),
                    })
            except Exception:
                pass
        elif applied_at:
            try:
                app_dt = datetime.fromisoformat(applied_at.replace("Z", "+00:00"))
                days = (now - app_dt).days
                if days >= 7:
                    action_items.append({
                        "priority": 1,
                        "type": "follow_up_application",
                        "company": j["company_name"],
                        "title": j["title"],
                        "note": f"Applied {days}d ago, no follow-up scheduled",
                        "url": j.get("url", ""),
                    })
            except Exception:
                pass

    # Priority 2: Outreach follow-ups (reached out, no notes/response)
    all_jobs = s.table("jobs").select("company_name, title, score_breakdown").execute().data or []
    for j in all_jobs:
        bd = j.get("score_breakdown") or {}
        ro_at = bd.get("reached_out_at", "")
        ro_notes = bd.get("reached_out_notes", "")
        if ro_at and not ro_notes:
            try:
                ro_dt = datetime.fromisoformat(ro_at.replace("Z", "+00:00"))
                days = (now - ro_dt).days
                if days >= 3:
                    action_items.append({
                        "priority": 2,
                        "type": "follow_up_outreach",
                        "company": j["company_name"],
                        "title": j["title"],
                        "note": f"Reached out {days}d ago, no response logged",
                    })
            except Exception:
                pass

    # Priority 3: Top unactioned open roles (score 80+, status new/borderline)
    top_open = (
        s.table("jobs").select("id, company_name, title, attractiveness_score, url, score_breakdown")
        .in_("status", ["new", "borderline", "prep_ready"])
        .gte("attractiveness_score", 80)
        .order("attractiveness_score", desc=True)
        .limit(4).execute().data or []
    )
    for j in top_open:
        bd = j.get("score_breakdown") or {}
        action_items.append({
            "priority": 3,
            "type": "apply_now",
            "company": j["company_name"],
            "title": j["title"],
            "score": j.get("attractiveness_score"),
            "key_angle": bd.get("key_angle", ""),
            "url": j.get("url", ""),
        })

    # Priority 4: High-score radar companies with no outreach yet (generate message)
    hot_radar = (
        s.table("companies")
        .select("name, sector, attention_score, what_they_do, relationship_message, stage")
        .gte("attention_score", 75)
        .is_("radar_status", "null")
        .neq("feedback", "not_for_me")
        .order("attention_score", desc=True)
        .limit(5).execute().data or []
    )
    for r in hot_radar:
        action_items.append({
            "priority": 4,
            "type": "reach_out",
            "company": r["name"],
            "sector": r.get("sector", ""),
            "score": r.get("attention_score"),
            "what_they_do": r.get("what_they_do", ""),
            "stage": r.get("stage", ""),
            "relationship_message": r.get("relationship_message", ""),
        })

    # Sort and cap at 10
    action_items.sort(key=lambda x: x["priority"])
    action_items = action_items[:10]

    # -----------------------------------------------------------------------
    # Format action items
    # -----------------------------------------------------------------------

    if action_items:
        lines.append(f"YOUR TO-DO LIST THIS WEEK ({len(action_items)} items)")
        lines.append("-" * 60)
        lines.append("")

        for i, item in enumerate(action_items, 1):
            t = item["type"]

            if t == "follow_up_application":
                lines.append(f"{i}. ⏰  FOLLOW UP ON APPLICATION")
                lines.append(f"   {item['company']} — {item['title']}")
                lines.append(f"   {item['note']}")
                lines.append(f"   Action: Send a 3-line note to your contact or via the portal.")
                lines.append(f"   Draft: 'Hi [name], I applied to the {item['title']} role recently")
                lines.append(f"   and wanted to reiterate my interest. Happy to share more about")
                lines.append(f"   my work on PayPal App Switch (+450bps CVR) or TruthSeek (voice AI evals).'")
                if item.get("url"):
                    lines.append(f"   Link: {item['url']}")

            elif t == "follow_up_outreach":
                lines.append(f"{i}. 📧  FOLLOW UP ON OUTREACH")
                lines.append(f"   {item['company']} — {item['title']}")
                lines.append(f"   {item['note']}")
                lines.append(f"   Action: Send one short follow-up. Reference your original note.")

            elif t == "apply_now":
                lines.append(f"{i}. 🚀  APPLY NOW  —  {item['score']}/100")
                lines.append(f"   {item['company']} — {item['title']}")
                if item.get("key_angle"):
                    lines.append(f"   Why you: {item['key_angle']}")
                if item.get("url"):
                    lines.append(f"   Apply: {item['url']}")

            elif t == "reach_out":
                lines.append(f"{i}. 🔥  REACH OUT NOW  —  {item['score']}/100  ({item.get('sector','')})")
                lines.append(f"   {item['company']}")
                if item.get("what_they_do"):
                    lines.append(f"   What they do: {item['what_they_do']}")
                if item.get("relationship_message"):
                    lines.append(f"   Draft LinkedIn message:")
                    for msg_line in item["relationship_message"].split("\n"):
                        lines.append(f"   {msg_line}")
                else:
                    # Generate one on the fly
                    try:
                        msg = claude.messages.create(
                            model="claude-sonnet-4-6",
                            max_tokens=200,
                            messages=[{"role": "user", "content": f"""Write a 3-sentence LinkedIn message from Rachita Kumar to someone at {item['company']}.

Rachita's background: Senior PM at PayPal (shipped App Switch, first mobile checkout, +450bps CVR). Founding PM at TruthSeek (voice AI, LLM evals). Finance background (PE/IB India). Builder (built AI apps solo).

{item['company']} does: {item.get('what_they_do','')}

Rules: specific, no fluff, no em dashes. End with a clear ask for a 20-min call. Sound like a person, not a cover letter."""}]
                        )
                        gen_msg = msg.content[0].text.strip()
                        lines.append(f"   Draft LinkedIn message (generated):")
                        for msg_line in gen_msg.split("\n"):
                            lines.append(f"   {msg_line}")
                        # Save it back
                        s.table("companies").update({"relationship_message": gen_msg}).eq("name", item["company"]).execute()
                    except Exception:
                        lines.append(f"   Action: Find a PM or founder on LinkedIn and send a short note about your AI PM background.")

            lines.append("")

    # -----------------------------------------------------------------------
    # New roles this week (if any)
    # -----------------------------------------------------------------------

    if new_jobs_wk:
        lines.append("-" * 60)
        lines.append(f"NEW ROLES THIS WEEK (top 10):")
        for j in new_jobs_wk[:10]:
            score = j.get("attractiveness_score")
            score_str = f"{score}/100" if score else "unscored"
            lines.append(f"  {j['company_name']} — {j['title']} · {score_str}")
        lines.append("")

    lines.append(f"{'=' * 60}")
    lines.append(f"  Generated: {now.strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"{'=' * 60}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Job 4: LinkedIn curator monitor (every 6 hours)
# ---------------------------------------------------------------------------

def linkedin_monitor_job():
    log.info("=== LinkedIn Curator Monitor ===")
    try:
        from agent.monitor_linkedin import run_linkedin_monitor
        result = run_linkedin_monitor()
        log.info(
            f"LinkedIn monitor: {result['posts_processed']} new post(s), "
            f"{result['companies_added']} companies added"
        )
        if result.get("posts"):
            for p in result["posts"]:
                log.info(f"  {p['author']}: {p['companies_found']} companies found, {p['companies_added']} added")
    except Exception as e:
        log.error(f"LinkedIn monitor failed: {e}", exc_info=True)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    log.info("Job Agent Scheduler starting")
    log.info(f"Logs: {log_file}")
    log.info(f"Morning brief: {brief_file}")

    # Only run startup jobs if today is Monday — avoids wasting tokens on mid-week restarts
    today = datetime.now(timezone.utc).strftime("%A")
    if today == "Monday":
        log.info("Monday startup — running all discovery jobs now...")
        job_discovery_job()
        rss_scan_job()
        linkedin_monitor_job()
        morning_brief_job()
    else:
        log.info(f"Startup on {today} — skipping discovery (runs Monday only). Scheduler armed.")

    scheduler = BlockingScheduler(timezone="America/Los_Angeles")

    # Job board polling (Ashby + Greenhouse + LinkedIn + WATS) — Monday 9:00am PT
    scheduler.add_job(
        job_discovery_job,
        trigger=CronTrigger(
            day_of_week="mon",
            hour=9,
            minute=0,
            timezone="America/Los_Angeles",
        ),
        id="job_discovery",
        name="Job Board Polling",
        replace_existing=True,
    )

    # RSS scan (Next Play, Bella Nazzari, TechCrunch) — Monday 9:05am PT
    scheduler.add_job(
        rss_scan_job,
        trigger=CronTrigger(
            day_of_week="mon",
            hour=9,
            minute=5,
            timezone="America/Los_Angeles",
        ),
        id="rss_scan",
        name="RSS Scan",
        replace_existing=True,
    )

    # LinkedIn curator monitor — Monday + Thursday 9:10am PT
    scheduler.add_job(
        linkedin_monitor_job,
        trigger=CronTrigger(
            day_of_week="mon,thu",
            hour=9,
            minute=10,
            timezone="America/Los_Angeles",
        ),
        id="linkedin_monitor",
        name="LinkedIn Curator Monitor",
        replace_existing=True,
    )

    # Monday brief with to-do list + outreach drafts — Monday 10:00am PT
    # Runs after all discovery jobs have completed
    scheduler.add_job(
        morning_brief_job,
        trigger=CronTrigger(
            day_of_week="mon",
            hour=10,
            minute=0,
            timezone="America/Los_Angeles",
        ),
        id="morning_brief",
        name="Monday Brief",
        replace_existing=True,
    )

    log.info("Scheduler running:")
    log.info("  Job board polling      — Monday 9:00am PT (Ashby, Greenhouse, LinkedIn, WATS)")
    log.info("  RSS scan (3 sources)   — Monday 9:05am PT")
    log.info("  LinkedIn curator scan  — Monday + Thursday 9:10am PT")
    log.info("  Monday brief + to-do   — Monday 10:00am PT")
    log.info("Press Ctrl+C to stop.")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler stopped.")
