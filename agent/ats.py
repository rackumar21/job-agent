"""
ATS analysis — compares Rachita's resume against a job description.

Flow:
  1. Load resume from profile/resume.md (cached in Claude system prompt)
  2. Send JD + job details as user message
  3. Get structured JSON: ats_score, keyword_matches, gaps, rewrite suggestions

Uses Claude Haiku + prompt caching for cost efficiency.
Resume is cached across calls (90% cost reduction on repeated analysis).
"""

import os
import json
from pathlib import Path
import anthropic
from dotenv import load_dotenv

load_dotenv()
_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

_PROFILE_DIR = Path(__file__).parent.parent / "profile"


def _load_resume() -> str:
    path = _PROFILE_DIR / "resume.md"
    if path.exists():
        return path.read_text()
    return ""


_SYSTEM_PROMPT = """You are a senior technical recruiter AND an ATS system simultaneously.
You evaluate resumes against job descriptions with honest, actionable analysis.

Your job is to tell the candidate exactly:
1. How well their resume matches this JD (score + specific evidence)
2. What keywords are missing that would get them filtered out
3. Which of their existing bullets are strongest for THIS role
4. The top 3 highest-impact rewrites they could make
5. What angles to lead with in a cover letter

Be honest. Don't inflate scores. A 70 is a solid match — not every role needs to be 90+.

CANDIDATE RESUME:
{resume}"""


def analyze_ats(title: str, company: str, jd_text: str) -> dict:
    """
    Run ATS analysis comparing the resume against a job description.

    Returns structured dict:
    {
        "ats_score": int (0-100),
        "summary": str,
        "keyword_matches": [{"keyword": str, "found_in_resume": bool, "context": str}],
        "missing_keywords": [str],
        "strong_matches": [str],
        "gaps": [{"gap": str, "severity": "high|medium|low", "recommendation": str}],
        "rewrite_suggestions": [{"original": str, "rewritten": str, "reason": str}],
        "cover_letter_angles": [str]
    }
    """
    resume = _load_resume()
    if not resume:
        return {"error": "Resume file not found at profile/resume.md"}

    jd_trimmed = (jd_text or "").strip()[:5000]
    if not jd_trimmed:
        return {"error": "No job description text available for this role. Try viewing the job posting directly."}

    system_text = _SYSTEM_PROMPT.format(resume=resume)

    user_message = f"""Evaluate this resume against the job below.

JOB: {title} at {company}

JOB DESCRIPTION:
{jd_trimmed}

Return ONLY valid JSON (no markdown, no code fences, no explanation):
{{
  "ats_score": <integer 0-100>,
  "summary": "<2-3 sentences: overall match, biggest strength, biggest gap>",
  "keyword_matches": [
    {{"keyword": "<important term from JD>", "found_in_resume": <true|false>, "context": "<where it appears in resume, or empty string>"}}
  ],
  "missing_keywords": ["<important JD term missing from resume>"],
  "strong_matches": [
    "<exact or paraphrased resume bullet that directly addresses a JD requirement>"
  ],
  "gaps": [
    {{"gap": "<specific gap>", "severity": "<high|medium|low>", "recommendation": "<concrete, specific fix>"}}
  ],
  "rewrite_suggestions": [
    {{"original": "<existing resume bullet, abbreviated>", "rewritten": "<improved version with JD keywords>", "reason": "<why this change helps>"}}
  ],
  "cover_letter_angles": [
    "<specific angle or story to lead with for this role>"
  ]
}}

Rules:
- keyword_matches: include 8-12 of the most important terms from the JD
- missing_keywords: only include genuinely important terms, not every word
- strong_matches: max 3 bullets
- gaps: max 4 gaps, focus on high-severity ones
- rewrite_suggestions: exactly 3, highest-impact only
- cover_letter_angles: 2-3 specific angles (not generic)
- Score honestly: 60-75 is a strong match for most roles"""

    try:
        msg = _client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            system=[{
                "type": "text",
                "text": system_text,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": user_message}],
        )
        raw = msg.content[0].text.strip()
        # Strip markdown fences if model wraps anyway
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        return json.loads(raw)
    except json.JSONDecodeError as e:
        return {"error": f"JSON parse error: {e}"}
    except Exception as e:
        return {"error": str(e)}
