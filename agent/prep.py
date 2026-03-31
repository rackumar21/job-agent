"""
Prep layer — generates a personalized outreach message for each pipeline job.
Run standalone: python agent/prep.py

Generates ONE outreach message per job, ready to send on LinkedIn or email.
Style: observation about what they're building → connect to Rachita's experience → clear ask.
No cover letters. No interview stories. Those come later.
"""

import os
import json
import anthropic
from dotenv import load_dotenv
from supabase import create_client
from datetime import datetime, timezone

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

RACHITA_PROFILE = """
CANDIDATE: Rachita Kumar

Current: Senior PM at PayPal, Branded Checkout (June 2024-present)
- Shipped App Switch, PayPal's first mobile checkout (0-to-1): coordinated 6 engineering tracks,
  ran controlled experiments, +450 bps conversion, $50M incremental TPV, 850K+ monthly attempts.
- A/B conversion program: 6+ concurrent tests per sprint, +300 bps from winners.
- Built a Claude-powered diagnostic tool using Confluence MCP: cut funnel analysis from 2 days
  to 10 minutes. The whole checkout PM team now uses it.

Founding PM, TruthSeek (voice AI qualitative research, ran alongside PayPal, 2025-2026):
- Built the product function from scratch: customer discovery, PRDs, sprint coordination,
  weekly client conversations translated into product direction.
- Designed the LLM voice interview agent that replaced a human moderator.
- Built eval frameworks: follow-up quality lifted from 2.8 to 4.1 out of 5, call completion
  38% to 61%, funnel from 3,758 down to 7 completions.
- Ran live CPG consumer research studies for enterprise clients (OWN/FoodPharmer).
- Owned enterprise client relationships end to end.

Before product: 5 years in private equity and investment banking in India (Madison India Capital,
Premji Invest, Deutsche Bank). Finance-first career before pivoting to product via Wharton MBA.

Builder: Built Lunar (AI health companion) solo in React, Supabase, Claude API, Vercel. Live.
Built this job search agent. Uses Claude Code and Cursor daily.

What she wants: PM or Strategy & Ops at an AI-native company. 50-300 people, post-PMF,
customer-facing work. Not big tech, not pure infra.
"""

OUTREACH_PROMPT = """You are writing a LinkedIn/email outreach message for Rachita Kumar to send to someone at a company she wants to work at. She will find the right person herself and fill in the name. Write [Name] as the placeholder.

RACHITA'S PROFILE:
{profile}

COMPANY: {company}
ROLE SHE'S INTERESTED IN: {title}
ROLE TYPE: {role_type}
JOB DESCRIPTION (for context on what they're building):
{jd}

KEY ANGLE (why she fits this specific role):
{key_angle}

STYLE GUIDE — study these real examples she has written and match this exact style:

EXAMPLE 1 (Sierra, to John — opens with a product observation):
"Hi John. Treating recruiters as entrepreneurs rather than vendors changes the incentive structure entirely. Challenge I see is how do you build AI that makes each recruiter's specialized judgment more valuable. I worked on a version of this at TruthSeek with AI-led research. Would love to connect.

I've spent the last year building and deploying voice AI agents for enterprise clients at TruthSeek. The hard problems I worked on: designing agent behavior that holds up in real conversations, building eval frameworks to measure quality across multiple dimensions, and getting enterprise clients to trust AI. I understand both the technical layer and the customer trust layer, which is where most AI agent products break down.

What draws me to Sierra is the configuration and consistency problem. Building one AI agent is hard. Building a platform where thousands of enterprises can deploy agents that each feel native to their brand, their policies, and their edge cases is a different order of problem entirely. The failure mode isn't the model, it's the space between what the model can do and what each enterprise actually needs it to do in production. I've seen that gap firsthand and I want to work on closing it at Sierra's scale."

EXAMPLE 2 (Juicebox, to Ishan — opens with TruthSeek, connects to why this company/stage):
"Hi Ishan, I'm a Senior PM at PayPal and the founding PM at TruthSeek, a voice AI startup. At TruthSeek I built the product function from scratch: customer discovery, PRDs, sprint coordination, and weekly client conversations that I translated into clear product direction. I iterated on AI agent quality through eval cycles, and owned enterprise client relationships end to end.

At PayPal I've shipped products at scale, run a conversion experimentation program with 6+ concurrent A/B tests per sprint, and navigated complex cross-functional stakeholders to get things done. I know what good product process looks like at a large company and how to strip it down to what actually matters at a startup.

Juicebox is at exactly the stage where founding PM ownership matters most, and this is the kind of role I am actively looking for."

EXAMPLE 3 (Tavus, to Angie — shorter, connects experience directly to their product):
"Hi Angie! I was the founding PM at a voice-AI user research startup. The biggest challenge was making the AI agent feel more human to be able to have a real conversation. That's what drew me to video AI and to Tavus. Love what you're building! I came across a PM role and would love to connect."

EXAMPLE 4 (Listen Labs, to Alfred — specific about what she built, direct connection to what they're building):
"Hi Alfred. I was the founding PM at a voice AI user research platform for SMBs in India. I designed the interview agent, ran LLM-as-judge evals and delivered a live study for a CPG brand. I've been following Listen Labs' growth, love what you're building. I see a founding PM opening, would love to chat."

EXAMPLE 5 (Cold DM to a PM at target company — shorter, leads with what she built, asks about their work):
"I've been following your work at [Company]. I'm a PM at PayPal and also built an AI health companion solo using Claude API and Supabase. Would love 20 minutes to understand how [Company] thinks about [specific problem relevant to their role]."

ADDITIONAL CONTEXT:
- If the company is in fintech, payments, or a regulated industry: her finance background (PE, IB) is a direct asset — use it.
- The outreach should feel like asking about their work, not begging for a job. The interest in the role comes through naturally from the connection she draws.
- If the company is early-stage (seed, Series A), lean on the TruthSeek founding PM story. If larger, lean on PayPal scale + TruthSeek AI depth.
- Never summarise the resume. Pick the ONE most relevant thing and go deep on it.

RULES:
1. Start with "Hi [Name]." — always use [Name] as the placeholder.
2. Open with a specific observation about what they're building or the problem they're solving. This should show you've thought about their business, not just read their homepage.
3. Pick ONE experience from her background — the single most relevant one — and use it to prove the insight in your opening. Do NOT mention both PayPal and TruthSeek. Do NOT list her roles. One company, one or two specific things, that's it.
4. The second paragraph exists to prove the first paragraph. It should feel like evidence for the observation, not a new topic.
5. End with a simple direct ask: "would love to connect" or "would love to chat."
6. NEVER use em dashes (—) or hyphens as dashes. Use commas, semicolons, colons, or full stops.
7. Tone: direct, confident, human. A conversation opener, not a cover letter.
8. Length: 80-180 words. 2-3 short paragraphs. Shorter is better.
9. Do NOT say "I am writing to express my interest" or "I am excited to apply."
10. Do NOT explain the company back to them.
11. Do NOT list achievements like a resume. The message should sound like something a sharp person would actually send, not something generated from a template.

Return ONLY the message text. No subject line, no JSON, no explanation."""


def fetch_pipeline_jobs_without_prep(limit: int = 10):
    res = (
        supabase.table("jobs")
        .select("id, company_name, title, jd_text, url, score_breakdown, score_reasoning, attractiveness_score")
        .eq("status", "pipeline")
        .is_("prep_materials", "null")
        .limit(limit)
        .execute()
    )
    return res.data or []


def generate_outreach(job: dict) -> str:
    bd = job.get("score_breakdown") or {}
    prompt = OUTREACH_PROMPT.format(
        profile=RACHITA_PROFILE,
        company=job["company_name"],
        title=job["title"],
        role_type=bd.get("role_type", "pm"),
        jd=(job.get("jd_text") or "(no job description available)")[:3000],
        key_angle=bd.get("key_angle", ""),
    )
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


def save_prep(job_id: str, outreach_message: str):
    supabase.table("jobs").update({
        "prep_materials": {
            "outreach_message": outreach_message,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    }).eq("id", job_id).execute()


def run_prep(limit: int = 10):
    print("\n=== Prep Layer ===")
    jobs = fetch_pipeline_jobs_without_prep(limit)

    if not jobs:
        print("No pipeline jobs need prep.")
        return

    print(f"Generating outreach for {len(jobs)} jobs...\n")

    for job in jobs:
        company = job["company_name"]
        title = job["title"]
        print(f"  [{company}] {title}")
        try:
            outreach = generate_outreach(job)
            save_prep(job["id"], outreach)
            print(f"    ✓ {len(outreach)} chars")
        except Exception as e:
            print(f"    ! Error: {e}")

    print("\nDone.")


if __name__ == "__main__":
    run_prep()
