# Job Agent — V2 Ideas

Ideas for future versions. Ordered roughly by impact.

---

## Interview prep generator

**One click before every interview.**

Input: company name + role title
Output:
- Company research brief (what they do, recent news, funding, key execs)
- Why Rachita is a fit (specific alignment between her background and this company's mission)
- 5 questions she should ask (specific to the company's stage, product, and role)
- Which of her stories to lead with (mapped to the role's likely interview themes)
- Red flags to address proactively

Could be triggered from the Pipeline tab: "Prep for interview" button next to each job.

Tech: Claude Sonnet + DuckDuckGo web search + profile/about.md for story selection.

---

## Warm path finder

**Find the right person before applying cold.**

For every company in Open Roles and On Radar:
- Query LinkedIn API (or Proxycurl) for 1st/2nd degree connections at that company
- Surface: name, title, how connected, mutual connections
- Generate a connection request note in Rachita's voice (different from the outreach draft — shorter, warmer)

Priority: 1st degree = reach out now, 2nd degree = ask mutual for intro, 3rd+ = cold outreach

This is the "warm path > cold apply" principle operationalized.

---

## Follow-up reminder system

**Never let a warm lead go cold.**

Track outreach dates and application dates. Surface in the Monday brief:
- Outreach sent 3+ days ago with no response → "Follow up on {Company}"
- Application sent 7+ days ago → "Follow up with recruiter at {Company}"
- Interview scheduled → "Prep reminder 24h before"

Could be a persistent banner at the top of the dashboard (above the nav), not buried in a tab.

Tech: already have `reached_out_at` and `applied_at` in score_breakdown. Just need to surface them.

---

## Score calibration loop

**Did the 75-point threshold work?**

After 30 days of data: look at all jobs scored 75+. Of those, how many led to:
- Application (good — high-quality signal)
- Pipeline move (good)
- Skip (bad — threshold too permissive or scoring miscalibrated)

And all jobs scored 55-74 (borderline):
- How many should have been 75+? (Rachita applies to any borderline = threshold too strict)
- How many were correctly filtered? (Rachita skips them = threshold right)

Surface a "calibration report" weekly. Let Rachita adjust weights without code changes — edit preferences.json.

---

## Natural language search

**"Find me Series B voice AI companies in the US."**

Input: free-text query
Output: filtered view of Open Roles + On Radar matching the query

Could use Claude to interpret the query → extract filters → apply to the companies/jobs tables.
Or use embedding similarity if the data set grows large enough.

---

## Hiring manager finder

**Find the right person for every open role, not just the company.**

For each job in Open Roles:
- Search LinkedIn for "Head of Product", "CPO", "VP Product" at that company
- Also look for the hiring manager listed in the JD (often implicit)
- Add to the outreach draft: "Suggested recipient: {Name}, {Title}"

Tech: Proxycurl or LinkedIn scraping via Apify.

---

## Profile + memory tab

**Makes the agent open-sourceable.**

Right now the agent is hardcoded for Rachita. To open-source it for other job seekers:
- Profile tab in the dashboard: edit resume.md, about.md, preferences.json in the UI
- No-code setup: paste your resume, set preferences, done
- The agent automatically recalibrates scoring weights based on your profile

This is the V2 product if the agent becomes a real thing.

---

## Application form filler (long-term)

**From Kriti's playbook — auto-fill standard application fields.**

For Greenhouse/Ashby jobs: these have structured application forms.
Greenhouse and Ashby APIs expose the form fields.
Could pre-fill: name, email, LinkedIn, resume, and short-answer responses.

Rachita still reviews and submits. Agent drafts, human sends.

Deprioritized: manual tailoring matters more at this stage of job search. Worth revisiting at volume.
